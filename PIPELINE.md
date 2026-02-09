# EduViz Pipeline

Visual guide to how EduViz transforms documents into educational videos.

For setup instructions, see the [Backend README](backend/README.md) and [Frontend README](frontend/README.md).
For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## End-to-End Flow

From document upload to final video — the complete journey through EduViz.

```mermaid
flowchart TD
    subgraph Input
        Upload["Upload Document\n(PDF, Text, Image)"]
    end

    subgraph ContentAnalysis["1 · Content Analysis"]
        Extract["Extract & analyze content"]
        Topics["Generate topic suggestions"]
        Extract --> Topics
    end

    subgraph UserConfig["2 · User Configuration"]
        Select["Select topics & reorder"]
        Config["Set depth, language,\nvoice, theme"]
        Select --> Config
    end

    subgraph ScriptGen["3 · Script Generation"]
        Script["Generate narration per section"]
        Segment["Segment with timing"]
        Script --> Segment
    end

    subgraph Production["4 · Section Production (parallel per section)"]
        direction LR
        Animation["Animation\nGeneration"]
        Audio["TTS Audio\nSynthesis"]
    end

    subgraph Assembly["5 · Video Assembly"]
        Combine["Merge video + audio\nper section"]
        Concat["Concatenate sections"]
        Thumb["Generate thumbnails"]
        Combine --> Concat --> Thumb
    end

    Upload --> ContentAnalysis
    ContentAnalysis --> UserConfig
    UserConfig --> ScriptGen
    ScriptGen --> Production
    Production --> Assembly
    Assembly --> Result["Final Video"]
```

---

## Animation Generation Pipeline

Each section goes through a 3-stage agentic pipeline managed by `AnimationOrchestrator`, with a separate rendering step in `ManimGenerator`.

```mermaid
flowchart TD
    Section["Section input\n(narration, duration, theme)"]

    subgraph Choreo["Stage 1 · Choreography"]
        ChoreoIn["Analyze narration content"]
        ChoreoOut["Output: structured visual plan\n(elements, timing, transitions)"]
        ChoreoIn --> ChoreoOut
    end

    subgraph Impl["Stage 2 · Implementation"]
        ImplIn["Convert plan → Manim Python code"]
        ImplTheme["Inject theme styling"]
        ImplIn --> ImplTheme
    end

    subgraph Refine["Stage 3 · Refinement"]
        Loop["Validate → Triage → Fix cycle\n(up to 5 iterations)"]
    end

    subgraph Render["Stage 4 · Rendering"]
        Exec["Execute Manim → MP4"]
        VisionPost["Post-render Vision QC"]
        Exec --> VisionPost
    end

    Section --> Choreo
    Choreo --> Impl
    Impl --> Refine
    Refine -->|valid| Render
    Refine -->|max retries exceeded| Retry["Retry from Stage 1\n(up to 2 clean retries)"]
    Retry --> Choreo
    Render --> Done["Video segment + thumbnail"]
```

**Real class ownership:**

| Stage | Class | File |
|:---|:---|:---|
| Choreography | `Choreographer` | `stages/choreographer.py` |
| Implementation | `Implementer` | `stages/implementer.py` |
| Refinement | `Refiner` | `stages/refiner.py` |
| Orchestration | `AnimationOrchestrator` | `orchestrator.py` |
| Rendering + Vision QC | `ManimGenerator` | `generator.py` |

---

## Refinement: The Certain / Uncertain Model

The `Refiner` uses a triage model to classify validation issues as **certain** (definitely broken) or **uncertain** (might be a false positive). The `FalsePositiveWhitelist` is checked first so previously confirmed false positives are never re-evaluated.

```mermaid
flowchart TD
    Code["Generated Manim code"]

    Static["Static Validation\n(syntax, imports, forbidden patterns)"]
    CST["CSTFixer\n(deterministic transforms)"]
    Runtime["Runtime Validation\n(execute code, catch errors)"]
    Spatial["Spatial Validation\n(overlaps, bounds, visibility)"]

    WL{"Check\nFalsePositiveWhitelist"}
    Triage{"Triage remaining issues"}

    CertainFix["AdaptiveFixerAgent\n(LLM surgical edits)"]
    Defer["Defer uncertain issues\nto post-render Vision QC"]

    Code --> Static
    Static -->|errors| CertainFix
    Static -->|pass| CST
    CST --> Runtime
    Runtime -->|errors| CertainFix
    Runtime -->|pass| Spatial
    Spatial -->|no issues| Valid["✓ Code validated"]
    Spatial -->|issues found| WL

    WL -->|"known false positive"| Skip["Skip\n(already verified)"]
    WL -->|"not in whitelist"| Triage

    Triage -->|"certain"| CertainFix
    Triage -->|"uncertain"| Defer

    CertainFix --> Code
    Skip --> Valid
    Defer --> Valid

    style Valid fill:#d4edda,stroke:#28a745
    style CertainFix fill:#fff3cd,stroke:#856404
    style Defer fill:#e2e3e5,stroke:#6c757d
    style WL fill:#e2e3e5,stroke:#6c757d
```

