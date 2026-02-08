from app.services.pipeline.animation.generation.core.visual_strategy import (
    build_visual_strategy,
)


def test_build_visual_strategy_practice_contains_concrete_visual_requirements():
    strategy = build_visual_strategy(
        content_focus="practice",
        video_mode="comprehensive",
        document_context="standalone",
        section={"visual_type": "graph"},
    )
    assert "PRACTICAL VISUAL PRIORITY" in strategy
    assert "graphs, tables, timelines" in strategy
    assert "inputs -> transformation steps -> outputs" in strategy
    assert "Do not rely on Text/MathTex-only plans" in strategy
    assert "Use varied object families" in strategy
    assert "visual_change" in strategy
    assert "data_binding" in strategy
    assert "layout_zone" in strategy
    assert "co-visible text blocks at center" in strategy


def test_build_visual_strategy_auto_uses_section_content_type():
    strategy = build_visual_strategy(
        content_focus="as_document",
        video_mode="overview",
        document_context="auto",
        section={"content_type": "practical"},
    )
    assert "PRACTICAL VISUAL PRIORITY" in strategy


def test_build_visual_strategy_mentions_reference_recreation_when_assets_present():
    strategy = build_visual_strategy(
        content_focus="as_document",
        video_mode="comprehensive",
        document_context="auto",
        section={
            "section_data": {
                "supporting_data": [
                    {
                        "type": "referenced_content",
                        "label": "Figure 4",
                        "value": {"binding_key": "figure:4", "recreate_in_video": True},
                    }
                ]
            }
        },
    )
    assert "REFERENCE RECREATION" in strategy
    assert "referenced items=1" in strategy
