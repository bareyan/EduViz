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
from typing import Any, Dict, Optional, Union, List, Iterator
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
import uuid
from contextvars import ContextVar
from contextlib import contextmanager

from .logging import get_logger


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
        log_file: Optional[Path] = None,
        console_logging: bool = True
    ):
        """
        Initialize LLM logger.
        
        Args:
            max_prompt_length: Maximum characters to log for prompts (None = unlimited)
            max_response_length: Maximum characters to log for responses (None = unlimited)
            log_file: Optional dedicated log file for LLM interactions
            console_logging: Whether to log to console as well
        """
        self.max_prompt_length = max_prompt_length
        self.max_response_length = max_response_length
        self.console_logging = console_logging
        
        # Set up logger
        self.logger = get_logger(__name__, component="llm_logger")
        
        # Set up dedicated file logging if requested
        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            
            # Use JSON formatting for file logs
            from .logging import StructuredFormatter
            file_handler.setFormatter(StructuredFormatter())
            
            # Add handler to this logger
            logging.getLogger(__name__).addHandler(file_handler)
        
        # Track active requests for timing
        self._active_requests: Dict[str, float] = {}

    def _extract_image_metadata(self, contents: Union[str, List[Any]]) -> Dict[str, int]:
        """Extract image metadata from multimodal contents."""
        if not isinstance(contents, list):
            return {"image_count": 0, "image_bytes_total": 0}

        image_count = 0
        image_bytes_total = 0

        for item in contents:
            # Raw bytes
            if isinstance(item, (bytes, bytearray)):
                image_count += 1
                image_bytes_total += len(item)
                continue

            # Dict-like parts
            if isinstance(item, dict):
                mime_type = item.get("mime_type") or item.get("mimeType")
                if mime_type and isinstance(mime_type, str) and mime_type.startswith("image/"):
                    image_count += 1
                    data = item.get("data") or item.get("inline_data")
                    if isinstance(data, (bytes, bytearray)):
                        image_bytes_total += len(data)
                continue

            # Object-like parts
            if hasattr(item, "parts"):
                for part in item.parts:
                    if isinstance(part, (bytes, bytearray)):
                        image_count += 1
                        image_bytes_total += len(part)
                        continue
                    mime_type = getattr(part, "mime_type", None)
                    data = getattr(part, "data", None) or getattr(part, "inline_data", None)
                    if mime_type and isinstance(mime_type, str) and mime_type.startswith("image/"):
                        image_count += 1
                        if isinstance(data, (bytes, bytearray)):
                            image_bytes_total += len(data)
                continue

            data = getattr(item, "data", None) or getattr(item, "inline_data", None)
            mime_type = getattr(item, "mime_type", None)
            if mime_type and isinstance(mime_type, str) and mime_type.startswith("image/"):
                image_count += 1
                if isinstance(data, (bytes, bytearray)):
                    image_bytes_total += len(data)

        return {"image_count": image_count, "image_bytes_total": image_bytes_total}
    
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
                    if "text" in item:
                        if isinstance(item["text"], str):
                            parts.append(item["text"])
                    elif "parts" in item:
                        for part in item["parts"]:
                            if isinstance(part, str):
                                parts.append(part)
                            elif isinstance(part, dict) and "text" in part and isinstance(part["text"], str):
                                parts.append(part["text"])
                elif hasattr(item, "text"):
                    # Handle object-like content parts
                    if isinstance(item.text, str):
                        parts.append(item.text)
                elif hasattr(item, "parts"):
                    for part in item.parts:
                        if hasattr(part, "text") and isinstance(part.text, str):
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
        
        # Truncate system instruction
        truncated_system = None
        full_system_text = None
        if system_instruction:
            if isinstance(system_instruction, str):
                truncated_system = self._truncate_text(system_instruction, 200)
                full_system_text = system_instruction
            else:
                # Try to extract text from object
                sys_text = self._extract_prompt_text(system_instruction)
                truncated_system = self._truncate_text(sys_text, 200)
                full_system_text = sys_text
        
        # Create request record
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
        
        # Log the request
        log_data = {
            "event": "llm_request",
            **asdict(request),
            **(context or {})
        }
        
        if self.console_logging:
            self.logger.info(
                f"LLM Request | Model: {model} | Prompt: {len(full_prompt)} chars",
                extra={"extra_data": log_data}
            )
        else:
            # Still log to file even if console logging is disabled
            logging.getLogger(__name__).info(
                f"LLM Request | Model: {model}",
                extra={"extra_data": log_data}
            )

        # Per-section JSONL logging (full prompt/response)
        section_log_path = llm_section_log_path_var.get()
        if section_log_path:
            image_meta = self._extract_image_metadata(contents)
            section_log_data = {
                "event": "llm_request",
                "request_id": request_id,
                "timestamp": timestamp,
                "model": model,
                "prompt": full_prompt,
                "prompt_length": len(full_prompt),
                "config": config or {},
                "system_instruction": full_system_text,
                "tools": tool_names,
                **image_meta,
                "section_context": llm_section_context_var.get() or {},
            }
            _append_section_log(section_log_path, section_log_data)

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
        
        # Truncate response if needed
        truncated_response = self._truncate_text(
            response_text,
            self.max_response_length
        )
        
        # Create response record
        response_record = LLMResponse(
            request_id=request_id,
            timestamp=timestamp,
            response_text=truncated_response,
            duration_seconds=round(duration, 3),
            success=success,
            error=error,
            metadata=metadata
        )
        
        # Log the response
        log_data = {
            "event": "llm_response",
            **asdict(response_record),
            **(context or {})
        }
        
        level = logging.INFO if success else logging.ERROR
        
        if self.console_logging:
            if success:
                self.logger.info(
                    f"LLM Response | Duration: {duration:.2f}s | Length: {len(response_text)} chars",
                    extra={"extra_data": log_data}
                )
            else:
                self.logger.error(
                    f"LLM Error | Duration: {duration:.2f}s | Error: {error}",
                    extra={"extra_data": log_data}
                )
        else:
            # Still log to file even if console logging is disabled
            logging.getLogger(__name__).log(
                level,
                f"LLM Response | Success: {success}",
                extra={"extra_data": log_data}
            )

        # Per-section JSONL logging (full response)
        section_log_path = llm_section_log_path_var.get()
        if section_log_path:
            section_log_data = {
                "event": "llm_response",
                "request_id": request_id,
                "timestamp": timestamp,
                "response_text": response_text,
                "response_length": len(response_text),
                "duration_seconds": round(duration, 3),
                "success": success,
                "error": error,
                "metadata": metadata,
                "section_context": llm_section_context_var.get() or {},
            }
            _append_section_log(section_log_path, section_log_data)
    
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

