import os

import grpc
from flask import Flask, jsonify, request

import inventory_pb2
import inventory_pb2_grpc

app = Flask(__name__)

INVENTORY_ADDR = os.getenv("INVENTORY_GRPC_ADDR", "localhost:50052")
DEADLINE_SECONDS = float(os.getenv("INVENTORY_DEADLINE_SECONDS", "2"))

channel = grpc.insecure_channel(INVENTORY_ADDR)
stub = inventory_pb2_grpc.InventoryServiceStub(channel)

GRPC_TO_HTTP = {
    grpc.StatusCode.INVALID_ARGUMENT: 400,
    grpc.StatusCode.NOT_FOUND: 404,
    grpc.StatusCode.FAILED_PRECONDITION: 409,
    grpc.StatusCode.UNAVAILABLE: 503,
    grpc.StatusCode.DEADLINE_EXCEEDED: 504,
}
REJECTIONS = {
    grpc.StatusCode.INVALID_ARGUMENT,
    grpc.StatusCode.NOT_FOUND,
    grpc.StatusCode.FAILED_PRECONDITION,
}


@app.post("/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    quantity = body.get("quantity")

    if not isinstance(item_id, str) or not isinstance(quantity, int):
        return jsonify(error="item_id (string) and quantity (int) are required"), 400

    req = inventory_pb2.CheckInventoryRequest(item_id=item_id, quantity=quantity)

    try:
        resp = stub.CheckInventory(req, timeout=DEADLINE_SECONDS)
    except grpc.RpcError as e:
        code = e.code()
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            app.logger.warning("inventory call exceeded %.1fs deadline", DEADLINE_SECONDS)
        status = "order rejected" if code in REJECTIONS else "error"
        return jsonify(status=status, grpc_code=code.name, detail=e.details()), GRPC_TO_HTTP.get(code, 502)

    return jsonify(status="order accepted", inventory={
        "item_id": resp.item_id,
        "requested": resp.requested,
        "available": resp.available,
        "in_stock": resp.in_stock,
    }), 201


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    app.run(port=int(os.getenv("ORDER_PORT", "8001")), threaded=True)
