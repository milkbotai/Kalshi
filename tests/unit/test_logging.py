"""Unit tests for logging configuration."""

import logging

import structlog

from src.shared.config.logging import configure_logging, get_logger


class TestLogging:
    """Test suite for logging configuration."""

    def test_configure_logging_sets_up_structlog(self) -> None:
        """Test that configure_logging sets up structlog correctly."""
        configure_logging()
        
        # Verify structlog is configured
        logger = structlog.get_logger("test")
        assert isinstance(logger, structlog.stdlib.BoundLogger)

    def test_get_logger_returns_bound_logger(self) -> None:
        """Test that get_logger returns a BoundLogger instance."""
        configure_logging()
        logger = get_logger("test_module")
        
        assert isinstance(logger, structlog.stdlib.BoundLogger)

    def test_logger_can_log_messages(self) -> None:
        """Test that logger can log messages without errors."""
        configure_logging()
        logger = get_logger("test_module")
        
        # These should not raise exceptions
        logger.debug("Debug message", key="value")
        logger.info("Info message", count=42)
        logger.warning("Warning message")
        logger.error("Error message", error_code=500)

    def test_logging_level_is_set(self) -> None:
        """Test that logging level is configured."""
        configure_logging()
        
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO  # Default from settings
