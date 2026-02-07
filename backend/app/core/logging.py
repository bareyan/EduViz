"""
Production-grade structured logging configuration
Provides consistent logging across the entire application with:
- Structured JSON logging for production
- Human-readable logs for development
- Request correlation IDs
- Performance tracking
- Error context capture
"""

import logging
import sys
import json
import os
from typing import Any, Dict, Optional
from datetime import datetime, UTC
from contextvars import ContextVar
from pathlib import Path
from logging.handlers import RotatingFileHandler

SENSITIVE_KEY_TOKENS = ("password", "secret", "token", "api_key", "apikey", "authorization")

# Context variable for request correlation
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
job_id_var: ContextVar[Optional[str]] = ContextVar("job_id", default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging in production"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": _sanitize_for_logging("message", record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation IDs
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        job_id = job_id_var.get()
        if job_id:
            log_data["job_id"] = job_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # Add extra fields:
        # - Preserve any explicitly provided `record.extra_data`
        # - Also include any non-standard LogRecord attributes (e.g. from logger.info(..., extra={...}))
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "getMessage",
            "message",
            "taskName",  # Added in Python 3.12
        }

        extra: Dict[str, Any] = {}

        if hasattr(record, "extra_data"):
            extra_data = getattr(record, "extra_data")
            if isinstance(extra_data, dict):
                # Copy to avoid mutating any shared dict
                extra.update(extra_data)

        for key, value in vars(record).items():
            if key in standard_attrs:
                continue
            if key.startswith("_"):
                continue
            if key == "extra_data":
                continue
            if callable(value):
                continue
            if key not in extra:
                extra[key] = value

        if extra:
            log_data["extra"] = _sanitize_for_logging("extra", extra)

        return json.dumps(log_data)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in SENSITIVE_KEY_TOKENS)


def _sanitize_for_logging(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for child_key, child_value in value.items():
            if _is_sensitive_key(str(child_key)):
                sanitized[child_key] = "***REDACTED***"
            else:
                sanitized[child_key] = _sanitize_for_logging(str(child_key), child_value)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_for_logging(key, item) for item in value]

    if isinstance(value, tuple):
        return tuple(_sanitize_for_logging(key, item) for item in value)

    if isinstance(value, str) and _is_sensitive_key(key):
        return "***REDACTED***"

    return value


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]

        # Format correlation IDs
        context_parts = []
        request_id = request_id_var.get()
        if request_id:
            context_parts.append(f"req:{request_id[:8]}")

        job_id = job_id_var.get()
        if job_id:
            context_parts.append(f"job:{job_id[:8]}")

        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        # Build log line
        log_line = (
            f"{color}{timestamp}{reset} "
            f"{color}{record.levelname:8s}{reset} "
            f"{record.name:30s}{context} "
            f"{record.getMessage()}"
        )

        # Add exception if present
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds extra context to all log messages"""

    def process(self, msg: str, kwargs: Any) -> tuple:
        # Add extra data to the log record
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # Add correlation IDs
        request_id = request_id_var.get()
        if request_id:
            kwargs["extra"]["request_id"] = request_id

        job_id = job_id_var.get()
        if job_id:
            kwargs["extra"]["job_id"] = job_id

        # Merge with additional extra data
        if hasattr(self, "extra") and self.extra:
            kwargs["extra"].update(self.extra)

        return msg, kwargs


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    use_json: bool = False,
    pipeline_log_file: Optional[Path] = None
) -> None:
    """
    Configure application logging
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging to file
        use_json: If True, use structured JSON logging; otherwise human-readable
        pipeline_log_file: Optional file path for a separate pipeline log file
    """
    # Convert level string to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    if use_json:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(console_handler)

    # File handler (if specified)
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", str(20 * 1024 * 1024)))
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(StructuredFormatter())  # Always use JSON for file logs
        root_logger.addHandler(file_handler)

    # Separate pipeline log handler (if specified)
    if pipeline_log_file:
        pipeline_log_file.parent.mkdir(parents=True, exist_ok=True)
        pipeline_handler = RotatingFileHandler(
            pipeline_log_file,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        pipeline_handler.setLevel(numeric_level)
        pipeline_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(pipeline_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str, **extra: Any) -> LoggerAdapter:
    """
    Get a logger with optional extra context
    
    Args:
        name: Logger name (usually __name__)
        **extra: Additional context to include in all log messages
    
    Returns:
        LoggerAdapter with the specified context
    
    Example:
        logger = get_logger(__name__, service="video_generator")
        logger.info("Processing video", extra={"section": 5})
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, extra)


def set_request_id(request_id: str) -> None:
    """Set request ID for correlation across log messages"""
    request_id_var.set(request_id)


def set_job_id(job_id: str) -> None:
    """Set job ID for correlation across log messages"""
    job_id_var.set(job_id)


def clear_context() -> None:
    """Clear correlation context"""
    request_id_var.set(None)
    job_id_var.set(None)


# Convenience functions for logging with timing
class LogTimer:
    """Context manager for timing operations with automatic logging"""

    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.INFO):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time: Optional[float] = None

    def __enter__(self) -> "LogTimer":
        self.start_time = datetime.now().timestamp()
        self.logger.log(self.level, f"Starting: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb) -> None:
        duration = datetime.now().timestamp() - self.start_time

        if exc_type:
            self.logger.error(
                f"Failed: {self.operation}",
                extra={"duration_seconds": duration, "error": str(exc_val)},
                exc_info=True
            )
        else:
            self.logger.log(
                self.level,
                f"Completed: {self.operation}",
                extra={"duration_seconds": duration}
            )
