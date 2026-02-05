"""
Schema filters for script generation outputs.

These filters remove unused fields while preserving all values for the
fields we keep. No truncation or cropping is applied.
"""

from typing import Any, Dict, List


OUTLINE_TOP_LEVEL_KEYS = {
    "title",
    "subject_area",
    "overview",
    "learning_objectives",
    "sections_outline",
    "document_analysis",
}

OUTLINE_SECTION_KEYS = {
    "id",
    "title",
    "section_type",
    "content_to_cover",
    "key_points",
    "visual_type",
    "estimated_duration_seconds",
    "page_start",
    "page_end",
}

SECTION_KEYS = {
    "id",
    "title",
    "narration",
    "tts_narration",
    "supporting_data",
    "source_pages",
    "source_pdf_path",
    "visual_description",
}


def filter_outline(outline: Dict[str, Any]) -> Dict[str, Any]:
    """Return a slim outline schema without truncating preserved values."""
    if not isinstance(outline, dict):
        return {}

    filtered: Dict[str, Any] = {}
    for key in OUTLINE_TOP_LEVEL_KEYS:
        if key in outline:
            filtered[key] = outline.get(key)

    # Keep only gaps_to_fill from document_analysis
    doc_analysis = filtered.get("document_analysis")
    if isinstance(doc_analysis, dict):
        gaps = doc_analysis.get("gaps_to_fill")
        filtered["document_analysis"] = {"gaps_to_fill": gaps} if gaps is not None else {}
    elif "document_analysis" in filtered:
        filtered["document_analysis"] = {}

    sections = outline.get("sections_outline")
    if isinstance(sections, list):
        filtered_sections: List[Dict[str, Any]] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            filtered_section = {
                key: section.get(key)
                for key in OUTLINE_SECTION_KEYS
                if key in section
            }
            filtered_sections.append(filtered_section)
        filtered["sections_outline"] = filtered_sections

    return filtered


def filter_section(section: Dict[str, Any]) -> Dict[str, Any]:
    """Return a slim section schema without truncating preserved values."""
    if not isinstance(section, dict):
        return {}

    filtered = {
        key: section.get(key)
        for key in SECTION_KEYS
        if key in section
    }

    return filtered
