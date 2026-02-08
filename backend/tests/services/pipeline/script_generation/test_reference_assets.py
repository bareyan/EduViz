from unittest.mock import Mock

from app.services.pipeline.script_generation.overview_generator import OverviewGenerator
from app.services.pipeline.script_generation.section_generator import SectionGenerator


def _section_generator() -> SectionGenerator:
    base = Mock()
    base.chars_per_second = 12.5
    base.target_segment_duration = 8
    return SectionGenerator(base=base, use_pdf_page_slices=False)


def test_section_generator_adds_missing_referenced_content_entries():
    generator = _section_generator()
    section = {
        "narration": "As shown in Figure 3, the stack doubles. Table 1 summarizes scores.",
        "tts_narration": "As shown in Figure 3, the stack doubles. Table 1 summarizes scores.",
        "supporting_data": [],
    }

    enriched = generator._ensure_reference_content(section)
    references = [item["label"] for item in enriched["supporting_data"] if item.get("type") == "referenced_content"]

    assert "Figure 3" in references
    assert "Table 1" in references
    assert len(references) == 2


def test_section_generator_deduplicates_existing_referenced_content():
    generator = _section_generator()
    section = {
        "narration": "Figure 2 shows the architecture.",
        "tts_narration": "Figure 2 shows the architecture.",
        "supporting_data": [
            {
                "type": "referenced_content",
                "label": "Figure 2",
                "value": {"binding_key": "figure:2", "recreate_in_video": True},
            }
        ],
    }

    enriched = generator._ensure_reference_content(section)
    reference_items = [item for item in enriched["supporting_data"] if item.get("type") == "referenced_content"]
    assert len(reference_items) == 1


def test_section_generator_deduplicates_mentions_across_narration_and_tts():
    generator = _section_generator()
    section = {
        "narration": "Equation 4 defines the gate.",
        "tts_narration": "Equation 4 defines the gate clearly.",
        "supporting_data": [],
    }

    enriched = generator._ensure_reference_content(section)
    reference_items = [item for item in enriched["supporting_data"] if item.get("type") == "referenced_content"]
    assert len(reference_items) == 1
    assert reference_items[0]["value"]["binding_key"] == "equation:4"


def test_section_generator_rewrites_deictic_reference_phrasing():
    generator = _section_generator()
    section = {
        "narration": "If you look at Figure 3, the receptive field expands.",
        "tts_narration": "As shown in Figure 3 in the paper, the receptive field expands.",
        "supporting_data": [],
    }

    enriched = generator._ensure_reference_content(section)

    assert "if you look at" not in enriched["narration"].lower()
    assert "as shown in" not in enriched["tts_narration"].lower()
    assert "in the paper" not in enriched["tts_narration"].lower()
    assert "Figure 3 shows" in enriched["narration"]


def test_overview_generator_validate_script_adds_reference_content_entries():
    generator = OverviewGenerator(base=Mock())
    script = {
        "title": "WaveNet",
        "overview": "Overview",
        "sections": [
            {
                "id": "s1",
                "title": "Architecture",
                "narration": "Figure 5 compares the ablations.",
                "tts_narration": "Figure 5 compares the ablations.",
                "supporting_data": [],
            }
        ],
    }

    validated = generator._validate_script(script, topic={"title": "WaveNet"})
    reference_items = [
        item
        for item in validated["sections"][0]["supporting_data"]
        if item.get("type") == "referenced_content"
    ]
    assert len(reference_items) == 1
    assert reference_items[0]["label"] == "Figure 5"


def test_overview_generator_rewrites_deictic_reference_phrasing():
    generator = OverviewGenerator(base=Mock())
    section = {
        "narration": "As you can see in Figure 2, this block filters features.",
        "tts_narration": "Looking at Figure 2 in the paper, this block filters features.",
        "supporting_data": [],
    }

    enriched = generator._ensure_reference_content(section)

    assert "as you can see in" not in enriched["narration"].lower()
    assert "looking at" not in enriched["tts_narration"].lower()
    assert "in the paper" not in enriched["tts_narration"].lower()
    assert "Figure 2 shows" in enriched["narration"]
