"""
Tests for adapters/scripts_io module

Comprehensive tests for script file I/O utilities including loading,
saving, unwrapping, and metadata extraction.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.adapters.scripts_io import (
    _script_path,
    unwrap_script,
    load_script,
    load_script_raw,
    save_script,
    get_script_metadata,
    load_section_script,
)


class TestScriptPath:
    """Test suite for _script_path helper"""

    def test_script_path_construction(self):
        """Test that script path is correctly constructed"""
        path = _script_path("test-job-123")
        
        assert isinstance(path, Path)
        assert path.name == "script.json"
        assert "test-job-123" in str(path)


class TestUnwrapScript:
    """Test suite for unwrap_script function"""

    def test_unwrap_wrapped_script(self):
        """Test unwrapping a wrapped script"""
        wrapped = {
            "script": {
                "title": "Test Title",
                "sections": [{"id": "sec1"}]
            },
            "mode": "comprehensive",
            "output_language": "en"
        }
        
        result = unwrap_script(wrapped)
        
        assert result["title"] == "Test Title"
        assert len(result["sections"]) == 1
        # Should not contain wrapper keys
        assert "mode" not in result
        assert "output_language" not in result

    def test_unwrap_already_unwrapped_script(self):
        """Test that already unwrapped scripts pass through unchanged"""
        unwrapped = {
            "title": "Test Title",
            "sections": [{"id": "sec1"}]
        }
        
        result = unwrap_script(unwrapped)
        
        assert result["title"] == "Test Title"
        assert result["sections"] == [{"id": "sec1"}]

    def test_unwrap_with_title_only(self):
        """Test unwrapping when inner script has only title"""
        wrapped = {
            "script": {
                "title": "Title Only"
            },
            "mode": "overview"
        }
        
        result = unwrap_script(wrapped)
        
        assert result["title"] == "Title Only"

    def test_unwrap_with_sections_only(self):
        """Test unwrapping when inner script has only sections"""
        wrapped = {
            "script": {
                "sections": [{"id": "sec1"}, {"id": "sec2"}]
            }
        }
        
        result = unwrap_script(wrapped)
        
        assert len(result["sections"]) == 2

    def test_unwrap_script_key_but_not_dict(self):
        """Test when script key exists but is not a dict"""
        data = {
            "script": "not a dict",
            "title": "Outer Title"
        }
        
        result = unwrap_script(data)
        
        # Should return original since script is not a valid dict
        assert result["script"] == "not a dict"
        assert result["title"] == "Outer Title"


class TestLoadScript:
    """Test suite for load_script function"""

    def test_load_script_success(self, tmp_path):
        """Test successful script loading"""
        # Create test script
        job_id = "test-job"
        script_data = {
            "script": {
                "title": "Test Video",
                "sections": [{"id": "sec1", "title": "Section 1"}]
            }
        }
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            job_dir = tmp_path / job_id
            job_dir.mkdir()
            script_path = job_dir / "script.json"
            script_path.write_text(json.dumps(script_data))
            
            result = load_script(job_id)
        
        assert result["title"] == "Test Video"
        assert len(result["sections"]) == 1

    def test_load_script_not_found(self, tmp_path):
        """Test loading non-existent script raises HTTPException"""
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                load_script("nonexistent-job")
        
        assert exc_info.value.status_code == 404
        assert "Script not found" in exc_info.value.detail

    def test_load_script_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises HTTPException"""
        job_id = "test-job"
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            job_dir = tmp_path / job_id
            job_dir.mkdir()
            script_path = job_dir / "script.json"
            script_path.write_text("{ invalid json }")
            
            with pytest.raises(HTTPException) as exc_info:
                load_script(job_id)
        
        assert exc_info.value.status_code == 500
        assert "Invalid script JSON" in exc_info.value.detail


class TestLoadScriptRaw:
    """Test suite for load_script_raw function"""

    def test_load_script_raw_preserves_wrapper(self, tmp_path):
        """Test that raw loading preserves wrapper structure"""
        job_id = "test-job"
        script_data = {
            "script": {
                "title": "Test Video",
                "sections": []
            },
            "mode": "comprehensive",
            "output_language": "en"
        }
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            job_dir = tmp_path / job_id
            job_dir.mkdir()
            script_path = job_dir / "script.json"
            script_path.write_text(json.dumps(script_data))
            
            result = load_script_raw(job_id)
        
        # Should preserve wrapper
        assert "script" in result
        assert result["mode"] == "comprehensive"
        assert result["output_language"] == "en"

    def test_load_script_raw_not_found(self, tmp_path):
        """Test loading non-existent script raises HTTPException"""
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                load_script_raw("nonexistent-job")
        
        assert exc_info.value.status_code == 404