### Post-Render Vision QC

After rendering, `ManimGenerator._run_vision_verification` resolves the deferred uncertain issues. The result feeds back into the whitelist for future iterations.

```mermaid
flowchart TD
    Render["Render MP4"]
    Extract["Extract frames at\nissue timestamps"]
    Gemini["Gemini Vision\nanalyzes frames"]
    Verdict{"Verdict\nper issue"}

    Fix["Apply fix via Refiner\n+ re-render once"]
    AddWL["Add to FalsePositiveWhitelist\n(skipped in future iterations)"]

    Render --> Extract --> Gemini --> Verdict
    Verdict -->|"confirmed real"| Fix
    Verdict -->|"false positive"| AddWL

    style Fix fill:#fff3cd,stroke:#856404
    style AddWL fill:#d4edda,stroke:#28a745
```

**Key components in `refinement/`:**

| Component | Responsibility |
|:---|:---|
| `CSTFixer` | Deterministic code transforms via libcst (indentation, imports, bounds clamping) |
| `AdaptiveFixerAgent` | LLM-based surgical edits with strategy selection and failure memory |
| `IssueRouter` | Classifies issues as certain vs uncertain |
| `IssueVerifier` | Sends uncertain issues to Gemini Vision for confirmation |
| `FalsePositiveWhitelist` | Tracks confirmed false positives — checked before triage to skip known non-issues |

---

## Validation Layers

Four validation layers run in sequence. Each catches a different class of errors.

| Layer | File | What it catches | How it works |
|:---|:---|:---|:---|
| **Static** | `static.py` | Syntax errors, missing imports, forbidden patterns (file I/O, subprocess, network) | AST parsing + pattern matching |
| **Runtime** | `runtime.py` | `NameError`, `AttributeError`, `ImportError`, execution crashes | Executes code in isolated subprocess |
| **Spatial** | `spatial.py` | Object overlaps, out-of-bounds elements, hidden objects, text-on-text collisions | Manim dry-run with injected spatial checks |
| **Vision** | `vision.py` | Color contrast issues, readability, visual alignment | Gemini Vision analyzes rendered screenshots |

---

## Available Themes

Themes control background color, text defaults, and accent palette. Defined in `animation/config.py`.

| Theme | Background | Text | Accents |
|:---|:---|:---|:---|
| **3Blue1Brown** (default) | `#171717` | `#FFFFFF` | `#58C4DD` `#83C167` `#FFC857` `#FF6B6B` |
| **Clean White** | `#FFFFFF` | `#111111` | `#1D4ED8` `#0F766E` `#D97706` `#DC2626` |
| **Dracula** | `#282A36` | `#F8F8F2` | `#8BE9FD` `#50FA7B` `#FFB86C` `#FF5555` |
| **Solarized Dark** | `#002B36` | `#EEE8D5` | `#268BD2` `#2AA198` `#B58900` `#DC322F` |
| **Nord** | `#2E3440` | `#ECEFF4` | `#88C0D0` `#A3BE8C` `#EBCB8B` `#BF616A` |

---

## AI Model Configuration

Models are configurable per pipeline stage via `config/models.py` and exposed through the `/pipelines` API endpoint.

| Pipeline Stage | Purpose | Default Model |
|:---|:---|:---|
| Content Analysis | Extract topics from documents | Gemini Flash |
| Script Generation | Write narration scripts | Gemini Flash |
| Choreography | Plan visual elements & timing | Gemini Flash Thinking |
| Implementation | Generate Manim code | Gemini Flash |
| Refinement | Fix validation errors | Gemini Flash |

---

## Technology Stack

| Layer | Technologies |
|:---|:---|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, React Router, Axios |
| **Backend** | FastAPI, Python 3.12+, Uvicorn, Pydantic |
| **AI** | Google Gemini API / Vertex AI, Edge TTS (Gemini TTS experimental) |
| **Animation** | Manim, FFmpeg, libcst |
| **Infrastructure** | Docker, Nginx |
