import os
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cors_setup import configure_cors
from logging_utils import log_event

SERVICE_NAME = "service-a"
_default_worker_url = "http://127.0.0.1:8001/work"
_worker_url = os.getenv("WORKER_URL", _default_worker_url).strip()
WORKER_URL = (
    _worker_url
    if _worker_url.endswith("/work")
    else f"{_worker_url.rstrip('/')}/work"
)
TRACE_HEADER = "X-Trace-Id"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="service-a", lifespan=lifespan)
configure_cors(app)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    trace_id = request.headers.get(TRACE_HEADER) or str(uuid.uuid4())
    request.state.trace_id = trace_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        log_event(
            service=SERVICE_NAME,
            trace_id=trace_id,
            level="error",
            message=f"{request.method} {request.url.path} failed: {exc}",
            duration_ms=round(duration_ms, 2),
            emit_metrics=True,
            is_error=True,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    is_error = response.status_code >= 500
    log_event(
        service=SERVICE_NAME,
        trace_id=trace_id,
        level="error" if is_error else "info",
        message=f"{request.method} {request.url.path} -> {response.status_code}",
        duration_ms=round(duration_ms, 2),
        emit_metrics=True,
        is_error=is_error,
    )
    response.headers[TRACE_HEADER] = trace_id
    return response


@app.post("/request")
async def proxy_request(request: Request):
    trace_id = request.state.trace_id
    start = time.perf_counter()

    try:
        response = await request.app.state.http_client.get(
            WORKER_URL,
            headers={TRACE_HEADER: trace_id},
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        log_event(
            service=SERVICE_NAME,
            trace_id=trace_id,
            level="error",
            message=f"Worker returned {exc.response.status_code}",
            duration_ms=round(duration_ms, 2),
        )
        return JSONResponse(
            status_code=exc.response.status_code,
            content={"detail": "Worker request failed", "trace_id": trace_id},
        )
    except httpx.RequestError as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        log_event(
            service=SERVICE_NAME,
            trace_id=trace_id,
            level="error",
            message=f"Worker unreachable: {exc}",
            duration_ms=round(duration_ms, 2),
        )
        return JSONResponse(
            status_code=502,
            content={"detail": "Worker unreachable", "trace_id": trace_id},
        )

    duration_ms = (time.perf_counter() - start) * 1000
    log_event(
        service=SERVICE_NAME,
        trace_id=trace_id,
        level="info",
        message="Worker call completed",
        duration_ms=round(duration_ms, 2),
    )
    return {"trace_id": trace_id, "result": payload}


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_NAME}
