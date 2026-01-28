"""Structured logging configuration using structlog.

Provides JSON-formatted logs with context and correlation IDs for
production environments, and human-readable console logs for development.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from src.shared.config.settings import settings


def add_correlation_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add correlation ID to log events if present in context."""
    # Correlation ID will be added by middleware in future stories
    return event_dict


def configure_logging() -> None:
    """Configure structured logging for the application.

    Sets up structlog with appropriate processors based on environment:
    - Production: JSON output with timestamps
    - Development: Console output with colors
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_id,
    ]

    if settings.log_format == "json":
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Console output with colors
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str) -> Any:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
