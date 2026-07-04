"""File upload validation utilities.

Validates PDF and document uploads by checking file size, extension,
and MIME type (via magic bytes inspection).
"""
import re

import magic

from app.core.exceptions import PlatformError


class FileTooLargeException(PlatformError):
    """Raised when an uploaded file exceeds the 5MB size limit."""

    def __init__(self) -> None:
        """Initialise with a fixed file-too-large message."""
        super().__init__(
            message="File exceeds the 5MB size limit",
            code="FILE_TOO_LARGE",
            status_code=413,
        )


class InvalidFileTypeException(PlatformError):
    """Raised when an uploaded file has an unsupported extension."""

    def __init__(self) -> None:
        """Initialise with a fixed invalid-file-type message."""
        super().__init__(
            message="Invalid file type. Only PDF files are accepted for CVs",
            code="INVALID_FILE_TYPE",
            status_code=422,
        )


class InvalidFileContentException(PlatformError):
    """Raised when a file's magic bytes do not match its declared extension."""

    def __init__(self) -> None:
        """Initialise with a fixed invalid-content message."""
        super().__init__(
            message="File content does not match the expected type",
            code="INVALID_FILE_CONTENT",
            status_code=422,
        )


MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

ALLOWED_CV_EXTENSIONS = {".pdf"}

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}

ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
}


def validate_pdf_upload(file: bytes, filename: str) -> None:
    """Validate a CV upload. Runs three checks in order, raises on first failure."""

    # 1. Size check
    if len(file) > MAX_FILE_SIZE:
        raise FileTooLargeException()

    # 2. Extension check
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_CV_EXTENSIONS:
        raise InvalidFileTypeException()

    # 3. Magic bytes — confirms actual content, not just the filename
    mime = magic.from_buffer(file[:2048], mime=True)
    if mime != "application/pdf":
        raise InvalidFileContentException()


def validate_document_upload(file: bytes, filename: str) -> None:
    """Validate a supporting document upload."""

    # 1. Size check
    if len(file) > MAX_FILE_SIZE:
        raise FileTooLargeException()

    # 2. Extension check
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise InvalidFileTypeException()

    # 3. Magic bytes check
    mime = magic.from_buffer(file[:2048], mime=True)
    if mime not in ALLOWED_DOCUMENT_MIME_TYPES:
        raise InvalidFileContentException()

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and other issues."""
    name, _, ext = filename.rpartition(".")
    name = re.sub(r"[^\w\-]", "_", name)  # replaces anything not word char or hyphen with _
    name = re.sub(r"_+", "_", name).strip("_")  # collapse multiple underscores
    return f"{name}.{ext.lower()}" if ext else name
