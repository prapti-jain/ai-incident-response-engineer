# service-b (worker)

Worker service that performs work and supports configurable failure injection for testing incident response flows.

## Setup

```bash
cd services/service-b
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Endpoints

- `GET /work` — performs work (subject to injected failure mode)
- `POST /admin/inject` — set in-memory failure injection state
- `GET /health` — health check

## Failure injection

```bash
# Clear failure mode
curl -X POST http://localhost:8001/admin/inject \
  -H "Content-Type: application/json" \
  -d '{"mode": "none", "magnitude": 0}'

# Add latency (sleep magnitude ms before responding)
curl -X POST http://localhost:8001/admin/inject \
  -H "Content-Type: application/json" \
  -d '{"mode": "latency", "magnitude": 500}'

# Return 500 on magnitude percent of requests
curl -X POST http://localhost:8001/admin/inject \
  -H "Content-Type: application/json" \
  -d '{"mode": "error", "magnitude": 50}'

# Busy-loop for magnitude ms
curl -X POST http://localhost:8001/admin/inject \
  -H "Content-Type: application/json" \
  -d '{"mode": "cpu_spike", "magnitude": 200}'
```

Structured JSON logs are written to stdout for every request. When called via service-a, the same `trace_id` appears in both services' logs.
