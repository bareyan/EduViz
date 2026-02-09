
from app.models.jobs import DetailedProgress, JobResponse, ResumeInfo

def test_resume_info_defaults():
    info = ResumeInfo(can_resume=True, completed_sections=2, total_sections=5)
    assert info.failed_sections == []
    assert info.last_completed_section is None

def test_detailed_progress_creation():
    prog = DetailedProgress(
        job_id="job_1",
        status="processing",
        progress=0.5,
        message="Halfway there",
        current_stage="test"
    )
    assert prog.sections == []
    assert prog.script_ready is False
    assert prog.outline_ready is False
    assert prog.outline_sections == []
    assert prog.current_script_section_index is None

def test_job_response_structure():
    resp = JobResponse(
        job_id="job_1",
        status="completed",
        progress=1.0,
        message="Done"
    )
    assert resp.result is None
    assert resp.details is None
