"""
LLM Request/Response Logger

This module provides comprehensive logging for all LLM API interactions.
It captures:
- Shortened request data (prompts, configs)
- Full response data
- Timing and performance metrics
- Token usage (when available)
- Error tracking

Usage:
    from app.core.llm_logger import LLMLogger
    
    llm_logger = LLMLogger()
    
    # Before making LLM call
    request_id = llm_logger.log_request(
        model="gemini-2.5-flash",
        prompt="Your prompt here",
        config={"temperature": 0.7}
    )
    
    # After receiving response
    llm_logger.log_response(
        request_id=request_id,
        response="LLM response text",
        metadata={"tokens": 150}
    )
"""

import logging
import json
import time
from typing import Any, Dict, Optional, Union, List
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
import uuid

from .logging import get_logger, StructuredFormatter


class LLMHumanFormatter(logging.Formatter):
    """Human-readable formatter for LLM interactions"""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "extra_data"):
            return super().format(record)

        data = record.extra_data
        event = data.get("event", "unknown")
        model = data.get("model", "unknown")
        timestamp = data.get("timestamp", "unknown")
        request_id = data.get("request_id", "unknown")

        # Extract context if available
        context_items = []
        if "job_id" in data:
            context_items.append(f"Job: {data['job_id']}")
        if "section_index" in data:
            context_items.append(f"Section: {data['section_index']}")
        if "stage" in data:
            context_items.append(f"Stage: {data['stage']}")
        
        context_str = " | ".join(context_items) if context_items else "No context"

        parts = [
            "\n" + "=" * 80,
            f"LLM {event.upper()} | {timestamp}",
            f"Model: {model} | ID: {request_id}",
            f"Context: {context_str}",
            "-" * 80,
        ]

        if event == "llm_request":
            if data.get("system_instruction"):
                parts.append("SYSTEM INSTRUCTION:")
                parts.append(data["system_instruction"])
                parts.append("-" * 40)
            
            parts.append("PROMPT:")
            parts.append(data.get("prompt", ""))
            
            if data.get("config"):
                parts.append("-" * 40)
                parts.append(f"CONFIG: {json.dumps(data['config'], indent=2)}")
            
            if data.get("tools"):
                parts.append(f"TOOLS: {', '.join(data['tools'])}")

        elif event == "llm_response":
            duration = data.get("duration_seconds", 0)
            success = data.get("success", False)
            parts.append(f"STATUS: {'SUCCESS' if success else 'FAILED'} | DURATION: {duration}s")
            
            if not success and data.get("error"):
                parts.append(f"ERROR: {data['error']}")
            
            parts.append("-" * 40)
            parts.append("RESPONSE:")
            parts.append(data.get("response_text", ""))
            
            if data.get("metadata"):
                parts.append("-" * 40)
                parts.append(f"METADATA: {json.dumps(data['metadata'], indent=2)}")

        parts.append("=" * 80 + "\n")
        return "\n".join(parts)


@dataclass
class LLMRequest:
    """Represents an LLM request"""
    request_id: str
    timestamp: str
    model: str
    prompt: str  # Shortened version
    prompt_length: int  # Full length
    config: Dict[str, Any]
    system_instruction: Optional[str] = None
    tools: Optional[List[str]] = None  # Tool names only


