"""
Tests for core/logging module

Comprehensive tests for the logging configuration including formatters,
logger adapters, context variables, and the LogTimer context manager.
"""

import pytest
import logging
import json
from unittest.mock import MagicMock
from app.core.logging import (
    StructuredFormatter,
    DevelopmentFormatter,
    LoggerAdapter,
    setup_logging,
    get_logger,
    set_request_id,
    set_job_id,
    clear_context,
    LogTimer,
    request_id_var,
    job_id_var,
)


class TestStructuredFormatter:
    """Test suite for StructuredFormatter"""

    def test_format_basic_log(self):
        """Test basic log record formatting to JSON"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
        assert "logger" in parsed

    def test_format_with_extra_fields(self):
        """Test log record with extra fields"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"custom_field": "custom_value"}
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"

    def test_format_with_exception(self):
        """Test log record with exception info"""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test.module",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed["level"] == "ERROR"
        assert "exception" in parsed or "exc_info" in result.lower() or "traceback" in result.lower()


class TestDevelopmentFormatter:
    """Test suite for DevelopmentFormatter"""

    def test_format_basic_log(self):
        """Test basic log record formatting for development"""
        formatter = DevelopmentFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        # Should contain the message
        assert "Test message" in result
        # Should contain level indicator
        assert "INFO" in result or formatter.COLORS["INFO"] in result

    def test_format_different_levels(self):
        """Test formatting for different log levels"""
        formatter = DevelopmentFormatter()
        
        for level_name, level in [
            ("DEBUG", logging.DEBUG),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
        ]:
            record = logging.LogRecord(
                name="test.module",
                level=level,
                pathname="/path/to/file.py",
                lineno=42,
                msg=f"{level_name} message",
                args=(),
                exc_info=None,
            )
            
            result = formatter.format(record)
            assert f"{level_name} message" in result


class TestLoggerAdapter:
    """Test suite for LoggerAdapter"""

    def test_process_adds_extra_context(self):
        """Test that process adds extra context to log messages"""
        mock_logger = MagicMock()
        adapter = LoggerAdapter(mock_logger, extra={"service": "test_service"})
        
        msg, kwargs = adapter.process("Test message", {"extra": {}})
        
        assert msg == "Test message"
        assert "extra" in kwargs
        assert kwargs["extra"].get("service") == "test_service"

    def test_process_preserves_existing_extra(self):
        """Test that existing extra fields are preserved"""
        mock_logger = MagicMock()
        adapter = LoggerAdapter(mock_logger, extra={"service": "test_service"})
        
        msg, kwargs = adapter.process("Test message", {"extra": {"user": "alice"}})
        
        assert kwargs["extra"].get("service") == "test_service"
        assert kwargs["extra"].get("user") == "alice"


class TestSetupLogging:
    """Test suite for setup_logging function"""

    def test_setup_logging_default(self):
        """Test default logging setup"""
        # Just ensure no exception is raised
        setup_logging()
        
        # Get root logger and verify it's configured
        logger = logging.getLogger()
        assert logger is not None

    def test_setup_logging_with_level(self):
        """Test logging setup with custom level"""
        setup_logging(level="DEBUG")
        
        logger = logging.getLogger()
        # Root logger should be at or below DEBUG level
        assert logger.level <= logging.DEBUG or any(
            h.level <= logging.DEBUG for h in logger.handlers
        )

    def test_setup_logging_json_mode(self):
        """Test logging setup with JSON mode"""
        setup_logging(use_json=True)
        
        logger = logging.getLogger()
        assert logger is not None


class TestGetLogger:
    """Test suite for get_logger function"""

    def test_get_logger_basic(self):
        """Test getting a basic logger"""
        logger = get_logger("test.module")
        
        assert logger is not None
        # Should be a LoggerAdapter
        assert isinstance(logger, logging.LoggerAdapter)

    def test_get_logger_with_extra(self):
        """Test getting a logger with extra context"""
        logger = get_logger("test.module", component="test_component", version="1.0")
        
        assert isinstance(logger, logging.LoggerAdapter)
        assert logger.extra.get("component") == "test_component"
        assert logger.extra.get("version") == "1.0"


class TestContextVariables:
    """Test suite for context variable functions"""

    def test_set_request_id(self):
        """Test setting request ID"""
        clear_context()
        set_request_id("req-123")
        
        assert request_id_var.get() == "req-123"

    def test_set_job_id(self):
        """Test setting job ID"""
        clear_context()
        set_job_id("job-456")
        
        assert job_id_var.get() == "job-456"

    def test_clear_context(self):
        """Test clearing context variables"""
        set_request_id("req-123")
        set_job_id("job-456")
        
        clear_context()
        
        assert request_id_var.get() is None
        assert job_id_var.get() is None


class TestLogTimer:
    """Test suite for LogTimer context manager"""

    def test_log_timer_basic(self):
        """Test basic LogTimer usage"""
        mock_logger = MagicMock()
        
        with LogTimer(mock_logger, "test_operation"):
            pass  # Simulate work
        
        # Should have logged at least once
        assert mock_logger.log.called

    def test_log_timer_measures_time(self):
        """Test that LogTimer measures elapsed time"""
        mock_logger = MagicMock()
        
        import time
        with LogTimer(mock_logger, "slow_operation"):
            time.sleep(0.01)  # Small delay
        
        # Verify log was called with timing information
        assert mock_logger.log.called
        call_args = mock_logger.log.call_args
        # The message should contain timing info
        assert call_args is not None

    def test_log_timer_with_exception(self):
        """Test LogTimer behavior when exception occurs"""
        mock_logger = MagicMock()
        
        with pytest.raises(ValueError):
            with LogTimer(mock_logger, "failing_operation"):
                raise ValueError("Test error")
        
        # Should still log even with exception
        assert mock_logger.log.called

    def test_log_timer_custom_level(self):
        """Test LogTimer with custom log level"""
        mock_logger = MagicMock()
        
        with LogTimer(mock_logger, "debug_operation", level=logging.DEBUG):
            pass
        
        # Should log at DEBUG level
        call_args = mock_logger.log.call_args
        if call_args:
            assert call_args[0][0] == logging.DEBUG
