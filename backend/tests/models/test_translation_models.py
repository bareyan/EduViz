"""
Tests for models/translation module

Tests for translation-related Pydantic models.
"""

import pytest
from pydantic import ValidationError
from app.models.translation import (
    TranslationRequest,
    TranslationInfo,
    TranslationResponse,
)


class TestTranslationRequest:
    """Test suite for TranslationRequest model"""

    def test_create_with_required_fields(self):
        """Test creating TranslationRequest with required fields only"""
        request = TranslationRequest(
            job_id="job-123",
            target_language="fr"
        )
        
        assert request.job_id == "job-123"
        assert request.target_language == "fr"
        assert request.voice is None  # Optional field

    def test_create_with_all_fields(self):
        """Test creating TranslationRequest with all fields"""
        request = TranslationRequest(
            job_id="job-456",
            target_language="es",
            voice="es-ES-AlvaroNeural"
        )
        
        assert request.job_id == "job-456"
        assert request.target_language == "es"
        assert request.voice == "es-ES-AlvaroNeural"

    def test_missing_job_id_raises_error(self):
        """Test that missing job_id raises validation error"""
        with pytest.raises(ValidationError):
            TranslationRequest(target_language="fr")

    def test_missing_target_language_raises_error(self):
        """Test that missing target_language raises validation error"""
        with pytest.raises(ValidationError):
            TranslationRequest(job_id="job-123")

    def test_voice_can_be_none(self):
        """Test voice field accepts None"""
        request = TranslationRequest(
            job_id="job-789",
            target_language="de",
            voice=None
        )
        
        assert request.voice is None


class TestTranslationInfo:
    """Test suite for TranslationInfo model"""

    def test_create_with_required_fields(self):
        """Test creating TranslationInfo with required fields"""
        info = TranslationInfo(
            language="fr",
            language_name="French",
            has_audio=True,
            has_video=True
        )
        
        assert info.language == "fr"
        assert info.language_name == "French"
        assert info.has_audio is True
        assert info.has_video is True
        assert info.video_url is None

    def test_create_with_video_url(self):
        """Test creating TranslationInfo with video URL"""
        info = TranslationInfo(
            language="es",
            language_name="Spanish",
            has_audio=True,
            has_video=True,
            video_url="/outputs/job-123/translations/es/video.mp4"
        )
        
        assert info.video_url == "/outputs/job-123/translations/es/video.mp4"

    def test_has_audio_false(self):
        """Test TranslationInfo with audio not available"""
        info = TranslationInfo(
            language="ja",
            language_name="Japanese",
            has_audio=False,
            has_video=False
        )
        
        assert info.has_audio is False
        assert info.has_video is False

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raises error"""
        with pytest.raises(ValidationError):
            TranslationInfo(language="fr")

    def test_all_boolean_combinations(self):
        """Test various combinations of boolean fields"""
        # Audio only
        info1 = TranslationInfo(
            language="ko",
            language_name="Korean",
            has_audio=True,
            has_video=False
        )
        assert info1.has_audio is True
        assert info1.has_video is False
        
        # Video only
        info2 = TranslationInfo(
            language="zh",
            language_name="Chinese",
            has_audio=False,
            has_video=True
        )
        assert info2.has_audio is False
        assert info2.has_video is True


class TestTranslationResponse:
    """Test suite for TranslationResponse model"""

    def test_create_with_all_fields(self):
        """Test creating TranslationResponse with all fields"""
        response = TranslationResponse(
            job_id="job-123",
            language="fr",
            status="completed",
            message="Translation completed successfully"
        )
        
        assert response.job_id == "job-123"
        assert response.language == "fr"
        assert response.status == "completed"
        assert response.message == "Translation completed successfully"

    def test_in_progress_status(self):
        """Test TranslationResponse with in-progress status"""
        response = TranslationResponse(
            job_id="job-456",
            language="es",
            status="in_progress",
            message="Translating section 2 of 5"
        )
        
        assert response.status == "in_progress"
        assert "section 2" in response.message

    def test_failed_status(self):
        """Test TranslationResponse with failed status"""
        response = TranslationResponse(
            job_id="job-789",
            language="de",
            status="failed",
            message="Translation failed: Audio synthesis error"
        )
        
        assert response.status == "failed"
        assert "failed" in response.message

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raises error"""
        with pytest.raises(ValidationError):
            TranslationResponse(job_id="job-123")


class TestTranslationModelsIntegration:
    """Integration tests for translation models"""

    def test_request_response_flow(self):
        """Test typical request-response flow"""
        # Create request
        request = TranslationRequest(
            job_id="job-integration",
            target_language="hy",  # Armenian
            voice="hy-AM-AnahitNeural"
        )
        
        # Create response
        response = TranslationResponse(
            job_id=request.job_id,
            language=request.target_language,
            status="queued",
            message="Translation queued for processing"
        )
        
        assert response.job_id == request.job_id
        assert response.language == request.target_language

    def test_info_after_completion(self):
        """Test TranslationInfo after translation completion"""
        info = TranslationInfo(
            language="fr",
            language_name="French",
            has_audio=True,
            has_video=True,
            video_url="/outputs/test-job/translations/fr/final_video.mp4"
        )
        
        assert info.has_audio and info.has_video
        assert info.video_url is not None

    def test_model_serialization(self):
        """Test that models serialize correctly"""
        request = TranslationRequest(
            job_id="serial-test",
            target_language="it"
        )
        
        # Convert to dict
        request_dict = request.model_dump()
        
        assert request_dict["job_id"] == "serial-test"
        assert request_dict["target_language"] == "it"
        assert request_dict["voice"] is None

    def test_model_json_serialization(self):
        """Test that models serialize to JSON correctly"""
        response = TranslationResponse(
            job_id="json-test",
            language="pt",
            status="completed",
            message="Done"
        )
        
        # Convert to JSON
        json_str = response.model_dump_json()
        
        assert "json-test" in json_str
        assert "completed" in json_str