@dataclass
class LLMResponse:
    """Represents an LLM response"""
    request_id: str
    timestamp: str
    response_text: str
    duration_seconds: float
    success: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMLogger:
    """
    Logger for LLM API requests and responses.
    
    Features:
    - Automatic request/response correlation
    - Configurable prompt truncation
    - Separate log files for LLM interactions
    - Integration with existing logging infrastructure
    """
    
    def __init__(
        self,
        max_prompt_length: int = 500,
        max_response_length: Optional[int] = None,
        max_system_length: int = 500,
        log_file: Optional[Path] = None,
        full_log_file: Optional[Path] = None,
        console_logging: bool = True
    ):
        """
        Initialize LLM logger.
        
        Args:
            max_prompt_length: Maximum characters to log for prompts (None = unlimited)
            max_response_length: Maximum characters to log for responses (None = unlimited)
            max_system_length: Maximum characters to log for system instructions (None = unlimited)
            log_file: Optional dedicated log file for LLM interactions (truncated)
            full_log_file: Optional dedicated log file for truncated interactions
            console_logging: Whether to log to console as well
        """
        self.max_prompt_length = max_prompt_length
        self.max_response_length = max_response_length
        self.max_system_length = max_system_length
        self.console_logging = console_logging
        
        # Set up logger
        self.logger = get_logger(__name__, component="llm_logger")
        
        # Set up regular truncated file logging if requested
        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            
            from .logging import StructuredFormatter
            file_handler.setFormatter(StructuredFormatter())
            
            # Use a specific logger for truncated logs to avoid propagation issues
            self.truncated_logger = logging.getLogger(f"{__name__}.truncated")
            self.truncated_logger.setLevel(logging.INFO)
            self.truncated_logger.addHandler(file_handler)
            self.truncated_logger.propagate = False
        else:
            self.truncated_logger = None

        # Set up full untruncated file logging if requested
        if full_log_file:
            full_log_file = Path(full_log_file)
            full_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            full_file_handler = logging.FileHandler(full_log_file, encoding="utf-8")
            full_file_handler.setLevel(logging.INFO)
            
            full_file_handler.setFormatter(LLMHumanFormatter())
            
            self.full_logger = logging.getLogger(f"{__name__}.full")
            self.full_logger.setLevel(logging.INFO)
            self.full_logger.addHandler(full_file_handler)
            self.full_logger.propagate = False
        else:
            self.full_logger = None
        
        # Track active requests for timing
        self._active_requests: Dict[str, float] = {}
    
    def _truncate_text(self, text: Optional[str], max_length: Optional[int]) -> str:
        """Truncate text to specified length"""
        if text is None:
            return ""
        if max_length is None or len(text) <= max_length:
            return text
        return text[:max_length] + f"... [truncated, total: {len(text)} chars]"
    
    def _extract_prompt_text(self, contents: Union[str, List[Any]]) -> str:
        """Extract text from various content formats"""
        if isinstance(contents, str):
            return contents
        
        if isinstance(contents, list):
            parts = []
            for item in contents:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    # Handle dict-like content parts
                    if "text" in item and item["text"] is not None:
                        parts.append(item["text"])
                    elif "parts" in item:
                        for part in item["parts"]:
                            if isinstance(part, str):
                                parts.append(part)
                            elif isinstance(part, dict) and "text" in part and part["text"] is not None:
                                parts.append(part["text"])
                elif hasattr(item, "text"):
                    # Handle object-like content parts
                    if item.text is not None:
                        parts.append(item.text)
                elif hasattr(item, "parts"):
                    for part in item.parts:
                        if hasattr(part, "text") and part.text is not None:
                            parts.append(part.text)
            return "\n".join(parts)
        
        # Fallback: convert to string
        return str(contents)
    
    def _extract_tools_info(self, tools: Optional[List[Any]]) -> Optional[List[str]]:
        """Extract tool names from tools list"""
        if not tools:
            return None
        
        tool_names = []
        for tool in tools:
            if isinstance(tool, dict):
                # Function declarations
                if "function_declarations" in tool:
                    for func in tool["function_declarations"]:
                        name = func.get("name", "unknown")
                        tool_names.append(name)
                elif "name" in tool:
                    tool_names.append(tool["name"])
            elif hasattr(tool, "name"):
                tool_names.append(tool.name)
            else:
                tool_names.append(str(type(tool).__name__))
        
        return tool_names if tool_names else None
    
    def log_request(
        self,
        model: str,
        contents: Union[str, List[Any]],
        config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Any]] = None,
        system_instruction: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an LLM request.
        
        Args:
            model: Model name
            contents: Request contents (prompt)
            config: Generation configuration
            tools: Tools/functions available
            system_instruction: System instruction if any
            context: Additional context to log
        
        Returns:
            Request ID for correlation with response
        """
        request_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Extract and truncate prompt
        full_prompt = self._extract_prompt_text(contents)
        truncated_prompt = self._truncate_text(full_prompt, self.max_prompt_length)
        
        # Extract tool names
        tool_names = self._extract_tools_info(tools)
        
        # Extract and truncate system instruction
        full_system = None
        if system_instruction:
            if isinstance(system_instruction, str):
                full_system = system_instruction
            else:
                full_system = self._extract_prompt_text(system_instruction)
        
        truncated_system = self._truncate_text(full_system, self.max_system_length) if full_system else None
        
        # Create truncated request record
        request = LLMRequest(
            request_id=request_id,
            timestamp=timestamp,
            model=model,
            prompt=truncated_prompt,
            prompt_length=len(full_prompt),
            config=config or {},
            system_instruction=truncated_system,
            tools=tool_names
        )
        
        # Store start time for duration calculation
        self._active_requests[request_id] = time.time()
        
        # Prepare log data
        base_log_data = {
            "event": "llm_request",
            **(context or {})
        }
        
        # Log truncated version
        if self.console_logging:
            self.logger.info(
                f"LLM Request | Model: {model} | Prompt: {len(full_prompt)} chars",
                extra={"extra_data": {**base_log_data, **asdict(request)}}
            )
        
        if self.truncated_logger:
            self.truncated_logger.info(
                f"LLM Request | Model: {model}",
                extra={"extra_data": {**base_log_data, **asdict(request)}}
            )
            
        # Log to full logger (uses truncated content from request object)
        if self.full_logger:
            self.full_logger.info(
                f"LLM Request | Model: {model}",
                extra={"extra_data": {**base_log_data, **asdict(request)}}
            )
        
        return request_id
    
    def log_response(
        self,
        request_id: str,
        response: Any,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an LLM response.
        
        Args:
            request_id: Request ID from log_request
            response: Response object or text
            success: Whether the request succeeded
            error: Error message if failed
            metadata: Additional metadata (tokens, etc.)
            context: Additional context to log
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Calculate duration
        duration = 0.0
        if request_id in self._active_requests:
            duration = time.time() - self._active_requests[request_id]
            del self._active_requests[request_id]
        
        # Extract response text
        response_text = ""
        if success and response is not None:
            if isinstance(response, str):
                response_text = response
            elif hasattr(response, "text"):
                # Handle potential None or exception from .text
                try:
                    response_text = response.text or ""
                except Exception:
                    response_text = str(response)
            else:
                response_text = str(response)
        
        # Truncate response if needed FOR CONSOLE/TRUNCATED LOGGERS
        truncated_response = self._truncate_text(
            response_text,
            self.max_response_length
        )
        
        # Create truncated response record for console/truncated loggers
        response_record = LLMResponse(
            request_id=request_id,
            timestamp=timestamp,
            response_text=truncated_response,
            duration_seconds=round(duration, 3),
            success=success,
            error=error,
            metadata=metadata
        )
        
        # Create FULL response record for full logger (no truncation)
        full_response_record = LLMResponse(
            request_id=request_id,
            timestamp=timestamp,
            response_text=response_text,  # FULL text, not truncated
            duration_seconds=round(duration, 3),
            success=success,
            error=error,
            metadata=metadata
        )
        
        # Prepare log data
        base_log_data = {
            "event": "llm_response",
            **(context or {})
        }
        
        level = logging.INFO if success else logging.ERROR
        
        # Log truncated version to console
        if self.console_logging:
            if success:
                self.logger.info(
                    f"LLM Response | Duration: {duration:.2f}s | Length: {len(response_text)} chars",
                    extra={"extra_data": {**base_log_data, **asdict(response_record)}}
                )
            else:
                self.logger.error(
                    f"LLM Error | Duration: {duration:.2f}s | Error: {error}",
                    extra={"extra_data": {**base_log_data, **asdict(response_record)}}
                )
        
        # Log truncated version to file
        if self.truncated_logger:
            self.truncated_logger.log(
                level,
                f"LLM Response | Success: {success}",
                extra={"extra_data": {**base_log_data, **asdict(response_record)}}
            )

        # Log FULL UNTRUNCATED version to full logger
        if self.full_logger:
            self.full_logger.log(
                level,
                f"LLM Response | Success: {success}",
                extra={"extra_data": {**base_log_data, **asdict(full_response_record)}}
            )
    
    def log_error(
        self,
        request_id: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an LLM error.
        
        Args:
            request_id: Request ID from log_request
            error: Exception that occurred
            context: Additional context to log
        """
        self.log_response(
            request_id=request_id,
            response=None,
            success=False,
            error=str(error),
            context=context
        )


