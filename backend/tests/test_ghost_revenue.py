"""Ghost Revenue Hunter webhook, idempotency, and tenant-isolation coverage."""
import hashlib
import hmac
import json
import uuid

from fastapi.testclient import TestClient

from api.main import app
from db import get_connection, save_setting

client = TestClient(app)


def _tenant(label: str):
    suffix = uuid.uuid4().hex[:10]
    response = client.post("/auth/register", json={
        "email": f"ghost-{label}-{suffix}@example.com", "password": "GhostRevenue123!",
        "full_name": f"{label} Owner", "company_name": f"{label} Store",
    })
    assert response.status_code == 200
    return response.json()


def test_unmatched_captured_payment_creates_one_scoped_ghost_incident_without_charge():
    merchant_a = _tenant("a")
    merchant_b = _tenant("b")
    merchant_id = merchant_a["user"]["merchant_id"]
    user_id = merchant_a["user"]["user_id"]
    secret = "ghost-test-secret"
    save_setting("razorpay_webhook_secret", secret, merchant_id=merchant_id)

    payment_id = f"pay_ghost_{uuid.uuid4().hex[:12]}"
    payload = {"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": payment_id, "amount": 54321, "status": "captured", "description": "store checkout"
    }}}}
    body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    webhook_headers = {"x-razorpay-signature": signature, "content-type": "application/json"}

    first = client.post(f"/webhooks/razorpay?merchant_id={merchant_id}", content=body, headers=webhook_headers)
    assert first.status_code == 200
    assert first.json()["status"] == "ghost_revenue_detected"
    incident_id = first.json()["incident_id"]
    repeated = client.post(f"/webhooks/razorpay?merchant_id={merchant_id}", content=body, headers=webhook_headers)
    assert repeated.status_code == 200
    assert repeated.json()["incident_id"] == incident_id

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM ghost_revenue_incidents WHERE merchant_id = ? AND razorpay_payment_id = ?", (merchant_id, payment_id)).fetchone()[0]
        attempts = conn.execute("SELECT COUNT(*) FROM recovery_attempts WHERE recovery_link_payment_id = ?", (payment_id,)).fetchone()[0]
    assert count == 1
    assert attempts == 0  # detection only; no link/charge/retry is created

    headers_a = {"Authorization": f"Bearer {merchant_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {merchant_b['access_token']}"}
    listed_a = client.get("/ghost-revenue/incidents", headers=headers_a)
    assert listed_a.status_code == 200
    assert incident_id in [item["incident_id"] for item in listed_a.json()["incidents"]]
    listed_b = client.get("/ghost-revenue/incidents", headers=headers_b)
    assert listed_b.status_code == 200
    assert incident_id not in [item["incident_id"] for item in listed_b.json()["incidents"]]
    denied = client.post(f"/ghost-revenue/incidents/{incident_id}/resolve", headers=headers_b, json={"resolution": "ESCALATED_FOR_REVIEW"})
    assert denied.status_code == 404