
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import io

from app.main import app
from app.models import JobResponse
from app.models.status import JobStatus
from app.services.job_manager import Job

client = TestClient(app)

# --- Upload Tests ---
def test_upload_file_success():
    # Mock FileUploadUseCase
    mock_use_case = AsyncMock()
    mock_response = MagicMock()
    mock_response.file_id = "file_123"
    mock_response.filename = "test.pdf"
    mock_response.size = 1000
    mock_response.content_type = "application/pdf"
    mock_use_case.execute.return_value = mock_response

    with patch("app.routes.upload.FileUploadUseCase", return_value=mock_use_case):
        
        # Create a dummy file
        files = {"file": ("test.pdf", b"dummy content", "application/pdf")}
        response = client.post("/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["file_id"] == "file_123"
        assert data["filename"] == "test.pdf"

# --- Analysis Tests ---
def test_analyze_material_success():
    mock_result = {
        "file_id": "file_123",
        "analysis_id": "an_123",
        "summary": "Test Summary",
        "main_subject": "Math",
        "difficulty_level": "Beginner",
        "key_concepts": [],
        "detected_math_elements": 0,
        "suggested_topics": []
    }

    with patch("app.routes.analysis.find_uploaded_file", return_value="/tmp/test.pdf"), \
         patch("app.routes.analysis.analyzer.analyze", new_callable=AsyncMock) as mock_analyze:
        
        mock_analyze.return_value = mock_result
        
        response = client.post("/analyze", json={"file_id": "file_123"})
        
        assert response.status_code == 200
        assert response.json() == mock_result

def test_analyze_material_error():
    with patch("app.routes.analysis.find_uploaded_file", return_value="/tmp/bad.pdf"), \
         patch("app.routes.analysis.analyzer.analyze", side_effect=ValueError("Bad file")) as mock_analyze:
         
        response = client.post("/analyze", json={"file_id": "bad_file"})
        assert response.status_code == 500

# --- Jobs Tests ---
def test_get_job_status_success():
    mock_job = Job(
        id="job_123",
        status=JobStatus.COMPLETED,
        progress=100.0,
        message="Done"
    )
    
    mock_repo = MagicMock()
    mock_repo.get.return_value = mock_job
    
    with patch("app.routes.jobs.FileBasedJobRepository", return_value=mock_repo):
        response = client.get("/job/job_123")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job_123"
        assert data["status"] == "completed"
        assert data["progress"] == 1.0

def test_get_job_status_not_found():
    mock_repo = MagicMock()
    mock_repo.get.return_value = None
    
    with patch("app.routes.jobs.FileBasedJobRepository", return_value=mock_repo):
        response = client.get("/job/missing_job")
        assert response.status_code == 404

def test_delete_job():
    mock_repo = MagicMock()
    mock_repo.delete.return_value = {"id": "del_job"}
    
    with patch("app.routes.jobs.FileBasedJobRepository", return_value=mock_repo), \
         patch("app.routes.jobs.shutil.rmtree") as mock_rm:
        
        # Need to mock exists call? 
        # app.routes.jobs.OUTPUT_DIR / job_id .exists()
        # It's a Path object property. tough to patch just for one instance.
        # But for 'delete', checking execution is enough.
        
        with patch("pathlib.Path.exists", return_value=True):
            response = client.delete("/job/del_job")
            assert response.status_code == 200
            mock_repo.delete.assert_called_with("del_job")
