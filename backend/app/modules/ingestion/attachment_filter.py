"""Attachment filter — the gate before anything hits the CV parsing pipeline.

A message passes the filter only if it has at least one attachment that:
  1. Has an allowed file extension (pdf, docx, doc)
  2. Is within the size limit
  3. Has a MIME type consistent with its extension

This is intentionally strict. It's cheaper to skip borderline emails than
to waste parsing quota on cover-letter-only emails or auto-replies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.modules.ingestion.adapters.base import MailAttachment, MailMessage

logger = logging.getLogger(__name__)

# 10 MB — consistent with existing CV upload validation
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

# Allowed extensions — matches what the CV pipeline supports
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

# Allowed MIME types mapped to extensions
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    # Some mail clients send these generic types for office docs
    "application/octet-stream",
    "binary/octet-stream",
}

# Subject/body keywords that suggest a CV email — used for soft scoring only,
# not hard filtering, to avoid rejecting unusual subject lines.
CV_KEYWORDS = {
    "cv",
    "resume",
    "résumé",
    "curriculum vitae",
    "application",
    "apply",
    "applying",
    "job application",
    "candidate",
}


@dataclass
class FilterResult:
    """Result of running a message through the attachment filter."""

    passed: bool
    cv_attachments: list[MailAttachment]  # attachments that passed
    skip_reason: str = ""  # human-readable if passed=False


def _extension(filename: str) -> str:
    """Return the lowercased file extension including the dot."""
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""


def _looks_like_cv_email(message: MailMessage) -> bool:
    """Soft check — does the subject or body snippet contain CV keywords."""
    text = (message.subject + " " + message.body_snippet).lower()
    return any(kw in text for kw in CV_KEYWORDS)


def filter_message(message: MailMessage) -> FilterResult:
    """Run a MailMessage through all attachment filter rules.

    Returns a FilterResult. Only messages with passing CV attachments
    should be queued into the parsing pipeline.
    """
    if not message.attachments:
        return FilterResult(
            passed=False, cv_attachments=[], skip_reason="no_attachments"
        )

    cv_attachments: list[MailAttachment] = []

    for att in message.attachments:
        ext = _extension(att.filename)

        if ext not in ALLOWED_EXTENSIONS:
            logger.debug(
                "Skipping attachment %s — unsupported extension %s", att.filename, ext
            )
            continue

        if att.size > MAX_ATTACHMENT_BYTES:
            logger.debug(
                "Skipping attachment %s — size %d exceeds limit", att.filename, att.size
            )
            continue

        if att.content_type.lower() not in ALLOWED_MIME_TYPES:
            # Some clients lie about MIME type — still allow if extension matches
            logger.debug(
                "Attachment %s has unexpected MIME type %s but extension is valid — allowing",
                att.filename,
                att.content_type,
            )

        cv_attachments.append(att)

    if not cv_attachments:
        return FilterResult(
            passed=False,
            cv_attachments=[],
            skip_reason="no_valid_cv_attachments",
        )

    return FilterResult(passed=True, cv_attachments=cv_attachments)
