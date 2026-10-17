from marketplace_login.order_handoff import (
    BuyerUpdate,
    MarketplaceOrder,
    OrderHandoff,
    SellerAsset,
    VerifyLoginRequest,
)


class StubSms:
    def __init__(self, verified: bool) -> None:
        self.verified = verified
        self.verify_calls: list[tuple[str, str, str]] = []

    def request_otp(self, phone: str, idempotency_key: str) -> dict[str, object]:
        return {"accepted": True}

    def verify_otp(
        self, phone: str, code: str, idempotency_key: str
    ) -> dict[str, object]:
        self.verify_calls.append((phone, code, idempotency_key))
        return {"verified": self.verified}


def order() -> MarketplaceOrder:
    return MarketplaceOrder(
        order_id="ORD-7",
        buyer_phone="+15551234567",
        seller_assets=[SellerAsset("license", "https://seller.example/license/7")],
        buyer_updates=[BuyerUpdate("2026-09-04T10:00:00Z", "Ready")],
    )


def test_verified_buyer_receives_order_handoff() -> None:
    sms = StubSms(verified=True)
    workflow = OrderHandoff(sms, {"ORD-7": order()})

    result = workflow.verify_and_handoff(
        VerifyLoginRequest("ORD-7", "+15551234567", "481902", "verify-ORD-7-1")
    )

    assert result["state"] == "handed_off"
    assert result["seller_assets"] == [
        {"label": "license", "delivery_url": "https://seller.example/license/7"}
    ]
    assert result["buyer_updates"] == [
        {"occurred_at": "2026-09-04T10:00:00Z", "summary": "Ready"}
    ]
    assert sms.verify_calls == [
        ("+15551234567", "481902", "verify-ORD-7-1")
    ]


def test_unverified_buyer_cannot_receive_assets() -> None:
    workflow = OrderHandoff(StubSms(verified=False), {"ORD-7": order()})

    result = workflow.verify_and_handoff(
        VerifyLoginRequest("ORD-7", "+15551234567", "000000", "verify-ORD-7-2")
    )

    assert result == {"order_id": "ORD-7", "state": "verification_pending"}
    assert "seller_assets" not in result
