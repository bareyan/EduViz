from app.services.infrastructure.storage.analysis_repository import FileBasedAnalysisRepository


def test_save_and_get_analysis(tmp_path):
    repo = FileBasedAnalysisRepository(base_dir=tmp_path)
    payload = {
        "analysis_id": "analysis_file-1",
        "file_id": "file-1",
        "suggested_topics": [{"index": 0, "title": "Topic"}],
    }

    repo.save(payload)
    loaded = repo.get("analysis_file-1")

    assert loaded is not None
    assert loaded["analysis_id"] == "analysis_file-1"
    assert loaded["file_id"] == "file-1"


def test_get_missing_analysis_returns_none(tmp_path):
    repo = FileBasedAnalysisRepository(base_dir=tmp_path)
    assert repo.get("missing-analysis") is None
