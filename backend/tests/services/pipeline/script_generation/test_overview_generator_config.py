import json
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.pipeline.script_generation.overview_generator import OverviewGenerator


_OVERVIEW_ENV_KEYS = [
    "OVERVIEW_MIN_DURATION_SECONDS",
    "OVERVIEW_MAX_DURATION_SECONDS",
    "OVERVIEW_MIN_SECTIONS",
    "OVERVIEW_MAX_SECTIONS",
    "OVERVIEW_SECTION_MIN_WORDS",
    "OVERVIEW_SECTION_MAX_WORDS",
    "OVERVIEW_CONSTRAINT_RETRY_COUNT",
]


def _make_base() -> Mock:
    base = Mock()
    base.chars_per_second = 12.5
    base.generate_with_engine = AsyncMock()
    base.build_pdf_part = Mock(return_value=None)
    base.build_prompt_contents = Mock(side_effect=lambda prompt, part: [part, prompt])
    return base


def _clear_overview_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _OVERVIEW_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_overview_constraints_use_defaults_when_env_unset(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)

    generator = OverviewGenerator(base=_make_base())

    assert generator.constraints.min_duration_seconds == 180
    assert generator.constraints.max_duration_seconds == 420
    assert generator.constraints.min_sections == 5
    assert generator.constraints.max_sections == 8
    assert generator.constraints.section_min_words == 80
    assert generator.constraints.section_max_words == 170
    assert generator.constraints.constraint_retry_count == 1


def test_overview_constraints_clamp_invalid_env_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERVIEW_MIN_DURATION_SECONDS", "-10")
    monkeypatch.setenv("OVERVIEW_MAX_DURATION_SECONDS", "abc")
    monkeypatch.setenv("OVERVIEW_MIN_SECTIONS", "0")
    monkeypatch.setenv("OVERVIEW_MAX_SECTIONS", "-2")
    monkeypatch.setenv("OVERVIEW_SECTION_MIN_WORDS", "10")
    monkeypatch.setenv("OVERVIEW_SECTION_MAX_WORDS", "oops")
    monkeypatch.setenv("OVERVIEW_CONSTRAINT_RETRY_COUNT", "-1")

    generator = OverviewGenerator(base=_make_base())

    assert generator.constraints.min_duration_seconds == 60
    assert generator.constraints.max_duration_seconds == 420
    assert generator.constraints.min_sections == 1
    assert generator.constraints.max_sections == 1
    assert generator.constraints.section_min_words == 30
    assert generator.constraints.section_max_words == 170
    assert generator.constraints.constraint_retry_count == 0


def test_overview_prompt_reflects_constraint_ranges(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)
    generator = OverviewGenerator(base=_make_base())
    planning = generator._build_planning_profile(
        topic={"title": "Topic"},
        content="Sample source",
        total_pages=None,
    )

    prompt = generator._build_overview_prompt(
        content="Sample source",
        topic={"title": "Topic", "description": "Desc", "subject_area": "math"},
        language_name="English",
        language_instruction="Generate ALL content in English.",
        pdf_attached=False,
        total_pages=None,
        planning=planning,
    )

    assert "5-8 sections total" in prompt
    assert "80-170 words" in prompt
    assert "180-420 seconds" in prompt


def test_overview_schema_uses_configured_min_max_items(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)
    generator = OverviewGenerator(base=_make_base())

    schema = generator._get_response_schema()
    sections_schema = schema["properties"]["sections"]
    narration_description = sections_schema["items"]["properties"]["narration"]["description"]

    assert sections_schema["minItems"] == 5
    assert sections_schema["maxItems"] == 8
    assert "5-8" in sections_schema["description"]
    assert "80-170" in narration_description


def test_overview_constraint_violations_detect_under_target(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)
    generator = OverviewGenerator(base=_make_base())

    script = {
        "sections": [
            {"narration": "short text", "tts_narration": "short text"},
            {"narration": "short text", "tts_narration": "short text"},
        ]
    }

    metrics = generator._compute_script_metrics(script)
    violations = generator._collect_constraint_violations(metrics)

    assert "section_count_too_low" in violations
    assert "section_words_too_low" in violations
    assert "duration_too_low" in violations


