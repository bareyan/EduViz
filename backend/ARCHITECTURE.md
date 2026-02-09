# Backend Architecture

**Deep Dive into EduViz Backend Design**

For a high-level system overview, see [Root Architecture](../ARCHITECTURE.md).

---

## Directory Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── config/                    # Configuration management
│   ├── core/                      # Core utilities (logging, auth, context)
│   ├── models/                    # Pydantic data models
│   ├── routes/                    # API endpoints (thin controllers)
│   │   ├── upload.py
│   │   ├── analysis.py
│   │   ├── generation.py
│   │   ├── jobs.py
│   │   ├── sections.py
│   │   └── translation.py
│   └── services/
│       ├── infrastructure/        # Generic, reusable capabilities
│       │   ├── llm/              # LLM integration
│       │   ├── parsing/          # JSON/code parsing
│       │   ├── storage/          # File management
│       │   └── orchestration/    # Lifecycle management
│       └── pipeline/             # Business logic
│           ├── content_analysis/ # PDF/text/image analysis
│           ├── script_generation/# Narration script creation
│           ├── animation/        # Manim animation generation
│           ├── audio/            # TTS synthesis
│           └── assembly/         # Video composition
```

## Layer Responsibilities

### 1. Infrastructure Layer (`services/infrastructure/`)

**Purpose**: Generic, reusable capabilities independent of business logic.

- **LLM Layer** (`llm/`)
  - `PromptingEngine` - Single point for all LLM interactions
  - `CostTracker` - Monitor token usage and costs
  - `gemini/client.py` - Unified client for Gemini API and Vertex AI

- **Parsing Layer** (`parsing/`)
  - `json_parser.py` - JSON extraction with error recovery
  - `code_parser.py` - Code block extraction and validation

- **Storage Layer** (`storage/`)
  - File management and organization

- **Orchestration Layer** (`orchestration/`)
  - Lifecycle management and startup coordination

**Rule**: Never call LLM APIs directly - always use `PromptingEngine`.

### 2. Pipeline Layer (`services/pipeline/`)

**Purpose**: Business logic for content transformation stages.

- **Content Analysis** (`content_analysis/`)
  - Analyzes PDFs, text files, images
  - Extracts educational structure
  - Returns structured topic suggestions

- **Script Generation** (`script_generation/`)
  - Converts topics into narration scripts
  - Segments narration for audio sync
  - Uses `BaseScriptGenerator` for shared utilities

- **Animation Generation** (`animation/`)
  - **Unified Agent Architecture**: Single orchestrator manages lifecycle
  - **Segmented Generation**: Creates code piece-by-piece
  - **Tool-Based Refinement**: Uses surgical edits, not full regeneration
  - **Fail-Fast**: Raises specific exceptions

- **Audio Synthesis** (`audio/`)
  - Gemini TTS integration
  - Multiple voice support

- **Video Assembly** (`assembly/`)
  - FFmpeg-based composition
  - Thumbnail generation

### 3. Routes Layer (`routes/`)

**Purpose**: Thin API controllers that orchestrate services.

**Rule**: Routes should be <50 lines, delegating work to services. No business logic in routes.

## Animation Pipeline (Detailed)

### Stage 1: Choreography (Visual Planning)

**Location**: `pipeline/animation/generation/stages/choreographer.py`

**Process**:
- Analyzes narration content and duration
- Uses Gemini AI to plan visual elements
- Determines timing and transitions
- Outputs structured choreography plan

**Model**: Gemini 2.0 Flash Thinking (planning-optimized)

### Stage 2: Implementation (Code Generation)

**Location**: `pipeline/animation/generation/stages/implementer.py`

**Process**:
- Converts choreography plan to Manim Python code
- Applies theme-specific styling
- Ensures timing synchronization

**Model**: Gemini 2.0 Flash (generation-optimized)

### Stage 3: Refinement (Validation & Fixing)

**Location**: `pipeline/animation/generation/stages/refiner.py`

Multi-layer validation architecture:

#### Static Validation
- Syntax checking (AST parsing)
- Import verification
- Forbidden pattern detection (file I/O, network, subprocess)
- Type checking with Pyright (optional)

#### Runtime Validation
- Execution error detection
- Undefined name resolution
- Import dependency verification

#### Spatial Validation
- Object overlap detection
- Boundary checking (within frame)
- Visibility verification
- Z-index conflict detection

#### Vision Validation
**Key Innovation**: Uses Gemini Vision to verify uncertain spatial issues
- Captures actual video screenshots
- LLM analyzes visual quality
- Confirms real issues vs. false positives
- Updates whitelist dynamically

#### Adaptive Fixing
- **Deterministic Fixes**: CST (Concrete Syntax Tree) transformations for common issues
- **LLM-Based Fixes**: Surgical edits for complex problems
- **Incremental Refinement**: Validates after each fix

**Validation Flow**:
```
Code → Static → Runtime → Spatial → Vision QC
         ↓        ↓         ↓          ↓
      Fix/Retry Fix/Retry Fix/Retry Fix/Retry
```

### Stage 4: Rendering (Production)

**Location**: `pipeline/animation/generation/core/renderer.py`

**Process**:
- Executes validated Manim code
- Renders MP4 video segments
- Generates thumbnails for gallery
- Post-render visual quality checks

## Error Handling

### Exception Hierarchy

```python
PipelineError (Base)
├── AnalysisError
├── ScriptGenerationError
└── AnimationError
    ├── ChoreographyError
    ├── ImplementationError
    ├── RefinementError
    └── RenderingError
```

**Rule**: Fail-fast with specific context. Never silent failures.

## Configuration

See [ENVIRONMENT.md](ENVIRONMENT.md) for detailed configuration options.

### AI Backend Options

1. **Gemini API** (Default): API key-based, easy setup
2. **Vertex AI** (Enterprise): GCP project-based, production-grade

## Performance Optimizations

- **Cost Tracking**: Per-request LLM token monitoring
- **Caching**: Type module caching for LLM clients
- **Sampling**: Representative sampling for large documents (15K char limit)
- **Parallel Processing**: Concurrent section generation
