import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from google.genai import errors as genai_errors

logger = logging.getLogger("telemetry.errors")


class AnalyzeError(Exception):
    def __init__(self, message: str, status_code: int = 502, error_type: str = "analyze_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_type": "http_error",
            },
        )

    @app.exception_handler(AnalyzeError)
    async def analyze_error_handler(_request: Request, exc: AnalyzeError) -> JSONResponse:
        logger.error("analyze error: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "error_type": exc.error_type,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception")
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "error_type": type(exc).__name__,
            },
        )


def gemini_client_error_to_analyze_error(exc: genai_errors.ClientError) -> AnalyzeError:
    status = exc.code if exc.code else 502
    message = str(exc)

    if status == 429:
        return AnalyzeError(
            message=(
                "Gemini API rate limit or quota exceeded. "
                "Check your plan/billing at https://ai.google.dev/gemini-api/docs/rate-limits "
                f"or try a different GEMINI_MODEL. Details: {message}"
            ),
            status_code=429,
            error_type="gemini_quota_exceeded",
        )
    if status in (401, 403):
        return AnalyzeError(
            message=f"Gemini API authentication failed. Check GEMINI_API_KEY. Details: {message}",
            status_code=503,
            error_type="gemini_auth_error",
        )
    return AnalyzeError(
        message=f"Gemini API error: {message}",
        status_code=502,
        error_type="gemini_api_error",
    )
