# Module 3 Assignment

Two services, implemented twice:

- **Order Service** – accepts an order (`item_id`, `quantity`) on `POST /orders`.
- **Inventory Service** – checks whether the item exists and has enough stock.

The Order → Inventory call is implemented once with **REST/JSON** and once with **gRPC**. Both Order Services expose the same HTTP API, so the only difference is how they talk to Inventory.


## Setup

Python 3.10+.

```bash
python -m venv .venv
source .venv/Scripts/activate
# For Windows
.venv/Scripts/activate
pip install -r requirements.txt
```

## Running the REST version

Two terminals, from the project root:

```bash
python REST/inventory_service.py     # http://127.0.0.1:5001
python REST/order_service.py         # http://127.0.0.1:8000
```

Place an order:

```bash
curl -i -X POST http://127.0.0.1:8000/orders -H "Content-Type: application/json" -d '{"item_id":"apple","quantity":3}'
```

## Running the gRPC version

The generated stubs are committed. To regenerate them after editing the `.proto`:

```bash
python -m grpc_tools.protoc -I proto --python_out=grpc_version --grpc_python_out=grpc_version proto/inventory.proto
```

Two terminals, from inside `grpc_version/`:

```bash
cd grpc_version
python inventory_server.py           # gRPC on :50052
```

```bash
cd grpc_version
python order_service.py              # http://127.0.0.1:8001
```

Place an order (Order Service calls Inventory over gRPC):

```bash
curl -i -X POST http://127.0.0.1:8001/orders -H "Content-Type: application/json" -d '{"item_id":"apple","quantity":3}'
```

Or call the gRPC Inventory Service directly:

```bash
python client.py apple 3             # args: item_id quantity [deadline_seconds]
```

### Configuration

| Variable | Default | Used by |
|---|---|---|
| `INVENTORY_DELAY_SECONDS` | `0` | Both Inventory Services – artificial delay per request |
| `INVENTORY_TIMEOUT_SECONDS` | `2` | REST Order Service – HTTP timeout |
| `INVENTORY_DEADLINE_SECONDS` | `2` | gRPC Order Service – gRPC deadline |
| `INVENTORY_PORT` / `ORDER_PORT` | `5001` / `8000` (REST), `8001` (gRPC) | Listening ports |
| `INVENTORY_GRPC_PORT` / `INVENTORY_GRPC_ADDR` | `50052` / `localhost:50052` | gRPC server / clients |

> Had to use port 50052 for gRPC instead of the usual 50051 because of Multipass.


---

## Evidence

### Successful REST request and response

Order Service → Inventory Service over HTTP/JSON:

```text
$ curl -i -X POST http://127.0.0.1:8000/orders -H "Content-Type: application/json" -d '{"item_id":"apple","quantity":3}'
HTTP/1.1 201 CREATED
Server: Werkzeug/3.1.9 Python/3.13.15
Content-Type: application/json
Content-Length: 105

{"inventory":{"available":10,"in_stock":true,"item_id":"apple","requested":3},"status":"order accepted"}

real	0m0.083s
```

The underlying REST inventory call on its own:

```text
$ curl -i -X POST http://127.0.0.1:5001/inventory/check -H "Content-Type: application/json" -d '{"item_id":"apple","quantity":3}'
HTTP/1.1 200 OK
Content-Type: application/json

{"available":10,"in_stock":true,"item_id":"apple","requested":3}
```

Rejections use matching HTTP status codes:

```text
{"item_id":"laptop","quantity":99}  ->  HTTP/1.1 409 CONFLICT
{"inventory":{"available":2,"error":"insufficient stock","item_id":"laptop","requested":99},"status":"order rejected"}

{"item_id":"pear","quantity":1}     ->  HTTP/1.1 404 NOT FOUND
{"inventory":{"error":"item 'pear' not found"},"status":"order rejected"}

{"item_id":"apple","quantity":0}    ->  HTTP/1.1 400 BAD REQUEST
{"inventory":{"error":"item_id (string) and quantity (positive int) are required"},"status":"order rejected"}
```

### Successful gRPC request and response

Direct `CheckInventory` RPC:

```text
$ python client.py apple 3
CheckInventory request (deadline=2.0s):
item_id: "apple"
quantity: 3

Response: OK
item_id: "apple"
requested: 3
available: 10
in_stock: true
```

Through the gRPC-backed Order Service:

```text
$ curl -i -X POST http://127.0.0.1:8001/orders -H "Content-Type: application/json" -d '{"item_id":"apple","quantity":3}'
HTTP/1.1 201 CREATED
Content-Type: application/json

{"inventory":{"available":10,"in_stock":true,"item_id":"apple","requested":3},"status":"order accepted"}
```

Unavailable items return gRPC status codes:

```text
$ python client.py laptop 99
Response: FAILED_PRECONDITION: insufficient stock: requested 99, available 2

$ python client.py pear 1
Response: NOT_FOUND: item 'pear' not found
```

…which the Order Service maps to HTTP:

```text
HTTP/1.1 409 CONFLICT
{"detail":"insufficient stock: requested 99, available 2","grpc_code":"FAILED_PRECONDITION","status":"order rejected"}

HTTP/1.1 404 NOT FOUND
{"detail":"item 'pear' not found","grpc_code":"NOT_FOUND","status":"order rejected"}
```

### REST timeout handling

