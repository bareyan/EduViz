# EduViz Pipeline — Architecture & Prompts Reference

This document maps the end-to-end pipeline, the logical flow, key modules, and all Manim-related prompts used by the animation generation subsystem.

**Audience:** engineers and reviewers who need a single place to understand how content moves through the system, where prompts live, and how generation + validation iterate.

---

**Contents**

- **Overview**
- **High-level flow**
- **Logical tree (components & responsibilities)**
- **Animation generation: prompts and tools**
- **Validation & iteration loop**
- **Key files & where to find them**
- **Extending the pipeline**
- **Next steps / PR checklist**

---

## Overview

EduViz converts uploaded content into narrated video sections with algorithmically generated animations. The system is organized as a series of pipeline stages implemented as services under `backend/app/services/pipeline`.

Core capabilities:
- Parse and analyze input documents (PDF / text)
- Generate script sections and narration
- Produce a visual script / segmented plan
- Generate Manim `construct()` code via LLM prompts
- Validate, patch, and iterate until code is valid
- Render and assemble final video using FFmpeg


## High-level flow

1. Upload / ingest content
2. Content analysis → generate script sections
3. For each section: produce narration + visual script
4. Animation generation (LLM).
   - Use `write_manim_code` tool for full code generation
   - Use `patch_manim_code` for targeted fixes
   - Iterate until validation succeeds
5. Render segments and assemble into final video
6. Store outputs


## Logical tree (components & responsibilities)

- **API / Routes**
  - `backend/app/main.py` — app entrypoint and wiring
  - `backend/app/routes/sections.py` — endpoints for section operations (including recompile)

- **Pipeline services** (major modules)
  - `backend/app/services/pipeline/content_analysis` — parse and extract structured content
  - `backend/app/services/pipeline/script_generation` — generate textual script and sections
  - `backend/app/services/pipeline/visual_script` — plan per-section visuals and timing
  - `backend/app/services/pipeline/animation` — the Manim generation/validation pipeline
  - `backend/app/services/pipeline/assembly` — rendering and ffmpeg assembly

- **Infrastructure / LLM**
  - `backend/app/services/infrastructure/llm/prompting_engine` — engine, tools, and helpers used to call LLMs and register tools

- **Storage / Outputs**
  - `backend/app/core` + repository services under `backend/app/services/infrastructure/storage`


## Animation generation: prompts and tools

All Manim-related prompt templates are centralized in:
- File: [backend/app/services/pipeline/animation/prompts.py](backend/app/services/pipeline/animation/prompts.py)

Primary templates exported there (used by generation flows):
- `AGENTIC_GENERATION_SYSTEM`: System prompt describing tool-based iteration and rules (used to start the agentic generation flow).
- `AGENTIC_GENERATION_USER`: User prompt template that asks the model to generate the `construct()` method body for a section.
- `AGENTIC_GENERATION_WITH_VISUAL_SCRIPT_USER`: Variant that consumes the Visual Script (segments + timing) to strictly follow the script.
- `RECOMPILE_SYSTEM` / `RECOMPILE_USER`: Prompts exposed for user-driven recompilation of code via the sections route.
- `TOOL_CORRECTION_SYSTEM`: System prompt used when performing tool-based corrections (calls into `patch_manim_code` / `write_manim_code`).
- `FIX_CODE_USER`, `FIX_CODE_RETRY_USER`, `GENERATION_RETRY_USER`: Templates the generation tool uses when receiving validation errors and instructing the model to fix code.

Helper formatting functions (also in `prompts.py`):
- `format_section_context(section)` — short section metadata for prompts
- `format_timing_context(section)` — simple timing lines for narration-to-animation alignment
- `format_visual_script_for_prompt(visual_script)` — turns a VisualScriptPlan into a human-readable chunk for the LLM
- `format_segment_timing_for_prompt(visual_script)` — tabular timing breakdown for the LLM

