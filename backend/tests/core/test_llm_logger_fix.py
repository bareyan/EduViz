"""
Tests for LLM Logger robustness fixes.
Specifically targets the "NoneType has no len()" error.
"""

from unittest.mock import MagicMock
from app.core.llm_logger import LLMLogger

def test_truncate_text_with_none():
    """Test that _truncate_text handles None input gracefully."""
    logger = LLMLogger()
    result = logger._truncate_text(None, 100)
    assert result == ""

def test_log_response_with_none_text():
    """Test that log_response handles a response with None text (common in some Gemini candidates)."""
    logger = LLMLogger(console_logging=False)
    request_id = "test-req-id"
    logger._active_requests[request_id] = 100.0  # Mock start time
    
    # Mock a response object that has a .text property but it returns None
    mock_response = MagicMock()
    # Most likely scenario: response.text raises an AttributeError or returns None
    # depending on the client library state.
    type(mock_response).text = property(lambda x: None)
    
    # This should not raise "TypeError: object of type 'NoneType' has no len()"
    logger.log_response(
        request_id=request_id,
        response=mock_response,
        success=True
    )
    
def test_log_response_with_exception_text():
    """Test that log_response handles a response that raises an exception on .text access."""
    logger = LLMLogger(console_logging=False)
    request_id = "test-req-id"
    logger._active_requests[request_id] = 100.0
    
    mock_response = MagicMock()
    type(mock_response).text = property(lambda x: (_ for _ in ()).throw(AttributeError("No text content")))
    
    # Should fall back to str(response) and not crash
    logger.log_response(
        request_id=request_id,
        response=mock_response,
        success=True
    )

def test_log_request_with_none_prompt():
    """Basic safety check for log_request handles None contents (though unlikely)."""
    logger = LLMLogger(console_logging=False)
    # Should not crash
    logger.log_request(model="test-model", contents=None)
