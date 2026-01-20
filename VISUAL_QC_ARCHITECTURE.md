# Visual QC Architecture Diagram

## High-Level System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Video Generation Pipeline                        │
│                                                                       │
│  ┌──────────────┐                                                    │
│  │   Material   │                                                    │
│  │   Analysis   │                                                    │
│  └──────┬───────┘                                                    │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                    │
│  │   Script     │                                                    │
│  │  Generation  │                                                    │
│  └──────┬───────┘                                                    │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────┐                   │
│  │  FOR EACH SECTION (Parallel Processing)     │                   │
│  │                                              │                   │
│  │  ┌─────────────────────────────────┐        │                   │
│  │  │ 1. Generate Manim Code (Gemini) │        │                   │
│  │  └──────────┬──────────────────────┘        │                   │
│  │             │                                │                   │
│  │             ▼                                │                   │
│  │  ┌─────────────────────────────────┐        │                   │
│  │  │ 2. Render Video (Manim)         │        │                   │
│  │  └──────────┬──────────────────────┘        │                   │
│  │             │                                │                   │
│  │             ▼                                │                   │
│  │  ╔═══════════════════════════════════════╗  │                   │
│  │  ║   VISUAL QUALITY CONTROL (NEW!)      ║  │                   │
│  │  ║                                       ║  │                   │
│  │  ║  ┌─────────────────────────────────┐ ║  │                   │
│  │  ║  │ a. Extract Keyframes (FFmpeg)   │ ║  │                   │
│  │  ║  │    - 5 frames from video        │ ║  │                   │
│  │  ║  └───────────┬─────────────────────┘ ║  │                   │
│  │  ║              │                        ║  │                   │
│  │  ║              ▼                        ║  │                   │
│  │  ║  ┌─────────────────────────────────┐ ║  │                   │
│  │  ║  │ b. Analyze Frames               │ ║  │                   │
│  │  ║  │    - Vision LLM (Ollama)        │ ║  │                   │
│  │  ║  │    - Detect visual issues       │ ║  │                   │
│  │  ║  └───────────┬─────────────────────┘ ║  │                   │
│  │  ║              │                        ║  │                   │
│  │  ║              ▼                        ║  │                   │
│  │  ║       Critical Issues?                ║  │                   │
│  │  ║       ┌─────┴─────┐                  ║  │                   │
│  │  ║       │           │                  ║  │                   │
│  │  ║      Yes         No                  ║  │                   │
│  │  ║       │           │                  ║  │                   │
│  │  ║       ▼           ▼                  ║  │                   │
│  │  ║  ┌─────────┐  ┌────────┐            ║  │                   │
│  │  ║  │Generate │  │ Accept │            ║  │                   │
│  │  ║  │  Fixed  │  │ Video  │            ║  │                   │
│  │  ║  │  Code   │  └────────┘            ║  │                   │
│  │  ║  └────┬────┘                         ║  │                   │
│  │  ║       │                              ║  │                   │
│  │  ║       ▼                              ║  │                   │
│  │  ║  ┌─────────────────────────────┐    ║  │                   │
│  │  ║  │ c. Re-render with Fix       │    ║  │                   │
│  │  ║  │    - Update Manim code      │    ║  │                   │
│  │  ║  │    - Render again           │    ║  │                   │
│  │  ║  └─────────┬───────────────────┘    ║  │                   │
│  │  ║            │                         ║  │                   │
│  │  ║            └──► QC Again (max 2x)   ║  │                   │
│  │  ╚═══════════════════════════════════════╝  │                   │
│  │             │                                │                   │
│  │             ▼                                │                   │
│  │  ┌─────────────────────────────────┐        │                   │
│  │  │ 3. Section Complete             │        │                   │
│  │  └─────────────────────────────────┘        │                   │
│  └──────────────────────────────────────────────┘                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                    │
│  │   Combine    │                                                    │
│  │   Sections   │                                                    │
│  └──────┬───────┘                                                    │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                    │
│  │    Final     │                                                    │
│  │    Video     │                                                    │
│  └──────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Visual QC Component Detail

