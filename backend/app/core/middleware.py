import logging
import time
import uuid
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import VisionGPTError

logger = logging.getLogger("visiongpt.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured Request Logging & Request Correlation ID Middleware.
    Generates or propagates 'X-Request-ID' across HTTP requests and responses.
    Logs method, path, status_code, duration_ms, and request_id.
    Strictly protects privacy: NEVER logs request/response body contents or Authorization secrets.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        # Extract existing or generate new UUID request_id
        req_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        if not req_id or len(req_id.strip()) == 0:
            req_id = str(uuid.uuid4())

        request.state.request_id = req_id
        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            # Inject X-Request-ID header into response
            response.headers["X-Request-ID"] = req_id

            # Safe structured request logging (NO request bodies, NO secrets)
            logger.info(
                f"HTTP {request.method} '{request.url.path}' -> {response.status_code} "
                f"({duration_ms}ms) [Request-ID: {req_id}]"
            )
            return response
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"HTTP {request.method} '{request.url.path}' -> FAILED ({duration_ms}ms) "
                f"[Request-ID: {req_id}] Error: {exc}",
                exc_info=True
            )
            raise exc


def get_request_id(request: Request) -> str:
    """
    Safely retrieves the request_id attached to request state or headers.
    """
    if hasattr(request.state, "request_id") and request.state.request_id:
        return request.state.request_id
    return request.headers.get("X-Request-ID") or "req_unknown"


def sanitize_error_message(message: str) -> str:
    """
    Sanitizes error strings to ensure secrets, API keys, database URLs, or internal paths are never exposed.
    """
    msg = str(message)
    if "API_KEY" in msg or "key=" in msg or "password=" in msg or "postgres://" in msg or "postgresql://" in msg:
        return "An internal authentication or infrastructure error occurred."
    return msg


async def visiongpt_exception_handler(request: Request, exc: VisionGPTError) -> JSONResponse:
    """
    Handles custom application VisionGPTErrors with machine-readable error codes and request IDs.
    """
    req_id = get_request_id(request)
    body = {
        "success": False,
        "error": {
            "code": exc.code,
            "message": sanitize_error_message(exc.message),
            "details": exc.details if exc.details else None,
            "request_id": req_id
        }
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers={"X-Request-ID": req_id}
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handles standard FastAPI HTTPExceptions while retaining existing error contract compatibility.
    """
    req_id = get_request_id(request)
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR"
    }
    error_code = code_map.get(exc.status_code, "HTTP_ERROR")
    body = {
        "success": False,
        "error": {
            "code": error_code,
            "message": sanitize_error_message(str(exc.detail)),
            "request_id": req_id
        }
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers={"X-Request-ID": req_id}
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handles Pydantic RequestValidationErrors (HTTP 422) with structured field error breakdown.
    """
    req_id = get_request_id(request)
    sanitized_errors = []
    for err in exc.errors():
        loc = " -> ".join([str(loc_item) for loc_item in err.get("loc", [])])
        sanitized_errors.append({
            "field": loc,
            "message": sanitize_error_message(err.get("msg", "Invalid value")),
            "type": err.get("type", "value_error")
        })

    body = {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid request payload or parameters.",
            "details": sanitized_errors,
            "request_id": req_id
        }
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=body,
        headers={"X-Request-ID": req_id}
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global catch-all exception handler for unhandled server errors (HTTP 500).
    Logs traceback server-side and returns a sanitized JSON response with request ID.
    """
    req_id = get_request_id(request)
    logger.error(f"Unhandled Exception on {request.method} '{request.url.path}' [Request-ID: {req_id}]: {exc}", exc_info=True)

    body = {
        "success": False,
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": req_id
        }
    }
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body,
        headers={"X-Request-ID": req_id}
    )


from starlette.exceptions import HTTPException as StarletteHTTPException

def setup_middleware_and_exceptions(app: FastAPI) -> None:
    """
    Registers RequestLoggingMiddleware and global exception handlers on the FastAPI app instance.
    """
    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(VisionGPTError, visiongpt_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