# Context for per-section LLM logging
llm_section_log_path_var: ContextVar[Optional[Path]] = ContextVar(
    "llm_section_log_path", default=None
)
llm_section_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "llm_section_context", default=None
)


def _append_section_log(log_path: Path, data: Dict[str, Any]) -> None:
    """Append a JSONL record to the per-section log file."""
    try:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
    except Exception:
        # Avoid raising during pipeline execution; logging must be best-effort.
        pass


def set_llm_section_log(path: Path, context: Optional[Dict[str, Any]] = None) -> None:
    """Set the per-section log path and base context."""
    llm_section_log_path_var.set(Path(path))
    llm_section_context_var.set(context or {})


def clear_llm_section_log() -> None:
    """Clear per-section log path and context."""
    llm_section_log_path_var.set(None)
    llm_section_context_var.set(None)


@contextmanager
def llm_section_log(path: Path, context: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    """Context manager for scoped per-section logging."""
    path_token = llm_section_log_path_var.set(Path(path))
    context_token = llm_section_context_var.set(context or {})
    try:
        yield
    finally:
        llm_section_log_path_var.reset(path_token)
        llm_section_context_var.reset(context_token)


@contextmanager
def llm_section_context(updates: Dict[str, Any]) -> Iterator[None]:
    """Temporarily update the per-section context."""
    current = llm_section_context_var.get() or {}
    merged = {**current, **(updates or {})}
    token = llm_section_context_var.set(merged)
    try:
        yield
    finally:
        llm_section_context_var.reset(token)


def get_llm_logger() -> LLMLogger:
    """
    Get the default LLM logger instance.
    
    Configuration via environment variables:
    - LLM_LOG_MAX_PROMPT_LENGTH: Max prompt chars to log (default: 500)
    - LLM_LOG_MAX_RESPONSE_LENGTH: Max response chars to log (default: None/unlimited)
    - LLM_LOG_FILE: Path to dedicated LLM log file (default: None)
    - LLM_LOG_CONSOLE: Enable console logging (default: true)
    """
    global _default_logger
    
    if _default_logger is None:
        import os
        
        max_prompt = int(os.getenv("LLM_LOG_MAX_PROMPT_LENGTH", "500"))
        max_response = os.getenv("LLM_LOG_MAX_RESPONSE_LENGTH")
        max_response = int(max_response) if max_response else None
        
        log_file = os.getenv("LLM_LOG_FILE")
        log_file = Path(log_file) if log_file else None
        
        console = os.getenv("LLM_LOG_CONSOLE", "true").lower() == "true"
        
        _default_logger = LLMLogger(
            max_prompt_length=max_prompt,
            max_response_length=max_response,
            log_file=log_file,
            console_logging=console
        )
    
    return _default_logger
