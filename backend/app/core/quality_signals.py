"""Data-quality signals: things that are not errors but must not go unnoticed.

A CV that could not be read ran at 21 to 28% for two months before anyone saw it,
because each one was handled quietly. Each such event is logged as one structured
line (``name key=value ...``, easy to search and count) and sent to Sentry as a warning
grouped by ``name``, so Sentry shows ONE issue per kind with its count and rate rather
than a flood of separate issues. Nothing here can fail the caller.
"""

import logging

import sentry_sdk

logger = logging.getLogger(__name__)

# The kinds of signal, so a typo in one place cannot create a silent second kind.
CV_UNREADABLE_PARSE = "cv_unreadable_parse"
SCORE_NOT_SAVED = "score_not_saved"


def report_quality_signal(name: str, *, level: str = "warning", **fields) -> None:
    """Record that ``name`` happened, with ``fields`` saying which and why.

    ``level`` is how loud it is in Sentry: "warning" for data-quality notes, "error"
    for something that stops the product working (it then trips Sentry's default alert
    for new issues).
    """
    try:
        logger.log(
            logging.ERROR if level == "error" else logging.WARNING,
            "%s %s",
            name,
            " ".join(f"{key}={value}" for key, value in sorted(fields.items())),
        )
        with sentry_sdk.new_scope() as scope:
            scope.fingerprint = [name]
            scope.set_context("signal", {key: str(value) for key, value in fields.items()})
            sentry_sdk.capture_message(name, level=level)
    except Exception:  # never let a report break the work it is reporting on
        logger.debug("could not report quality signal %s", name, exc_info=True)
