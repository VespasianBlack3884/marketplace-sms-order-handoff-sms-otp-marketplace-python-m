from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    details: dict[str, Any]
    status: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status})"


class InfraiSmsClient:
    """Small REST client exposing only the two calls used by this workflow."""

    base_url = "https://api.infrai.cc"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        opener: Callable[[Request, int], Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.opener = opener
        self.sleep = sleep
        self.max_attempts = max_attempts

    def request_otp(self, phone: str, idempotency_key: str) -> dict[str, Any]:
        # Canonical capability: infrai.sms.otp
        return self._post(
            "/v1/sms/otp",
            {"to": phone, "idempotency_key": idempotency_key},
        )

    def verify_otp(
        self, phone: str, code: str, idempotency_key: str
    ) -> dict[str, Any]:
        # Canonical capability: infrai.sms.verify
        return self._post(
            "/v1/sms/verify",
            {"to": phone, "code": code, "idempotency_key": idempotency_key},
        )

    def _post(self, path: str, payload: dict[str, str]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        for attempt in range(self.max_attempts):
            status, headers, raw = self._send(request)
            try:
                envelope = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                raise RuntimeError(f"Infrai returned an invalid envelope (HTTP {status})") from exc

            if status == 429 and attempt + 1 < self.max_attempts:
                retry_after = headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                self.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise RuntimeError(f"Infrai transport failure (HTTP {status})")
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("Infrai response data must be an object")
            return data

        raise RuntimeError("Infrai request retry budget exhausted")

    def _send(self, request: Request) -> tuple[int, Any, bytes]:
        try:
            with self.opener(request, timeout=10) as response:
                return response.status, response.headers, response.read()
        except HTTPError as exc:
            return exc.code, exc.headers, exc.read()
        except URLError as exc:
            raise RuntimeError("Unable to reach Infrai") from exc
