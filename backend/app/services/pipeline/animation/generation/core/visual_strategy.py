"""
Visual strategy guidance builder for choreography prompts.

Single Responsibility:
- Translate generation intent (content focus + section hints) into explicit
  visual planning instructions for the choreographer stage.
"""

from typing import Any, Dict


def _normalize_focus(content_focus: str, section: Dict[str, Any]) -> str:
    focus = (content_focus or "").strip().lower()
    if focus in {"practice", "theory"}:
        return focus

    section_type = str(section.get("content_type", "")).strip().lower()
    if section_type in {"practical", "problem-solving"}:
        return "practice"
    if section_type == "theoretical":
        return "theory"
    return "as_document"


def build_visual_strategy(
    *,
    content_focus: str,
    video_mode: str,
    document_context: str,
    section: Dict[str, Any],
) -> str:
    """
    Build visual-planning strategy text for choreography prompts.

    The returned string is concise and deterministic so it can be safely
    injected into prompt templates.
    """
    focus = _normalize_focus(content_focus, section)
    mode = (video_mode or "comprehensive").strip().lower()
    context = (document_context or "auto").strip().lower()
    visual_type = str(section.get("visual_type", "")).strip().lower()
    section_data = section.get("section_data") if isinstance(section.get("section_data"), dict) else {}
    supporting_data = section_data.get("supporting_data")
    if not isinstance(supporting_data, list):
        supporting_data = section.get("supporting_data", [])
    if not isinstance(supporting_data, list):
        supporting_data = []

    reference_items = [
        item
        for item in supporting_data
        if isinstance(item, dict)
        and (
            str(item.get("type", "")).strip().lower() == "referenced_content"
            or (
                isinstance(item.get("value"), dict)
                and bool(item.get("value", {}).get("recreate_in_video", False))
            )
        )
    ]

    base = [
        f"Mode={mode}; Context={context}; Section visual_type={visual_type or 'unspecified'}.",
        f"Supporting data items={len(supporting_data)}; referenced items={len(reference_items)}.",
        "Keep every visual tied to narration and avoid decorative-only objects.",
        "Use varied object families when relevant: Axes/NumberPlane, plotted curves, tables, arrows, braces, highlights, and geometric primitives.",
        "Prefer animated state changes (Transform/ReplacementTransform, progressive reveals, moving indicators) over static title-card sequences.",
        "For every step, provide explicit visual_change and narration_cue text.",
        "Bind visuals to supporting data with data_binding keys when possible.",
        "Assign layout_zone for each object and spread co-visible objects across different zones.",
        "Avoid placing multiple co-visible text blocks at center; use relative_to/relation/spacing to keep separation.",
    ]

    if reference_items:
        base.extend(
            [
                "REFERENCE RECREATION: If narration cites Figure/Table/Equation/Appendix, recreate it on-screen.",
                "For each cited artifact, include at least one bound object with a matching data_binding key.",
            ]
        )

    if focus == "practice":
        base.extend(
            [
                "PRACTICAL VISUAL PRIORITY: favor concrete examples over abstract exposition.",
                "Show worked examples explicitly: inputs -> transformation steps -> outputs.",
                "Prefer data visuals when relevant: graphs, tables, timelines, and labeled diagrams.",
                "If supporting_data has numeric/categorical values, include at least one chart-like visual object.",
                "Minimize long static text blocks; use callouts and progressive reveals.",
                "Do not rely on Text/MathTex-only plans; pair text with structures (axes, table cells, arrows, regions, markers).",
                "For algorithmic or procedural topics, animate each operation on visible state (table update, vector shift, node/edge change).",
            ]
        )
    elif focus == "theory":
        base.extend(
            [
                "THEORY VISUAL PRIORITY: emphasize structure, definitions, and conceptual relationships.",
                "Use clean theorem/definition layouts, dependency diagrams, and proof-flow visuals.",
                "Prioritize conceptual clarity over dense numeric examples.",
                "Even for abstract sections, avoid text-only storytelling: include at least one structural visual anchor.",
            ]
        )
    else:
        base.extend(
            [
                "DOCUMENT-LED PRIORITY: mirror source balance between examples and formalism.",
                "If section content looks practical, increase concrete examples and data visuals.",
                "If section content looks theoretical, increase conceptual diagrams and formal structure.",
                "Avoid homogeneous object plans; vary between text, geometry, plots, and annotated structures as content allows.",
            ]
        )

    return "\n".join(base)
