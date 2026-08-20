import os
from pathlib import Path
from typing import Set

from app.core.config import settings
from app.core.exceptions import PermissionError, ValidationError

DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".sh", ".bat", ".cmd", ".py", ".js", ".php", ".phtml",
    ".dll", ".so", ".vbs", ".ps1", ".jar", ".cgi", ".pl", ".asp", ".aspx"
}


def sanitize_filename(original_filename: str) -> str:
    """
    Sanitizes user-controlled filename input.
    Strips directory separators, rejects dangerous executable/script extensions,
    and enforces configured ALLOWED_FILE_EXTENSIONS.
    """
    if not original_filename or not original_filename.strip():
        raise ValidationError(message="Filename cannot be empty.")

    # Strip any directory path components
    clean_name = os.path.basename(original_filename.strip())
    clean_name = clean_name.replace("../", "").replace("..\\", "").replace("/", "").replace("\\", "")

    if not clean_name:
        raise ValidationError(message="Filename contains invalid characters.")

    ext = Path(clean_name).suffix.lower()

    # Reject dangerous script/executable extensions
    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError(message=f"Uploaded file extension '{ext}' is prohibited for security reasons.")

    # Validate against allowed extensions
    allowed = [e.lower() for e in settings.ALLOWED_FILE_EXTENSIONS]
    if allowed and ext not in allowed:
        raise ValidationError(
            message=f"File extension '{ext}' is not permitted. Allowed extensions: {', '.join(sorted(allowed))}"
        )

    return clean_name


def validate_safe_path(base_dir: Path, target_path: Path) -> Path:
    """
    Validates that target_path resolves strictly within base_dir.
    Rejects directory traversal attempts (e.g. '../', absolute paths escaping storage).
    """
    base_resolved = base_dir.resolve()
    target_resolved = target_path.resolve()

    try:
        # Check if target is inside base_dir
        target_resolved.relative_to(base_resolved)
    except ValueError:
        raise PermissionError(message="Path traversal attempt blocked: target path escapes designated storage directory.")

    return target_resolved
