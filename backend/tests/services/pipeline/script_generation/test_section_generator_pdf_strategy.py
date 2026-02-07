from unittest.mock import AsyncMock, Mock

import pytest
from pathlib import Path

from app.services.pipeline.script_generation.section_generator import SectionGenerator


def _outline():
    return {
        "sections_outline": [
            {
                "id": "s1",
                "title": "Section 1",
                "section_type": "content",
                "content_to_cover": "Topic details",
                "key_points": ["A", "B"],
                "estimated_duration_seconds": 30,
                "page_start": 2,
                "page_end": 4,
            }
        ]
    }


def _mock_base():
    base = Mock()
    base.build_pdf_part = Mock(return_value={"pdf": "part"})
    base.slice_pdf_pages = Mock(return_value="/tmp/slice.pdf")
    base.build_prompt_contents = Mock(return_value=["attachment", "prompt"])
    base.generate_with_engine = AsyncMock(
        return_value='{"id":"s1","title":"Section 1","narration":"N","tts_narration":"N","supporting_data":[]}'
    )
    base.parse_json = Mock(
        return_value={
            "id": "s1",
            "title": "Section 1",
            "narration": "N",
            "tts_narration": "N",
            "supporting_data": [],
        }
    )
    return base


@pytest.mark.asyncio
async def test_pdf_strategy_defaults_to_full_pdf_without_slicing():
    base = _mock_base()
    generator = SectionGenerator(base=base, use_pdf_page_slices=False)
    artifacts_dir = Path("test_artifacts_pdf_strategy_default")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    sections = await generator.generate_sections(
        outline=_outline(),
        content="",
        language_name="English",
        language_instruction="Generate in English",
        pdf_path="C:/doc.pdf",
        total_pages=10,
        artifacts_dir=str(artifacts_dir),
    )

    assert len(sections) == 1
    assert sections[0]["source_pdf_path"] == "C:/doc.pdf"
    assert base.slice_pdf_pages.call_count == 0
    assert base.build_pdf_part.call_count == 1
    artifacts_dir.rmdir()


@pytest.mark.asyncio
async def test_pdf_strategy_can_opt_in_to_page_slicing():
    base = _mock_base()
    generator = SectionGenerator(base=base, use_pdf_page_slices=True)
    artifacts_dir = Path("test_artifacts_pdf_strategy_slice")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    sections = await generator.generate_sections(
        outline=_outline(),
        content="",
        language_name="English",
        language_instruction="Generate in English",
        pdf_path="C:/doc.pdf",
        total_pages=10,
        artifacts_dir=str(artifacts_dir),
    )

    assert len(sections) == 1
    assert sections[0]["source_pdf_path"] == "/tmp/slice.pdf"
    assert base.slice_pdf_pages.call_count == 1
    (artifacts_dir / "pdf_slices").rmdir()
    artifacts_dir.rmdir()
