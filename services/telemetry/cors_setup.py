import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class PrivateNetworkAccessMiddleware(BaseHTTPMiddleware):
    """Chrome requires this when a page on localhost fetches 127.0.0.1 (or vice versa)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.headers.get("origin"):
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response


def configure_cors(app: FastAPI) -> None:
    app.add_middleware(PrivateNetworkAccessMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