Where these prompts are used:
- Generation orchestration: `backend/app/services/pipeline/animation/generation/tools/generation.py` — imports and formats templates before sending to the LLM tools.
  - File: [backend/app/services/pipeline/animation/generation/tools/generation.py](backend/app/services/pipeline/animation/generation/tools/generation.py)
- Context / Manim-specific reference: `backend/app/services/pipeline/animation/generation/tools/context.py` — contains canonical `MANIM_VERSION` and `get_manim_reference()` which supplies `manim_context` used in prompts.
  - File: [backend/app/services/pipeline/animation/generation/tools/context.py](backend/app/services/pipeline/animation/generation/tools/context.py)

Tools the prompting engine exposes to the LLM (declared in the prompting engine / tool handler):
- `write_manim_code` — full code generation tool (returns validation results)
- `patch_manim_code` — targeted patching tool (search/replace or small edits)

These tools implement validation + return feedback; the system enforces the iteration rules from `AGENTIC_GENERATION_SYSTEM` where the agent must stop on "Validation Successful".


## Validation & iteration loop

- The generation tool executes this loop:
  1. Send `AGENTIC_GENERATION_SYSTEM` + `AGENTIC_GENERATION_USER` to the LLM (via the prompting engine) and call `write_manim_code`.
  2. The tool runs code validation (syntax + Manim CE expectations).
  3. If validation fails, the system prepares a `FIX_CODE_USER` request (with error output) and prefers `patch_manim_code` for small fixes.
  4. Iterate until success or max attempts reached. If user asks for a rewrite, `RECOMPILE_USER` can be used via route handlers.

Important enforcement rules (from templates):
- Model should not emit code in chat messages; it must call tools.
- When receiving "Validation Successful" the model must stop making changes.
- Timing rules (for visual scripts) must be honored: animations during audio segments must complete within the audio duration; `self.wait()` should honor post-narration pause.


## Key files & quick reference

- Prompts: [backend/app/services/pipeline/animation/prompts.py](backend/app/services/pipeline/animation/prompts.py)
- Generation orchestration & tools: [backend/app/services/pipeline/animation/generation/tools/generation.py](backend/app/services/pipeline/animation/generation/tools/generation.py)
- Manim context: [backend/app/services/pipeline/animation/generation/tools/context.py](backend/app/services/pipeline/animation/generation/tools/context.py)
- Route for recompilation (user-facing): [backend/app/routes/sections.py](backend/app/routes/sections.py)
- LLM prompting engine base and tool handling: [backend/app/services/infrastructure/llm/prompting_engine](backend/app/services/infrastructure/llm/prompting_engine)

Tests covering prompts and generation behaviors:
- `tests/services/pipeline/animation/test_animation_prompts.py` — ensures helpers and prompt formatting behave as expected.
- `tests/services/pipeline/animation/generation/tools/test_generation_tool.py` — tests tool behavior and iteration loop.


## Extending the pipeline

- To add a new prompt variant, add a `PromptTemplate` in `prompts.py` and import it in the generation tool where you need it.
- To add a new LLM tool (e.g. `refine_manim_code`): register it with the prompting engine, implement its wrapper in `generation/tools/*`, and update `AGENTIC_GENERATION_SYSTEM` (if you want agents to use it).
- To change canonical Manim references or versioning: update `generation/tools/context.py` (single source of truth for `MANIM_VERSION` and `get_manim_reference()`).


## Next steps / PR checklist

- [ ] Review this file for completeness and add missing components if you expect other prompts to be documented
- [ ] If you want the removed items reintroduced (e.g. `MANIM_VERSION` in `prompts.py`), revert with a short PR and add tests
- [ ] Optionally open a PR for this docs file and the `prompts.py` cleanup change together
- [ ] Run the backend test suite after changes: from `backend/` run:

```bash
python -m venv .venv
# activate .venv for your OS
pip install -r requirements.txt
pytest -q
```


---

If you'd like, I can also:
- Generate a sequence diagram ASCII/text block showing a single-generation iteration, or
- Create a small README in `backend/app/services/pipeline/animation/` with localized pointers to these prompts and tests.

Which of those (diagram / README / open PR) would you prefer next?
