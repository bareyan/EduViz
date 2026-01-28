
import pytest
from app.models.generation import GenerationRequest, GeneratedVideo, GenerationResponse

def test_generation_request_defaults():
    req = GenerationRequest(
        file_id="f1",
        analysis_id="a1",
        selected_topics=[0, 1]
    )
    assert req.style == "3blue1brown"
    assert req.max_video_length == 20
    assert req.voice == "en-US-GuyNeural"
    assert req.pipeline == "default"

def test_generated_video_structure():
    vid = GeneratedVideo(
        section_id="s1",
        title="Title",
        duration_seconds=120,
        video_path="/path/to/vid.mp4",
        narration="Hello world"
    )
    assert vid.duration_seconds == 120
    assert vid.section_id == "s1"

def test_generation_response():
    resp = GenerationResponse(
        job_id="j1",
        status="queued",
        message="Queued"
    )
    assert resp.job_id == "j1"
