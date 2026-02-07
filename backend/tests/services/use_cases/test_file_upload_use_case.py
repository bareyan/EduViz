"""
Tests for app.services.use_cases.file_upload_use_case
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import UploadFile, HTTPException
from app.services.use_cases.file_upload_use_case import FileUploadUseCase, FileUploadRequest


@pytest.mark.asyncio
class TestFileUploadUseCase:
    """Test FileUploadUseCase logic."""

    @pytest.fixture
    def use_case(self):
        return FileUploadUseCase()

    @pytest.fixture
    def mock_file(self):
        file = MagicMock(spec=UploadFile)
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.read = AsyncMock(side_effect=[b"test content", b""])
        return file

    async def test_upload_success(self, use_case, mock_file, tmp_path):
        """Test successful file upload."""
        request = FileUploadRequest(file=mock_file, file_id="cust-id")
        
        # Patch UPLOAD_DIR to use tmp_path
        with patch("app.services.use_cases.file_upload_use_case.UPLOAD_DIR", tmp_path), \
             patch("app.services.use_cases.file_upload_use_case.validate_file_type", return_value=".pdf"):
            
            response = await use_case.execute(request)
            
            assert response.file_id == "cust-id"
            assert response.filename == "test.pdf"
            assert response.size == 12 # len(b"test content")
            
            # Verify file was written
            saved_file = tmp_path / "cust-id.pdf"
            assert saved_file.exists()
            assert saved_file.read_bytes() == b"test content"

    async def test_upload_invalid_type(self, use_case, mock_file):
        """Test upload with invalid file type."""
        request = FileUploadRequest(file=mock_file)
        
        with patch("app.services.use_cases.file_upload_use_case.validate_file_type") as mock_val:
            mock_val.side_effect = HTTPException(status_code=400, detail="Invalid type")
            
            with pytest.raises(HTTPException) as exc:
                await use_case.execute(request)
            assert exc.value.status_code == 400

    async def test_upload_io_error(self, use_case, mock_file, tmp_path):
        """Test handling of IO errors."""
        request = FileUploadRequest(file=mock_file)
        
        with patch("app.services.use_cases.file_upload_use_case.UPLOAD_DIR", tmp_path), \
             patch("app.services.use_cases.file_upload_use_case.validate_file_type", return_value=".pdf"), \
             patch("builtins.open", side_effect=IOError("Disk Full")):
            
            with pytest.raises(HTTPException) as exc:
                await use_case.execute(request)
            assert exc.value.status_code == 500
            assert "Disk Full" in str(exc.value.detail)

    async def test_upload_too_large(self, use_case, mock_file, tmp_path):
        """Test upload rejected when file exceeds configured max size."""
        request = FileUploadRequest(file=mock_file, max_size_bytes=4)

        with patch("app.services.use_cases.file_upload_use_case.UPLOAD_DIR", tmp_path), \
             patch("app.services.use_cases.file_upload_use_case.validate_file_type", return_value=".pdf"):
            with pytest.raises(HTTPException) as exc:
                await use_case.execute(request)
            assert exc.value.status_code == 413