class TestSaveScript:
    """Test suite for save_script function"""

    def test_save_script_creates_file(self, tmp_path):
        """Test that save_script creates the script file"""
        job_id = "test-job"
        script_data = {
            "title": "Test Video",
            "sections": [{"id": "sec1"}]
        }
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            save_script(job_id, script_data)
            
            script_path = tmp_path / job_id / "script.json"
            assert script_path.exists()
            
            with open(script_path) as f:
                saved_data = json.load(f)
            
            assert saved_data["title"] == "Test Video"

    def test_save_script_creates_directory(self, tmp_path):
        """Test that save_script creates job directory if needed"""
        job_id = "new-job"
        script_data = {"title": "New Script"}
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            job_dir = tmp_path / job_id
            assert not job_dir.exists()
            
            save_script(job_id, script_data)
            
            assert job_dir.exists()
            assert (job_dir / "script.json").exists()

    def test_save_script_overwrites_existing(self, tmp_path):
        """Test that save_script overwrites existing script"""
        job_id = "test-job"
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            # Save first version
            save_script(job_id, {"title": "Version 1"})
            
            # Save second version
            save_script(job_id, {"title": "Version 2"})
            
            script_path = tmp_path / job_id / "script.json"
            with open(script_path) as f:
                saved_data = json.load(f)
            
            assert saved_data["title"] == "Version 2"


class TestGetScriptMetadata:
    """Test suite for get_script_metadata function"""

    def test_get_metadata_unwrapped_script(self):
        """Test extracting metadata from unwrapped script"""
        script = {
            "title": "Test Title",
            "total_duration_seconds": 300,
            "sections": [{"id": "sec1"}, {"id": "sec2"}, {"id": "sec3"}]
        }
        
        metadata = get_script_metadata(script)
        
        assert metadata["title"] == "Test Title"
        assert metadata["total_duration"] == 300
        assert metadata["sections_count"] == 3

    def test_get_metadata_wrapped_script(self):
        """Test extracting metadata from wrapped script"""
        script = {
            "script": {
                "title": "Wrapped Title",
                "total_duration_seconds": 600,
                "sections": [{"id": "sec1"}]
            },
            "mode": "comprehensive"
        }
        
        metadata = get_script_metadata(script)
        
        assert metadata["title"] == "Wrapped Title"
        assert metadata["total_duration"] == 600
        assert metadata["sections_count"] == 1

    def test_get_metadata_missing_fields(self):
        """Test defaults for missing fields"""
        script = {}
        
        metadata = get_script_metadata(script)
        
        assert metadata["title"] == "Untitled"
        assert metadata["total_duration"] == 0
        assert metadata["sections_count"] == 0


class TestLoadSectionScript:
    """Test suite for load_section_script function"""

    def test_load_section_script_found(self, tmp_path):
        """Test loading a specific section"""
        job_id = "test-job"
        script_data = {
            "title": "Test",
            "sections": [
                {"id": "sec1", "title": "Section 1"},
                {"id": "sec2", "title": "Section 2"},
                {"id": "sec3", "title": "Section 3"}
            ]
        }
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            job_dir = tmp_path / job_id
            job_dir.mkdir()
            (job_dir / "script.json").write_text(json.dumps(script_data))
            
            result = load_section_script(job_id, "sec2")
        
        assert result["id"] == "sec2"
        assert result["title"] == "Section 2"

    def test_load_section_script_not_found(self, tmp_path):
        """Test loading non-existent section raises HTTPException"""
        job_id = "test-job"
        script_data = {
            "title": "Test",
            "sections": [{"id": "sec1", "title": "Section 1"}]
        }
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            job_dir = tmp_path / job_id
            job_dir.mkdir()
            (job_dir / "script.json").write_text(json.dumps(script_data))
            
            with pytest.raises(HTTPException) as exc_info:
                load_section_script(job_id, "nonexistent")
        
        assert exc_info.value.status_code == 404
        assert "Section nonexistent not found" in exc_info.value.detail

    def test_load_section_script_wrapped(self, tmp_path):
        """Test loading section from wrapped script"""
        job_id = "test-job"
        script_data = {
            "script": {
                "title": "Wrapped",
                "sections": [{"id": "wrapped-sec", "title": "Wrapped Section"}]
            }
        }
        
        with patch("app.adapters.scripts_io.OUTPUT_DIR", tmp_path):
            job_dir = tmp_path / job_id
            job_dir.mkdir()
            (job_dir / "script.json").write_text(json.dumps(script_data))
            
            result = load_section_script(job_id, "wrapped-sec")
        
        assert result["id"] == "wrapped-sec"
