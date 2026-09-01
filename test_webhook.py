import json
import hmac
import hashlib
import urllib.request

WEBHOOK_SECRET = "test_webhook_secret_123"

payload = {
    "event": "payment.captured",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_test_002",
                "order_id": "order_TWpn8wWnHRyCVG",
                "amount": 659800,
                "currency": "INR",
                "status": "captured",
                "method": "card"
            }
        }
    }
}

raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

signature = hmac.new(
    WEBHOOK_SECRET.encode("utf-8"),
    raw_body,
    hashlib.sha256
).hexdigest()

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/webhooks/razorpay",
    data=raw_body,
    headers={
        "Content-Type": "application/json",
        "x-razorpay-signature": signature
    },
    method="POST"
)

try:
    with urllib.request.urlopen(request) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode())
except Exception as e:
    print("Webhook failed:", e)
