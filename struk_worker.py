from flask import Flask, request, jsonify
import requests
import hashlib
import json
import base64
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Config from .env
MIDTRANS_SERVER_KEY = os.getenv("MIDTRANS_SERVER_KEY")
IS_PRODUCTION = os.getenv("MIDTRANS_IS_PRODUCTION", "False").lower() == "true"
LARAVEL_WEBHOOK_URL = os.getenv(
    "LARAVEL_WEBHOOK_URL", "http://localhost:8000/payment/webhook"
)
MIDTRANS_BASE_URL = (
    "https://app.midtrans.com" if IS_PRODUCTION else "https://app.sandbox.midtrans.com"
)

# Logging setup
logging.basicConfig(
    filename="midtrans_proxy.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


@app.route("/")
def index():
    return jsonify({"message": "Midtrans Proxy API is running"})


@app.route("/payment/create-snap-token", methods=["POST"])
def create_snap_token():
    try:
        data = request.json or {}
        if not data.get("order_id") or not data.get("amount"):
            return jsonify({"error": "Missing order_id or amount"}), 400

        auth_str = base64.b64encode(f"{MIDTRANS_SERVER_KEY}:".encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_str}",
        }

        payload = {
            "transaction_details": {
                "order_id": data["order_id"],
                "gross_amount": data["amount"],
            },
            "customer_details": data.get("customer_details", {}),
            "item_details": data.get("item_details", []),
        }

        response = requests.post(
            MIDTRANS_BASE_URL + "/snap/v1/transactions",
            headers=headers,
            json=payload,
            timeout=10,
        )

        logging.info(f"Snap request success: {response.text}")
        return jsonify(response.json()), response.status_code

    except Exception as e:
        logging.exception("Error while creating snap token")
        return jsonify({"error": "Internal Server Error"}), 500


@app.route("/payment/webhook", methods=["POST"])
def midtrans_webhook():
    try:
        data = request.json or {}
        order_id = data.get("order_id")
        status_code = data.get("status_code")
        gross_amount = data.get("gross_amount")
        signature_key = data.get("signature_key")

        if not all([order_id, status_code, gross_amount, signature_key]):
            return jsonify({"error": "Incomplete payload"}), 400

        expected_signature = hashlib.sha512(
            f"{order_id}{status_code}{gross_amount}{MIDTRANS_SERVER_KEY}".encode()
        ).hexdigest()

        if expected_signature != signature_key:
            logging.warning(f"Invalid signature for order {order_id}")
            return jsonify({"message": "Invalid signature"}), 403

        transaction_status = data.get("transaction_status")
        logging.info(
            f"Webhook received for order {order_id}, status: {transaction_status}"
        )

        with open("webhook_log.txt", "a") as f:
            f.write(json.dumps(data) + "\n")

        # Forward to Laravel
        try:
            forward = requests.post(LARAVEL_WEBHOOK_URL, json=data, timeout=5)
            logging.info(f"Forwarded to Laravel: {forward.status_code} {forward.text}")
        except Exception as fw_ex:
            logging.error(f"Failed to forward to Laravel: {fw_ex}")

        return jsonify({"message": "Webhook processed"})

    except Exception as e:
        logging.exception("Error while handling webhook")
        return jsonify({"error": "Internal Server Error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
