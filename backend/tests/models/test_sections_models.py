
from app.models.sections import SectionProgress, SectionInfo, CodeUpdateRequest

def test_section_progress_defaults():
    sect = SectionProgress(
        index=0,
        id="sec_1",
        title="Intro",
        status="waiting"
    )
    assert sect.fix_attempts == 0
    assert sect.has_video is False
    assert sect.error is None

def test_section_info_defaults():
    info = SectionInfo(
        id="sec_1",
        title="Intro",
        status="ready",
        has_video=True,
        has_audio=True,
        has_code=True
    )
    assert info.video_url is None
    assert info.error is None

def test_code_update_request():
    req = CodeUpdateRequest(code="print('hello')")
    assert req.fix_attempt == 1
    
    req2 = CodeUpdateRequest(code="print('hi')", fix_attempt=2)
    assert req2.fix_attempt == 2
