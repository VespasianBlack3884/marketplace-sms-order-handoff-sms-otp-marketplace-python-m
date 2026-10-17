from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SellerAsset:
    label: str
    delivery_url: str


@dataclass(frozen=True)
class BuyerUpdate:
    occurred_at: str
    summary: str


@dataclass(frozen=True)
class MarketplaceOrder:
    order_id: str
    buyer_phone: str
    seller_assets: list[SellerAsset]
    buyer_updates: list[BuyerUpdate]


@dataclass(frozen=True)
class StartLoginRequest:
    order_id: str
    phone: str
    idempotency_key: str


@dataclass(frozen=True)
class VerifyLoginRequest:
    order_id: str
    phone: str
    code: str
    idempotency_key: str


class OrderHandoff:
    def __init__(self, sms: Any, orders: dict[str, MarketplaceOrder]) -> None:
        self.sms = sms
        self.orders = orders

    def start_login(self, request: StartLoginRequest) -> dict[str, str]:
        self._owned_order(request.order_id, request.phone)
        self.sms.request_otp(request.phone, request.idempotency_key)
        return {"order_id": request.order_id, "state": "code_sent"}

    def verify_and_handoff(self, request: VerifyLoginRequest) -> dict[str, Any]:
        order = self._owned_order(request.order_id, request.phone)
        result = self.sms.verify_otp(
            request.phone, request.code, request.idempotency_key
        )
        if result.get("verified") is not True:
            return {"order_id": order.order_id, "state": "verification_pending"}
        return {
            "order_id": order.order_id,
            "state": "handed_off",
            "seller_assets": [asdict(asset) for asset in order.seller_assets],
            "buyer_updates": [asdict(update) for update in order.buyer_updates],
        }

    def _owned_order(self, order_id: str, phone: str) -> MarketplaceOrder:
        order = self.orders.get(order_id)
        if order is None or order.buyer_phone != phone:
            raise LookupError("order does not match this buyer")
        return order