def test_short_planning_profile_boosts_section_words_around_twenty_five_percent(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)
    generator = OverviewGenerator(base=_make_base())

    planning = generator._build_planning_profile(
        topic={"estimated_duration": 5, "selected_topic_titles": ["Only Topic"]},
        content="short source",
        total_pages=3,
    )

    baseline = int(
        (generator.constraints.section_min_words + generator.constraints.section_max_words) / 2
    )
    expected = min(generator.constraints.section_max_words, int(round(baseline * 1.25)))

    assert planning.target_section_words == expected
    assert planning.target_section_words > baseline


def test_overview_planning_profile_prefers_more_sections_for_long_material(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)
    generator = OverviewGenerator(base=_make_base())

    planning = generator._build_planning_profile(
        topic={
            "estimated_duration": 35,
            "selected_topic_titles": ["Topic A", "Topic B"],
        },
        content="x" * 40000,
        total_pages=60,
    )

    assert planning.effective_min_sections >= 6
    assert planning.preferred_sections >= planning.effective_min_sections
    assert planning.preferred_duration_seconds >= 360
    assert planning.target_section_words >= 150


def test_overview_constraint_violations_use_adaptive_min_sections(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)
    generator = OverviewGenerator(base=_make_base())

    planning = generator._build_planning_profile(
        topic={"estimated_duration": 40, "selected_topic_titles": ["A", "B"]},
        content="x" * 45000,
        total_pages=70,
    )
    assert planning.effective_min_sections >= 6

    ok_len_text = " ".join(["concept"] * 120)
    script = {
        "sections": [
            {"narration": ok_len_text, "tts_narration": ok_len_text}
            for _ in range(5)
        ]
    }

    metrics = generator._compute_script_metrics(script)
    violations = generator._collect_constraint_violations(metrics, planning)
    assert "section_count_too_low" in violations


@pytest.mark.asyncio
async def test_overview_retries_when_first_script_misses_constraints(monkeypatch: pytest.MonkeyPatch):
    _clear_overview_env(monkeypatch)

    short_script = {
        "title": "Topic",
        "overview": "Overview",
        "sections": [
            {
                "id": "s1",
                "title": "Part 1",
                "narration": "Too short.",
                "tts_narration": "Too short.",
                "supporting_data": [],
            },
            {
                "id": "s2",
                "title": "Part 2",
                "narration": "Still short.",
                "tts_narration": "Still short.",
                "supporting_data": [],
            },
        ],
    }

    long_text = " ".join(["concept"] * 100)
    valid_script = {
        "title": "Topic",
        "overview": "Overview",
        "sections": [
            {
                "id": f"s{i}",
                "title": f"Part {i}",
                "narration": long_text,
                "tts_narration": long_text,
                "supporting_data": [],
            }
            for i in range(1, 6)
        ],
    }

    base = _make_base()
    base.generate_with_engine = AsyncMock(
        side_effect=[json.dumps(short_script), json.dumps(valid_script)]
    )

    generator = OverviewGenerator(base=base)

    script = await generator.generate_overview_script(
        content="source",
        topic={"title": "Topic", "description": "Desc", "subject_area": "math"},
        language_name="English",
        language_instruction="Generate ALL content in English.",
    )

    assert base.generate_with_engine.await_count == 2
    assert len(script["sections"]) == 5
    assert generator._collect_constraint_violations(generator._compute_script_metrics(script)) == []


def test_overview_fallback_has_at_least_configured_min_sections(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OVERVIEW_MIN_SECTIONS", "6")

    generator = OverviewGenerator(base=_make_base())
    fallback_script = generator._fallback_script(topic={"title": "Topic"})

    assert len(fallback_script["sections"]) >= 6
