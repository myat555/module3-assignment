import os
import sys

import grpc

import inventory_pb2
import inventory_pb2_grpc


def main():
    item_id = sys.argv[1] if len(sys.argv) > 1 else "apple"
    quantity = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    deadline = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0

    request = inventory_pb2.CheckInventoryRequest(item_id=item_id, quantity=quantity)
    print(f"CheckInventory request (deadline={deadline}s):\n{request}")

    with grpc.insecure_channel(os.getenv("INVENTORY_GRPC_ADDR", "localhost:50052")) as channel:
        stub = inventory_pb2_grpc.InventoryServiceStub(channel)
        try:
            response = stub.CheckInventory(request, timeout=deadline)
            print(f"Response: OK\n{response}")
        except grpc.RpcError as e:
            print(f"Response: {e.code().name}: {e.details()}")


if __name__ == "__main__":
    main()
