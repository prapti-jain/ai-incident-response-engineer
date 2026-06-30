import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cors_setup import configure_cors
from failure_state import FailureMode, failure_state
from logging_utils import log_event

SERVICE_NAME = "service-b"
TRACE_HEADER = "X-Trace-Id"


class InjectRequest(BaseModel):
    mode: FailureMode
    magnitude: int = Field(ge=0)


app = FastAPI(title="service-b")
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


@app.get("/work")
async def work(request: Request):
    trace_id = request.state.trace_id

    try:
        failure_state.apply()
    except RuntimeError as exc:
        log_event(
            service=SERVICE_NAME,
            trace_id=trace_id,
            level="error",
            message=str(exc),
            duration_ms=None,
            failure_mode=failure_state.mode,
            magnitude=failure_state.magnitude,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Injected worker failure",
                "trace_id": trace_id,
                "mode": failure_state.mode,
            },
        )

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "trace_id": trace_id,
        "failure_mode": failure_state.mode,
        "magnitude": failure_state.magnitude,
    }


@app.post("/admin/inject")
async def inject(payload: InjectRequest, request: Request):
    failure_state.set(payload.mode, payload.magnitude)
    log_event(
        service=SERVICE_NAME,
        trace_id=request.state.trace_id,
        level="info",
        message="Failure mode updated",
        duration_ms=None,
        failure_mode=failure_state.mode,
        magnitude=failure_state.magnitude,
    )
    return {
        "mode": failure_state.mode,
        "magnitude": failure_state.magnitude,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_NAME}
