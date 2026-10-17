import json

from marketplace_login.infrai_sms import InfraiSmsClient


class Response:
    status = 200
    headers: dict[str, str] = {}

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok":true,"data":{"verified":true},"metadata":{}}'


def test_verify_request_uses_exact_boundary_fields() -> None:
    captured = []

    def opener(request: object, timeout: int) -> Response:
        captured.append(request)
        return Response()

    client = InfraiSmsClient("test-key", opener=opener)
    result = client.verify_otp("+15551234567", "481902", "verify-ORD-7-1")

    request = captured[0]
    assert request.get_method() == "POST"
    assert request.full_url.endswith("/v1/sms/verify")
    assert json.loads(request.data) == {
        "to": "+15551234567",
        "code": "481902",
        "idempotency_key": "verify-ORD-7-1",
    }
    assert result == {"verified": True}

