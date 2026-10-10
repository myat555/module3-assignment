import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)

INVENTORY = {"apple": 10, "banana": 5, "laptop": 2}
DELAY_SECONDS = float(os.getenv("INVENTORY_DELAY_SECONDS", "0"))


@app.post("/inventory/check")
def check_inventory():
    if DELAY_SECONDS > 0:
        time.sleep(DELAY_SECONDS)

    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    quantity = body.get("quantity")

    if not isinstance(item_id, str) or not isinstance(quantity, int) or quantity <= 0:
        return jsonify(error="item_id (string) and quantity (positive int) are required"), 400

    if item_id not in INVENTORY:
        return jsonify(error=f"item '{item_id}' not found"), 404

    available = INVENTORY[item_id]
    if available < quantity:
        return jsonify(error="insufficient stock", item_id=item_id,
                       requested=quantity, available=available), 409

    return jsonify(item_id=item_id, requested=quantity, available=available, in_stock=True), 200


if __name__ == "__main__":
    app.run(port=int(os.getenv("INVENTORY_PORT", "5001")), threaded=True)