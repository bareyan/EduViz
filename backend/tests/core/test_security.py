
import pytest
from pathlib import Path
from app.core.security import (
    sanitize_filename, 
    validate_job_id, 
    validate_path_within_directory,
    validate_section_index,
    secure_file_path
)

class TestSanitizeFilename:
    def test_basic_sanitization(self):
        assert sanitize_filename("safe_file.txt") == "safe_file.txt"
        
    def test_path_traversal_removal(self):
        assert sanitize_filename("../../etc/passwd") == "passwd"
        assert sanitize_filename("..\\windows\\system32") == "system32"
        
    def test_null_byte_injection(self):
        assert sanitize_filename("file.txt\x00.exe") == "file.txt.exe"
        
    def test_dangerous_characters(self):
        assert sanitize_filename('file"name.txt') == "filename.txt"
        assert sanitize_filename("file|name.txt") == "filename.txt"
        
    def test_empty_result_raises_error(self):
        with pytest.raises(ValueError):
            sanitize_filename("   ...   ")

class TestValidateJobId:
    def test_valid_uuid(self):
        assert validate_job_id("12345678-1234-1234-1234-1234567890ab") is True
        
    def test_invalid_format(self):
        assert validate_job_id("invalid-uuid") is False
        assert validate_job_id("12345678-1234-1234-1234-1234567890ab/../passwd") is False

class TestValidatePathWithinDirectory:
    def test_safe_path(self, tmp_path):
        tmp_path = tmp_path.resolve()
        safe_file = tmp_path / "safe.txt"
        safe_file.touch()
        assert validate_path_within_directory(safe_file, tmp_path) is True
        
    def test_path_traversal(self, tmp_path):
        tmp_path = tmp_path.resolve()
        outside_file = tmp_path.parent / "outside.txt"
        # Create a relative path that tries to escape
        # Note: We can't easily construct a real escaping path object without it resolving automatically in some OSs
        # So we trust the boolean logic of the function
        assert validate_path_within_directory(outside_file, tmp_path) is False

class TestSecureFilePath:
    def test_constructs_valid_path(self, tmp_path):
        tmp_path = tmp_path.resolve()
        path = secure_file_path(tmp_path, "subdir", "file.txt", create_dirs=True)
        assert path is not None
        assert path == tmp_path / "subdir" / "file.txt"
        assert (tmp_path / "subdir").exists()
        
    def test_prevents_traversal(self, tmp_path):
        tmp_path = tmp_path.resolve()
        path = secure_file_path(tmp_path, "..", "outside.txt")
        assert path is None
