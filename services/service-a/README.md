# service-a (gateway)

Gateway service that accepts client requests and forwards work to service-b.

## Setup

```bash
cd services/service-a
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Service-b must be running on port 8001 before calling the gateway.

## Endpoints

- `POST /request` — calls service-b `GET /work` and returns the worker result
- `GET /health` — health check

## Example

```bash
curl -X POST http://localhost:8000/request
```

Structured JSON logs are written to stdout for every request, including `trace_id` propagated to service-b via the `X-Trace-Id` header.
