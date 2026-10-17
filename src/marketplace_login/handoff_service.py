from __future__ import annotations

import json
from dataclasses import fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TypeVar

from .infrai_sms import InfraiError, InfraiSmsClient
from .order_handoff import (
    BuyerUpdate,
    MarketplaceOrder,
    OrderHandoff,
    SellerAsset,
    StartLoginRequest,
    VerifyLoginRequest,
)

RequestModel = TypeVar("RequestModel", StartLoginRequest, VerifyLoginRequest)


def parse_model(model: type[RequestModel], body: dict[str, Any]) -> RequestModel:
    expected = {field.name for field in fields(model)}
    if set(body) != expected or not all(
        isinstance(body[name], str) and body[name] for name in expected
    ):
        raise ValueError(f"expected non-empty string fields: {sorted(expected)}")
    return model(**body)


def sample_orders() -> dict[str, MarketplaceOrder]:
    order = MarketplaceOrder(
        order_id="ORD-2048",
        buyer_phone="+15551234567",
        seller_assets=[
            SellerAsset("transfer packet", "https://seller.example/assets/ORD-2048"),
        ],
        buyer_updates=[
            BuyerUpdate("2026-09-04T09:30:00Z", "Seller approved handoff"),
        ],
    )
    return {order.order_id: order}


def make_handler(workflow: OrderHandoff) -> type[BaseHTTPRequestHandler]:
    class HandoffHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            routes: dict[str, tuple[type[Any], Any]] = {
                "/login/code": (StartLoginRequest, workflow.start_login),
                "/login/verify": (VerifyLoginRequest, workflow.verify_and_handoff),
            }
            route = routes.get(self.path)
            if route is None:
                self._reply(404, {"error": "route not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("request body must be an object")
                result = route[1](parse_model(route[0], body))
                self._reply(200, result)
            except (ValueError, json.JSONDecodeError) as exc:
                self._reply(400, {"error": str(exc)})
            except LookupError as exc:
                self._reply(404, {"error": str(exc)})
            except InfraiError as exc:
                status = exc.status if 400 <= exc.status < 500 else 502
                self._reply(status, {"error": exc.code})
            except RuntimeError:
                self._reply(502, {"error": "upstream transport error"})

        def _reply(self, status: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return HandoffHandler


def main() -> None:
    workflow = OrderHandoff(InfraiSmsClient(), sample_orders())
    server = ThreadingHTTPServer(("127.0.0.1", 8080), make_handler(workflow))
    print("marketplace handoff service listening on http://127.0.0.1:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