# Global singleton instance
_default_logger: Optional[LLMLogger] = None


def get_llm_logger() -> LLMLogger:
    """
    Get the default LLM logger instance.
    
    Configuration via environment variables:
    - LLM_LOG_MAX_PROMPT_LENGTH: Max prompt chars to log (default: 500)
    - LLM_LOG_MAX_RESPONSE_LENGTH: Max response chars to log (default: None/unlimited)
    - LLM_LOG_MAX_SYSTEM_LENGTH: Max system instruction chars to log (default: 500)
    - LLM_LOG_FILE: Path to dedicated LLM log file (default: None)
    - LLM_LOG_FULL_FILE: Path to full log file with truncated content (default: None)
    - LLM_LOG_CONSOLE: Enable console logging (default: true)
    """
    global _default_logger
    
    if _default_logger is None:
        import os
        
        max_prompt = int(os.getenv("LLM_LOG_MAX_PROMPT_LENGTH", "100000"))
        max_response = os.getenv("LLM_LOG_MAX_RESPONSE_LENGTH")
        max_response = int(max_response) if max_response else None
        max_system = int(os.getenv("LLM_LOG_MAX_SYSTEM_LENGTH", "500"))
        
        log_file = os.getenv("LLM_LOG_FILE")
        log_file = Path(log_file) if log_file else None
        
        full_log_file = os.getenv("LLM_LOG_FULL_FILE")
        full_log_file = Path(full_log_file) if full_log_file else None
        
        console = os.getenv("LLM_LOG_CONSOLE", "true").lower() == "true"
        
        _default_logger = LLMLogger(
            max_prompt_length=max_prompt,
            max_response_length=max_response,
            max_system_length=max_system,
            log_file=log_file,
            full_log_file=full_log_file,
            console_logging=console
        )
    
    return _default_logger
