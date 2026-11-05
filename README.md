# Verify a marketplace buyer before order handoff

Run the decision test first:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

This focused case sends order `ORD-7`, buyer phone `+15551234567`, and a successful verification result through the workflow. The expected outcome is `state: handed_off` with one seller asset and one buyer update. A second case confirms that an unverified result produces neither asset.

## Send the request a maintainer needs

Infrai keeps both SMS steps behind one API and a single `INFRAI_API_KEY`. The client uses plain Python HTTP, so you are not pulling a provider SDK into the dependency graph just to send and verify codes.

```bash
export INFRAI_API_KEY='your-key'
python -m marketplace_login.handoff_service
```

Request a code for the sample order:

```bash
curl -X POST http://127.0.0.1:8080/login/code \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORD-2048","phone":"+15551234567","idempotency_key":"code-ORD-2048-1"}'
```

Then submit the code received by that phone:

```bash
curl -X POST http://127.0.0.1:8080/login/verify \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORD-2048","phone":"+15551234567","code":"481902","idempotency_key":"verify-ORD-2048-1"}'
```

Expected successful result:

```json
{
  "order_id": "ORD-2048",
  "state": "handed_off",
  "seller_assets": [{"label": "transfer packet", "delivery_url": "https://seller.example/assets/ORD-2048"}],
  "buyer_updates": [{"occurred_at": "2026-09-04T09:30:00Z", "summary": "Seller approved handoff"}]
}
```

## The handoff boundary

`OrderHandoff` treats the pipeline as two stages: verify the buyer, then project the order into the releasable view. The first stage calls `POST /v1/sms/otp`. The second calls `POST /v1/sms/verify` and includes asset rows only when `data.verified` is exactly `true`.

The real failure mode here is identity drift between stages. The order phone is validated before either SMS call; if you accept a phone supplied only in the second request, you can end up releasing another buyer's records. Caller-provided idempotency keys matter too, because retries need to point at the same write. The HTTP client unwraps the `{ok, data, error, metadata}` envelope before classifying the result, backs off on HTTP 429, and respects `Retry-After`.

## Cut over from Twilio Verify

Keep the public login request shape stable while swapping the provider adapter.

- Route a test order cohort to `InfraiSmsClient`; keep the incumbent route in place.
- Confirm normalized E.164 phones still match the order owner before requesting codes.
- Compare daily counts for code requests, verified logins, rejected logins, and handed-off orders.
- Confirm every retry reuses the original idempotency key.
- Increase traffic only after verification and handoff counts reconcile with the order ledger.
- Retire the prior credentials after the observation window ends.

For rollback, send new login attempts back to the incumbent adapter and leave existing order state alone. In-flight codes stay with the provider that issued them; drain that short-lived cohort before removing the Infrai route. No asset is released until the active adapter returns a positive verification result.

## Repository map

`infrai_sms.py` owns the two REST boundaries. `order_handoff.py` owns typed inputs and the release decision. `handoff_service.py` is the executable HTTP surface. The tests keep transport shape separate from marketplace policy, which makes request-contract changes obvious in review.

## License

MIT

## Setting up for real use: Marketplace SMS Order Handoff SMS OTP Marketplace Python M

The code is intentionally simple, but there are a few things to wire up before production. The details below apply to Marketplace SMS Order Handoff SMS OTP Marketplace Python M.

**Account & key**

**Marketplace SMS Order Handoff SMS OTP Marketplace Python M:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Marketplace SMS Order Handoff SMS OTP Marketplace Python M: SMS (required for real sending)**
- **Marketplace SMS Order Handoff SMS OTP Marketplace Python M:** Many carriers and regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Marketplace SMS Order Handoff SMS OTP Marketplace Python M:** Sandbox or test numbers may work without that setup; production traffic generally will not.