Inventory restarted with a 5 s delay (timeout is 2 s):

```bash
INVENTORY_DELAY_SECONDS=5 python REST/inventory_service.py
```

```text
$ time curl -i -X POST http://127.0.0.1:8000/orders -H "Content-Type: application/json" -d '{"item_id":"apple","quantity":1}'
HTTP/1.1 504 GATEWAY TIMEOUT
Content-Type: application/json

{"error":"inventory service timed out after 2.0s"}

real	0m2.086s
```

The Order Service gave up after ~2 s (not 5 s), caught `requests.exceptions.Timeout`, and returned a clean `504`.

### gRPC deadline handling

Inventory restarted with a 5 s delay (deadline is 2 s):

```bash
INVENTORY_DELAY_SECONDS=5 python inventory_server.py
```

```text
$ time curl -i -X POST http://127.0.0.1:8001/orders -H "Content-Type: application/json" -d '{"item_id":"apple","quantity":1}'
HTTP/1.1 504 GATEWAY TIMEOUT
Content-Type: application/json

{"detail":"Deadline Exceeded","grpc_code":"DEADLINE_EXCEEDED","status":"error"}

real    0m2.185s

```

Direct RPC with the same deadline:

```text
$ time python client.py apple 1
CheckInventory request (deadline=2.0s):
item_id: "apple"
quantity: 1

Response: DEADLINE_EXCEEDED: Deadline Exceeded

real    0m2.422s

```

### Order Service remains running after the failures

Immediately after each timeout, the same Order Service process still answers health checks, and orders succeed again once Inventory is restarted without the delay. Restarting the inventory service shows this after ending the 5s delay timeout.

**REST Order Service** (health check right after the timeout, then a new order):

```text
$ curl -i http://127.0.0.1:8000/health
HTTP/1.1 200 OK
{"status":"ok"}

$ curl -i -X POST http://127.0.0.1:8000/orders -H "Content-Type: application/json" -d '{"item_id":"banana","quantity":2}'
HTTP/1.1 201 CREATED
{"inventory":{"available":5,"in_stock":true,"item_id":"banana","requested":2},"status":"order accepted"}
```

REST Order Service log (single process, no restart):

```text
 * Running on http://127.0.0.1:8000
127.0.0.1 - - [08/Oct/2026 16:21:55] "POST /orders HTTP/1.1" 201 -
127.0.0.1 - - [08/Oct/2026 16:21:55] "POST /orders HTTP/1.1" 409 -
[2026-10-08 16:22:11,883] WARNING in order_service: inventory call exceeded 2.0s timeout
127.0.0.1 - - [08/Oct/2026 16:22:11] "POST /orders HTTP/1.1" 504 -
127.0.0.1 - - [08/Oct/2026 16:22:11] "GET /health HTTP/1.1" 200 -
127.0.0.1 - - [08/Oct/2026 16:22:16] "POST /orders HTTP/1.1" 201 -
```

**gRPC Order Service:**

```text
$ curl -i http://127.0.0.1:8001/health
HTTP/1.1 200 OK
{"status":"ok"}

$ curl -i -X POST http://127.0.0.1:8001/orders -H "Content-Type: application/json" -d '{"item_id":"banana","quantity":2}'
HTTP/1.1 201 CREATED
{"inventory":{"available":5,"in_stock":true,"item_id":"banana","requested":2},"status":"order accepted"}
```

gRPC Order Service log (single process, running across the failure):

```text
 * Running on http://127.0.0.1:8001
127.0.0.1 - - [08/Oct/2026 16:11:43] "POST /orders HTTP/1.1" 201 -
127.0.0.1 - - [08/Oct/2026 16:11:43] "POST /orders HTTP/1.1" 409 -
127.0.0.1 - - [08/Oct/2026 16:11:43] "POST /orders HTTP/1.1" 404 -
[2026-10-08 16:11:52,977] WARNING in order_service: inventory call exceeded 2.0s deadline
127.0.0.1 - - [08/Oct/2026 16:11:52] "POST /orders HTTP/1.1" 504 -
127.0.0.1 - - [08/Oct/2026 16:11:53] "GET /health HTTP/1.1" 200 -
127.0.0.1 - - [08/Oct/2026 16:22:30] "POST /orders HTTP/1.1" 201 -
```

Both Order Services stay up because the timeout/deadline errors are caught inside the request handler (`requests.exceptions.Timeout` and `grpc.RpcError`) and turned into a normal HTTP response, and Flask's threaded server keeps serving other requests while one is waiting.

---

## REST vs. gRPC comparison

With REST, the contract lived only in code and documentation: I had to pick a URL and method, validate JSON types by hand in the Inventory Service, and choose which HTTP status codes meant "not found" or "insufficient stock". With gRPC, the `.proto` file was the single source of truth, the generated stubs gave typed request/response objects, and field types were enforced automatically, but it added a code-generation step and generated files to keep in sync. Error handling also felt different: REST maps outcomes onto general-purpose HTTP status codes (404, 409, 504), while gRPC has its own status codes (`NOT_FOUND`, `FAILED_PRECONDITION`, `DEADLINE_EXCEEDED`) that the Order Service had to translate back to HTTP for its own clients. Timeouts are configured per call in both, but a gRPC deadline is part of the RPC itself and is sent to the server, while the REST timeout is purely a client-side `requests` setting.
