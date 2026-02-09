# EduViz System Architecture

**High-Level Overview**

This document provides a bird's-eye view of the EduViz system architecture. For detailed component-level documentation, see:
- [Backend Architecture](backend/ARCHITECTURE.md) - Deep dive into services, pipeline, and validation
- [Frontend Architecture](frontend/ARCHITECTURE.md) - Component structure and state management

---

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│              React + TypeScript + Vite                      │
│                    (Port 3000)                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/REST
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                         Backend                             │
│                   FastAPI + Python                          │
│                    (Port 8000)                              │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                    Routes Layer                       │ │
│  │         (Thin API controllers)                        │ │
│  └───────────────────────────────────────────────────────┘ │
│                            │                                │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                   Pipeline Layer                      │ │
│  │  • Content Analysis  • Script Generation              │ │
│  │  • Animation         • Audio Synthesis                │ │
│  │  • Video Assembly                                     │ │
│  └───────────────────────────────────────────────────────┘ │
│                            │                                │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                Infrastructure Layer                   │ │
│  │  • LLM Integration   • Parsing Utilities              │ │
│  │  • Storage           • Orchestration                  │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  External APIs   │
                  │  • Gemini AI     │
                  │  • Gemini TTS    │
                  └──────────────────┘
```

## Technology Stack

### Backend
- **FastAPI** - Web framework
- **Manim** - Animation engine
- **Google Gemini** - AI/LLM
- **Gemini TTS** - Text-to-speech
- **FFmpeg** - Video processing

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling

## Core Pipeline (High-Level)

EduViz transforms documents into videos through a 4-stage AI-driven pipeline:

1. **Choreography** - AI plans visual elements and timing
2. **Implementation** - Generates Manim animation code
3. **Refinement** - Multi-layer validation and fixing
4. **Rendering** - Produces final video segments

For technical details on the pipeline stages, validation layers, and adaptive fixing, see [Backend Architecture](backend/ARCHITECTURE.md).

## Design Principles

- **Clean Architecture** - Infrastructure → Pipeline → Routes separation
- **Single Responsibility** - Each module has one clear purpose
- **Fail-Fast** - Specific exceptions with actionable error messages
- **DRY Principle** - Zero code duplication tolerance
