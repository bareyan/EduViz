import json

from app.core.llm_logger import LLMLogger, set_llm_section_log, clear_llm_section_log


def test_section_log_writes_full_prompt_and_response(tmp_path):
    log_path = tmp_path / "llm_calls.jsonl"
    logger = LLMLogger(max_prompt_length=5, max_response_length=5, console_logging=False)

    full_prompt = "This is a full prompt that should not be truncated."
    full_response = "This is a full response that should not be truncated."

    set_llm_section_log(log_path, {"section_index": 1, "stage": "test"})
    try:
        request_id = logger.log_request(
            model="test-model",
            contents=full_prompt,
            config={"temperature": 0.1},
        )
        logger.log_response(
            request_id=request_id,
            response=full_response,
            success=True,
            metadata={"usage": {"input_tokens": 1, "output_tokens": 2}},
        )
    finally:
        clear_llm_section_log()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    request_record = json.loads(lines[0])
    response_record = json.loads(lines[1])

    assert request_record["event"] == "llm_request"
    assert request_record["prompt"] == full_prompt
    assert request_record["prompt_length"] == len(full_prompt)
    assert request_record["section_context"]["section_index"] == 1

    assert response_record["event"] == "llm_response"
    assert response_record["response_text"] == full_response
    assert response_record["response_length"] == len(full_response)
    assert response_record["section_context"]["stage"] == "test"
