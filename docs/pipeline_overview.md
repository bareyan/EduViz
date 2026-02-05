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
   - Generate choreography JSON
   - Generate full Manim code
   - Apply surgical JSON fixes when validation fails
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


## Animation generation: prompts and schemas

All Manim-related prompt templates are centralized in:
- Directory: `backend/app/services/pipeline/animation/prompts/`

Primary templates (used by the animation generation flow):
- `ANIMATOR_SYSTEM` — system prompt for full Manim code generation.
- `CHOREOGRAPHER_SYSTEM` — system prompt for JSON choreography planning.
- `CHOREOGRAPHY_USER` / `CHOREOGRAPHY_COMPACT_USER` / `CHOREOGRAPHY_OBJECTS_USER` / `CHOREOGRAPHY_SEGMENTS_USER` — user prompts for planning.
- `FULL_IMPLEMENTATION_USER` — user prompt for full file implementation.
- `SURGICAL_FIX_SYSTEM` / `SURGICAL_FIX_USER` — JSON-only repair prompts for validation fixes.

Prompt usage:
- Generation orchestration: `backend/app/services/pipeline/animation/generation/processors.py`
- Scene file assembly and theme enforcement: `backend/app/services/pipeline/animation/generation/core/code_helpers.py`

The system enforces iteration rules via the prompts and validators, stopping once validation succeeds.


## Validation & iteration loop

- The animation pipeline executes this loop:
  1. Generate a JSON choreography plan.
  2. Generate full Manim code from the plan.
  3. Validate (syntax + runtime + spatial).
  4. Apply surgical fixes with structured JSON edits or a full replacement file.
  5. Iterate until valid or retries exhausted.


## Key files & quick reference

- Prompts: `backend/app/services/pipeline/animation/prompts/`
- Generation orchestration: `backend/app/services/pipeline/animation/generation/processors.py`
- Route for recompilation (user-facing): [backend/app/routes/sections.py](backend/app/routes/sections.py)
- LLM prompting engine base and tool handling: [backend/app/services/infrastructure/llm/prompting_engine](backend/app/services/infrastructure/llm/prompting_engine)

Tests covering prompts and generation behaviors:
- `tests/services/test_code_helpers.py` — checks scene parsing and code utilities.
- `tests/services/infrastructure/parsing/test_json_parser.py` — validates JSON repair helpers.


## Extending the pipeline

- To add a new prompt variant, add a `PromptTemplate` under `backend/app/services/pipeline/animation/prompts/` and import it in `generation/processors.py`.
- To change canonical Manim references or versioning: update the prompt reference blocks in `backend/app/services/pipeline/animation/prompts/`.


## Next steps / PR checklist

- [ ] Review this file for completeness and add missing components if you expect other prompts to be documented
- [ ] If you add new themes, update `code_helpers.py` and prompt guidance
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
