
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.analysis.analyzer import MaterialAnalyzer
from app.services.analysis.base import BaseAnalyzer

class TestMaterialAnalyzer:
    @pytest.fixture
    def analyzer(self):
        with patch("app.services.analysis.analyzer.PDFAnalyzer") as mock_pdf, \
             patch("app.services.analysis.analyzer.ImageAnalyzer") as mock_img, \
             patch("app.services.analysis.analyzer.TextAnalyzer") as mock_txt:
            
            # Setup async mocks
            mock_pdf.return_value.analyze = AsyncMock(return_value={"type": "pdf"})
            mock_img.return_value.analyze = AsyncMock(return_value={"type": "image"})
            mock_txt.return_value.analyze = AsyncMock(return_value={"type": "text"})
            
            yield MaterialAnalyzer()

    @pytest.mark.asyncio
    async def test_dispatch_pdf(self, analyzer):
        res = await analyzer.analyze("test.pdf", "id1")
        assert res["type"] == "pdf"
        analyzer.pdf_analyzer.analyze.assert_called_with("test.pdf", "id1")

    @pytest.mark.asyncio
    async def test_dispatch_image(self, analyzer):
        res = await analyzer.analyze("test.png", "id2")
        assert res["type"] == "image"
        analyzer.image_analyzer.analyze.assert_called_with("test.png", "id2")

    @pytest.mark.asyncio
    async def test_dispatch_unsupported(self, analyzer):
        with pytest.raises(ValueError):
            await analyzer.analyze("test.exe", "id3")

class TestBaseAnalyzer:
    def test_get_representative_sample_short(self):
        # We need to mock the mixins/dependencies of BaseAnalyzer to instantiate it?
        # Typically BaseAnalyzer is abstract or mixin, but here it's a class.
        # It calls get_model_config etc in __init__. We need to mock those.
        
        with patch("app.services.analysis.base.get_model_config"), \
             patch("app.services.analysis.base.create_client"), \
             patch("app.services.analysis.base.get_types_module"):
             
            base = BaseAnalyzer()
            text = "Short text"
            assert base._get_representative_sample(text) == text

    def test_get_representative_sample_long(self):
        with patch("app.services.analysis.base.get_model_config"), \
             patch("app.services.analysis.base.create_client"), \
             patch("app.services.analysis.base.get_types_module"):
             
            base = BaseAnalyzer()
            # Create text larger than defaults? default max is 15000.
            # Let's override for test if possible, or generate specific string.
            long_text = "a" * 20000
            mic_drop = base._get_representative_sample(long_text, max_chars=100)
            
            # 40 intro + 40 middle + 20 end = 100
            assert len(mic_drop) > 100 # because of inserted markers
            assert "[...content continues...]" in mic_drop
