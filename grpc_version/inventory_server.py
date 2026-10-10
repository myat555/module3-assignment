import os
import time
from concurrent import futures

import grpc

import inventory_pb2
import inventory_pb2_grpc

INVENTORY = {"apple": 10, "banana": 5, "laptop": 2}
DELAY_SECONDS = float(os.getenv("INVENTORY_DELAY_SECONDS", "0"))
PORT = os.getenv("INVENTORY_GRPC_PORT", "50052")


class InventoryService(inventory_pb2_grpc.InventoryServiceServicer):
    def CheckInventory(self, request, context):
        if DELAY_SECONDS > 0:
            time.sleep(DELAY_SECONDS)

        if not request.item_id or request.quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "item_id and a positive quantity are required")

        if request.item_id not in INVENTORY:
            context.abort(grpc.StatusCode.NOT_FOUND, f"item '{request.item_id}' not found")

        available = INVENTORY[request.item_id]
        if available < request.quantity:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION,
                          f"insufficient stock: requested {request.quantity}, available {available}")

        return inventory_pb2.CheckInventoryResponse(
            item_id=request.item_id,
            requested=request.quantity,
            available=available,
            in_stock=True,
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryService(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"gRPC Inventory Service listening on :{PORT} (delay={DELAY_SECONDS}s)", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
