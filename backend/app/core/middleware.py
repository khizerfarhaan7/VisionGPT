import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import VisionGPTError

logger = logging.getLogger("visiongpt.requests")


class InProcessRateLimiter:
    """
    Lightweight, in-process rate limiter for VisionGPT.
    Tracks client IP request timestamps in memory using a sliding window algorithm.
    Periodically purges expired entries to prevent memory leaks.
    Does NOT store request bodies, uploaded files, API keys, or user credentials.
    """
    _hits: Dict[str, List[float]] = defaultdict(list)

    @classmethod
    def is_rate_limited(cls, client_ip: str) -> bool:
        if not getattr(settings, "SECURITY_RATE_LIMIT_ENABLED", True):
            return False

        now = time.time()
        window = getattr(settings, "SECURITY_RATE_LIMIT_WINDOW_SECONDS", 60)
        max_requests = getattr(settings, "SECURITY_RATE_LIMIT_REQUESTS", 100)

        # Filter out expired timestamps for client_ip
        cls._hits[client_ip] = [t for t in cls._hits[client_ip] if now - t < window]

        if len(cls._hits[client_ip]) >= max_requests:
            return True

        cls._hits[client_ip].append(now)

        # Bounded memory cleanup
        if len(cls._hits) > 2000:
            for ip in list(cls._hits.keys()):
                cls._hits[ip] = [t for t in cls._hits[ip] if now - t < window]
                if not cls._hits[ip]:
                    del cls._hits[ip]

        return False

    @classmethod
    def reset(cls) -> None:
        """
        Resets rate limiter state (useful for test isolation).
        """
        cls._hits.clear()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured Request Logging, Correlation ID, Payload Size Protection, Security Headers, and Rate Limiting Middleware.
    - Generates/propagates 'X-Request-ID' across HTTP requests & responses.
    - Injects production security headers (nosniff, DENY, Referrer-Policy).
    - Enforces HTTP 413 Payload Too Large protection based on Content-Length.
    - Enforces HTTP 429 Rate Limiting protection.
    - Strictly protects privacy: NEVER logs request/response body contents or Authorization secrets.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        # Extract existing or generate new UUID request_id
        req_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        if not req_id or len(req_id.strip()) == 0:
            req_id = str(uuid.uuid4())

        request.state.request_id = req_id
        start_time = time.time()

        # 1. Request Payload Size Protection (HTTP 413)
        content_length_str = request.headers.get("content-length")
        if content_length_str:
            try:
                content_length = int(content_length_str)
                max_bytes = getattr(settings, "MAX_UPLOAD_SIZE_MB", 100) * 1024 * 1024
                if content_length > max_bytes:
                    logger.warning(
                        f"HTTP 413 Payload Too Large ({content_length} bytes > {max_bytes} bytes) "
                        f"on '{request.url.path}' [Request-ID: {req_id}]"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "success": False,
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request payload size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                                "request_id": req_id
                            }
                        },
                        headers={"X-Request-ID": req_id}
                    )
            except ValueError:
                pass

        # 2. Rate Limiting Protection (HTTP 429)
        client_ip = request.client.host if request.client else "127.0.0.1"
        if InProcessRateLimiter.is_rate_limited(client_ip):
            logger.warning(
                f"HTTP 429 Rate Limit Exceeded for IP '{client_ip}' on '{request.url.path}' "
                f"[Request-ID: {req_id}]"
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": {
                        "code": "TOO_MANY_REQUESTS",
                        "message": "Rate limit exceeded. Please try again later.",
                        "request_id": req_id
                    }
                },
                headers={"X-Request-ID": req_id}
            )

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            # Inject Correlation ID & Security Headers
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Record HTTP request metrics
            from app.services.metrics_service import MetricsService
            MetricsService.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms
            )

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
        headers={
            "X-Request-ID": req_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    req_id = get_request_id(request)
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
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
        headers={
            "X-Request-ID": req_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
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
        headers={
            "X-Request-ID": req_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
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
        headers={
            "X-Request-ID": req_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
    )


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
