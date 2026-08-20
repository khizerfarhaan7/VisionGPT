from typing import Any, Dict, Optional


class VisionGPTError(Exception):
    """
    Base application exception for VisionGPT.
    Exposes safe user-facing message, machine-readable error code, and HTTP status code.
    Never exposes internal tracebacks or secrets.
    """
    def __init__(
        self,
        message: str = "An application error occurred.",
        code: str = "APPLICATION_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(VisionGPTError):
    def __init__(self, message: str = "The requested resource was not found.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="NOT_FOUND", status_code=404, details=details)


class ValidationError(VisionGPTError):
    def __init__(self, message: str = "Invalid request payload or parameters.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422, details=details)


class AuthenticationError(VisionGPTError):
    def __init__(self, message: str = "Authentication credentials were invalid or missing.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="UNAUTHORIZED", status_code=401, details=details)


class PermissionError(VisionGPTError):
    def __init__(self, message: str = "Permission denied for this resource.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="FORBIDDEN", status_code=403, details=details)


class ResourceBusyError(VisionGPTError):
    def __init__(self, message: str = "The requested resource or AI model is currently busy. Please try again.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="RESOURCE_BUSY", status_code=429, details=details)


class InternalServerError(VisionGPTError):
    def __init__(self, message: str = "An unexpected server error occurred.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="INTERNAL_SERVER_ERROR", status_code=500, details=details)