```
┌─────────────────────────────────────────────────────────────────┐
│              VisualQualityController Class                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Inputs:                                                        │
│  • Video file path                                              │
│  • Section metadata (title, narration, visual_description)     │
│  • Model tier (fastest/balanced/capable/best)                  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Step 1: extract_keyframes()                              │ │
│  │  ─────────────────────────────────────────────────────   │ │
│  │  • Use FFmpeg to extract frames                           │ │
│  │  • Distribute evenly across video duration                │ │
│  │  • Save as PNG files                                      │ │
│  │  • Return: List of frame paths                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Step 2: analyze_frames()                                 │ │
│  │  ─────────────────────────────────────────────────────   │ │
│  │  • Build analysis prompt with context                     │ │
│  │  • Send frames to Ollama vision model                     │ │
│  │  • Model analyzes for visual issues:                      │ │
│  │    - Text overlaps                                         │ │
│  │    - Off-screen elements                                   │ │
│  │    - Unreadable text                                       │ │
│  │    - Crowded layouts                                       │ │
│  │    - Poor positioning                                      │ │
│  │  • Parse JSON response                                     │ │
│  │  • Return: {status, description, issues[]}                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          ↓                                      │
│                   Issues Found?                                 │
│                  ┌──────┴──────┐                               │
│                 Yes            No                              │
│                  │              │                               │
│                  ▼              ▼                               │
│  ┌─────────────────────────┐  Return "ok"                      │
│  │  Step 3: generate_fix() │                                   │
│  │  ─────────────────────  │                                   │
│  │  • Build fix prompt     │                                   │
│  │  • Include:             │                                   │
│  │    - Original code      │                                   │
│  │    - Issue descriptions │                                   │
│  │    - Fix suggestions    │                                   │
│  │  • LLM generates fix    │                                   │
│  │  • Validate code        │                                   │
│  │  • Return: Fixed code   │                                   │
│  └─────────────────────────┘                                   │
│                          ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Step 4: cleanup_frames()                                 │ │
│  │  ─────────────────────────────────────────────────────   │ │
│  │  • Delete temporary frame files                            │ │
│  │  • Remove temporary directories                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Outputs:                                                       │
│  • QC Result: {status, description, issues, frame_paths}       │
│  • Fixed Code: Complete Manim Python code (if issues found)   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Integration with ManimGenerator

```
┌─────────────────────────────────────────────────────────────────┐
│                    ManimGenerator Class                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  __init__():                                                    │
│    • Initialize Gemini client                                   │
│    • Initialize VisualQualityController ← NEW                  │
│                                                                 │
│  generate_section_video():                                      │
│    ├─► Generate Manim code (Gemini)                            │
│    ├─► Write code to file                                       │
│    └─► _render_scene() ────────────────────┐                   │
│                                             │                   │
│  _render_scene():                           │                   │
│  ┌──────────────────────────────────────────┘                  │
│  │                                                              │
│  │  1. Run manim command                                        │
│  │  2. Check for syntax/runtime errors                          │
│  │     └─► If error: _correct_manim_code() → retry            │
│  │                                                              │
│  │  3. Rendering successful                                     │
│  │  4. Find rendered video file                                 │
│  │                                                              │
│  │  ╔═══════════════════════════════════════╗                  │
│  │  ║  5. VISUAL QC CHECK (NEW!)            ║                  │
│  │  ║  ───────────────────────────────────  ║                  │
│  │  ║  if self.visual_qc and enabled:       ║                  │
│  │  ║    • Check model available            ║                  │
│  │  ║    • Run check_video_quality()        ║                  │
│  │  ║    • Cleanup frames                   ║                  │
│  │  ║    • If critical issues:              ║                  │
│  │  ║      - Generate fix                   ║                  │
│  │  ║      - Update code file               ║                  │
│  │  ║      - Recursively call _render_scene ║                  │
│  │  ║        with qc_iteration++            ║                  │
│  │  ║    • Max iterations: 2                ║                  │
│  │  ╚═══════════════════════════════════════╝                  │
│  │                                                              │
│  │  6. Return video path                                        │
│  └──────────────────────────────────────────────────────────────│
│                                                                 │
│  Configuration:                                                 │
│    ENABLE_VISUAL_QC = True          ← Enable/disable           │
│    QC_MODEL = "balanced"            ← Model selection          │
│    MAX_QC_ITERATIONS = 2            ← Retry limit              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                         Technology Stack                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Video Generation:                                              │
│  ┌──────────────────┐                                           │
│  │ Gemini AI        │ → Generate Manim code                    │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ Manim Community  │ → Render animations                      │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ Edge TTS         │ → Generate narration audio               │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ FFmpeg           │ → Combine audio + video                  │
│  └──────────────────┘                                           │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Visual Quality Control (NEW):                                  │
│  ┌──────────────────┐                                           │
│  │ Ollama           │ → Local LLM runtime                      │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ Vision LLM       │ → Analyze video frames                   │
│  │ (llama3.2-vision,│                                           │
│  │  moondream,      │                                           │
│  │  llava, etc.)    │                                           │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ FFmpeg           │ → Extract keyframes                      │
│  └──────────────────┘                                           │
│  ┌──────────────────┐                                           │
│  │ Python asyncio   │ → Async processing                       │
│  └──────────────────┘                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Example

