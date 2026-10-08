import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:5001/inventory/check")
TIMEOUT_SECONDS = float(os.getenv("INVENTORY_TIMEOUT_SECONDS", "2"))


@app.post("/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    payload = {"item_id": body.get("item_id"), "quantity": body.get("quantity")}

    try:
        resp = requests.post(INVENTORY_URL, json=payload, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        return jsonify(error=f"inventory service timed out after {TIMEOUT_SECONDS}s"), 504
    except requests.exceptions.ConnectionError:
        return jsonify(error="inventory service unavailable"), 503

    if resp.status_code == 200:
        return jsonify(status="order accepted", inventory=resp.json()), 201
    if resp.status_code in (400, 404, 409):
        return jsonify(status="order rejected", inventory=resp.json()), resp.status_code
    return jsonify(error="unexpected inventory response", upstream_status=resp.status_code), 502


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    app.run(port=8000, threaded=True)