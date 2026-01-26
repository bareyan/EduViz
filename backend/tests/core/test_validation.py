
import pytest
from fastapi import HTTPException
from app.core.validation import validate_file_type, validate_upload_path, validate_job_path
from app.config import UPLOAD_DIR, OUTPUT_DIR

def test_validate_file_type():
    # Test valid extensions
    assert validate_file_type("test.pdf", "application/pdf") == ".pdf"
    assert validate_file_type("test.png", "image/png") == ".png"
    
    # Test invalid extension
    with pytest.raises(HTTPException) as exc:
        validate_file_type("test.exe", "application/x-msdownload")
    assert exc.value.status_code == 400

def test_validate_upload_path():
    # Test valid path
    valid_id = "test_123"
    path = validate_upload_path(valid_id)
    assert path == (UPLOAD_DIR / valid_id).resolve()
    
    # Test traversal
    with pytest.raises(HTTPException):
        validate_upload_path("../etc/passwd")

def test_validate_job_path():
    # Test valid path
    valid_id = "job_123"
    path = validate_job_path(valid_id)
    assert path == (OUTPUT_DIR / valid_id).resolve()
    
    # Test traversal
    with pytest.raises(HTTPException):
        validate_job_path("../etc/passwd")