```
Example: Processing a Section about Differential Equations

┌────────────────────────────────────────────────────────────────┐
│  INPUT                                                         │
├────────────────────────────────────────────────────────────────┤
│  Section: {                                                    │
│    "id": "cauchy_lipschitz",                                   │
│    "title": "Cauchy-Lipschitz Theorem",                       │
│    "narration": "The Cauchy-Lipschitz theorem states...",     │
│    "visual_description": "Show theorem statement and proof",  │
│    "duration_seconds": 45                                      │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  STEP 1: Generate Manim Code (Gemini)                         │
├────────────────────────────────────────────────────────────────┤
│  Generated: scene_0.py with CauchyLipschitz(Scene) class      │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  STEP 2: Render Video (Manim)                                 │
├────────────────────────────────────────────────────────────────┤
│  Output: section_0.mp4 (45 seconds)                           │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  STEP 3: Extract Keyframes (FFmpeg)                           │
├────────────────────────────────────────────────────────────────┤
│  Extracted 5 frames at:                                        │
│  • frame_00.png (t=7.5s)   - Intro                            │
│  • frame_01.png (t=15s)    - Theorem statement                │
│  • frame_02.png (t=22.5s)  - Key equations                    │
│  • frame_03.png (t=30s)    - Proof steps                      │
│  • frame_04.png (t=37.5s)  - Conclusion                       │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  STEP 4: Analyze Frames (Vision LLM)                          │
├────────────────────────────────────────────────────────────────┤
│  Result: {                                                     │
│    "status": "issues",                                         │
│    "description": "Title overlapping with theorem equation",  │
│    "issues": [                                                 │
│      {                                                         │
│        "severity": "critical",                                 │
│        "type": "overlap",                                      │
│        "description": "Title text collides with theorem box", │
│        "frame_indices": [1, 2],                                │
│        "suggestion": "Use .next_to() with buff=0.8"           │
│      }                                                         │
│    ]                                                           │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  STEP 5: Generate Fix (Vision LLM)                            │
├────────────────────────────────────────────────────────────────┤
│  Fixed Code:                                                   │
│  - Changed: theorem.next_to(title, DOWN)                      │
│  - To: theorem.next_to(title, DOWN, buff=0.8)                 │
│  - Also: title.to_edge(UP, buff=0.5)                          │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  STEP 6: Re-render (Manim)                                    │
├────────────────────────────────────────────────────────────────┤
│  New Output: section_0.mp4 (with fixes)                       │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  STEP 7: QC Again (Iteration 2)                               │
├────────────────────────────────────────────────────────────────┤
│  Result: {                                                     │
│    "status": "ok",                                             │
│    "description": "Visuals are clear and well-organized",     │
│    "issues": []                                                │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│  OUTPUT                                                        │
├────────────────────────────────────────────────────────────────┤
│  Video: section_0.mp4 ✓ (Quality Approved)                    │
│  Code:  scene_0.py (Fixed version)                            │
│  Time:  ~90 seconds total (including fix iteration)           │
└────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
manimagain/
├── backend/
│   ├── app/
│   │   └── services/
│   │       ├── manim_generator.py      ← Modified (QC integration)
│   │       ├── visual_qc.py            ← NEW (QC implementation)
│   │       ├── video_generator_v2.py   (Uses manim_generator)
│   │       └── ...
│   └── requirements.txt                ← Modified (added ollama)
│
├── VISUAL_QC_README.md                 ← NEW (User guide)
├── VISUAL_QC_CONFIG_EXAMPLES.md        ← NEW (Config cookbook)
├── VISUAL_QC_IMPLEMENTATION.md         ← NEW (Implementation doc)
├── VISUAL_QC_ARCHITECTURE.md           ← NEW (This file)
├── test_visual_qc.py                   ← NEW (Test suite)
└── README.md                           ← Modified (Added QC feature)
```
