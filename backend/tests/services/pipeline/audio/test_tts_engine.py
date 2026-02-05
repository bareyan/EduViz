"""
Tests for app.services.pipeline.audio.tts_engine
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.pipeline.audio.tts_engine import TTSEngine

# Mock edge_tts module since it might not be installed

@pytest.fixture
def mock_edge_tts_module():
    mock = MagicMock()
    mock.Communicate = MagicMock()
    
    # Needs to be patched where it is used
    with patch("app.services.pipeline.audio.tts_engine.edge_tts", mock):
        yield mock

@pytest.mark.asyncio
class TestTTSEngine:
    """Test TTS Engine functionality."""

    async def test_synthesize_success(self, mock_edge_tts_module, tmp_path):
        """Test successful synthesis."""
        # Setup mock Communicate
        mock_comm_instance = AsyncMock()
        mock_edge_tts_module.Communicate.return_value = mock_comm_instance
        
        engine = TTSEngine()
        output_path = str(tmp_path / "audio.mp3")
        
        # Mock _get_audio_duration to verify it's called
        with patch.object(engine, "_get_audio_duration", AsyncMock(return_value=10.5)):
            duration = await engine.synthesize("Hello", output_path)
            
            assert duration == 10.5
            mock_edge_tts_module.Communicate.assert_called_once()
            mock_comm_instance.save.assert_called_with(output_path)

    async def test_synthesize_failure_fallback(self, mock_edge_tts_module, tmp_path):
        """Test fallback when synthesis fails."""
        mock_edge_tts_module.Communicate.side_effect = Exception("TTS API Error")
        
        engine = TTSEngine()
        output_path = str(tmp_path / "audio.mp3")
        
        with patch.object(engine, "_create_placeholder_audio", AsyncMock(return_value=5.0)) as mock_placeholder:
            duration = await engine.synthesize("Hello", output_path)
            
            assert duration == 5.0
            mock_placeholder.assert_called_once_with("Hello", output_path)

    async def test_synthesize_with_timing(self, mock_edge_tts_module, tmp_path):
        """Test synthesis with word timings."""
        mock_comm_instance = MagicMock()
        mock_edge_tts_module.Communicate.return_value = mock_comm_instance
        
        # Mock stream() to yield chunks
        async def mock_stream():
            yield {"type": "audio", "data": b"chunk1"}
            # offset in 100ns units. 10,000,000 = 1 sec
            yield {
                "type": "WordBoundary", 
                "text": "Hello", 
                "offset": 0, 
                "duration": 5000000 
            }
            yield {"type": "audio", "data": b"chunk2"}

        mock_comm_instance.stream = mock_stream
        
        engine = TTSEngine()
        output_path = str(tmp_path / "audio.mp3")
        
        with patch.object(engine, "_get_audio_duration", AsyncMock(return_value=1.0)):
            result = await engine.synthesize_with_timing("Hello", output_path)
            
            assert result["duration"] == 1.0
            assert len(result["word_timings"]) == 1
            assert result["word_timings"][0]["word"] == "Hello"
            assert result["word_timings"][0]["start"] == 0.0
            assert result["word_timings"][0]["duration"] == 0.5

    async def test_get_audio_duration_ffprobe(self):
        """Test getting duration via ffprobe."""
        engine = TTSEngine()
        
        # Mock subprocess
        process_mock = AsyncMock()
        process_mock.communicate.return_value = (b"12.345\n", b"")
        
        with patch("asyncio.create_subprocess_exec", return_value=process_mock) as mock_exec:
            duration = await engine._get_audio_duration("test.mp3")
            
            assert duration == 12.345
            args = mock_exec.call_args[0]
            assert args[0] == "ffprobe"
            assert args[-1] == "test.mp3"

    async def test_get_audio_duration_fallback(self):
        """Test fallback when ffprobe fails."""
        engine = TTSEngine()
        
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("No ffprobe")):
            duration = await engine._get_audio_duration("test.mp3")
            assert duration == 30.0

    async def test_create_placeholder_audio(self):
        """Test creating silent audio fallback."""
        engine = TTSEngine()
        process_mock = AsyncMock()
        
        with patch("asyncio.create_subprocess_exec", return_value=process_mock) as mock_exec:
            text = "Word1 Word2 Word3 Word4 Word5" # 5 words -> 2 seconds duration
            duration = await engine._create_placeholder_audio(text, "out.mp3")
            
            assert duration == 2.0
            # Verify ffmpeg called with correct duration
            args = mock_exec.call_args[0]
            assert args[0] == "ffmpeg"
            assert "-t" in args
            idx = args.index("-t")
            assert args[idx+1] == "2.0"

    def test_voice_helpers(self):
        """Test voice metadata helpers."""
        assert len(TTSEngine.get_available_voices()) > 0
        assert "en" in TTSEngine.get_available_languages()[0]["code"] or "auto" in str(TTSEngine.get_available_languages())
        
        voices = TTSEngine.get_voices_for_language("en")
        assert len(voices) >= 2
        assert voices[0]["gender"] in ["male", "female"]

    def test_default_voice(self):
        assert TTSEngine.get_default_voice_for_language("en") == "en-GB-RyanNeural"
        # Should fallback to auto/multilingual for unknown
        assert "Multilingual" in TTSEngine.get_default_voice_for_language("klingon")

