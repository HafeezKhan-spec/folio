"""Stripe configuration and the signed webhook that unlocks Pro."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from helpers import signup


def _sign(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed = f"{timestamp}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_billing_explains_missing_stripe_settings(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("STRIPE_PRICE_ID", "")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "")
    signup(client, "pay@example.com")
    response = client.get("/api/billing")
    assert response.status_code == 200
    body = response.json()
    assert body["price_label"] == "$2.99/month"
    assert body["plan"] == "free"
    assert body["checkout_available"] is False
    assert body["missing"] == [
        "STRIPE_SECRET_KEY",
        "STRIPE_PRICE_ID",
        "STRIPE_WEBHOOK_SECRET",
    ]
    checkout = client.post("/api/billing/checkout")
    assert checkout.status_code == 503
    assert "STRIPE_SECRET_KEY" in checkout.json()["detail"]
    assert "STRIPE_PRICE_ID" in checkout.json()["detail"]
    webhook = client.post("/api/billing/webhook", content=b"{}", headers={})
    assert webhook.status_code == 503
    assert "STRIPE_WEBHOOK_SECRET" in webhook.json()["detail"]


def test_signed_webhook_sets_pro(client, monkeypatch):
    secret = "whsec_test_secret"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    created = signup(client, "pay@example.com")
    assert created.json()["plan"] == "free"
    user_id = created.json()["id"]
    payload = json.dumps(
        {
            "id": "evt_test_1",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "object": "checkout.session",
                    "client_reference_id": user_id,
                    "metadata": {"user_id": user_id},
                }
            },
        }
    ).encode()
    response = client.post(
        "/api/billing/webhook",
        content=payload,
        headers={
            "stripe-signature": _sign(payload, secret),
            "content-type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/auth/me").json()["plan"] == "pro"
    bad = client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert bad.status_code == 400
