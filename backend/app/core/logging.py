"""Structured JSON logging configuration for the Elevare platform."""
import logging
import sys

from pythonjsonlogger import jsonlogger


def setup_logging(debug: bool = False) -> None:
    """Configure the root logger with a JSON formatter.

    In debug mode the log level is set to DEBUG; otherwise INFO.
    SQLAlchemy loggers are redirected to the root handler so all output
    goes through the same JSON formatter.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove default handlers
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Force SQLAlchemy loggers to use the root logger's JSON handler
    # instead of their own plain-text handlers
    for name in ("sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects"):
        sa_logger = logging.getLogger(name)
        sa_logger.handlers.clear()
        sa_logger.propagate = True
