"""
Services package - Core business logic and integrations

Organized by domain responsibility:

Pipeline (Core Video Generation Flow):
    - pipeline/content_analysis: Material analysis (PDF, images, text)
    - pipeline/script_generation: Modular video script creation
    - pipeline/animation: Animation generation, correction, and QC
    - pipeline/audio: Text-to-speech
    - pipeline/assembly: Video rendering and assembly
    
Infrastructure (Technical Concerns):
    - infrastructure/llm: LLM integration (Gemini, prompting, cost tracking)
    - infrastructure/storage: Data persistence
    - infrastructure/orchestration: Job management
    - infrastructure/parsing: JSON/code parsing utilities

Features (Secondary Capabilities):
    - features/translation: Video translation

Use Cases (Application Layer):
    - use_cases: Business logic orchestration

Architecture Principles:
    - Single Responsibility: Each module/file does one thing
    - Dependency Injection: Services accept dependencies
    - Async-first: All I/O operations use async/await
    - Error Recovery: Robust error handling and fallbacks
    - Cost Tracking: Integrated cost monitoring
"""

# Main entry points
from .pipeline.content_analysis import MaterialAnalyzer
from .pipeline.script_generation import ScriptGenerator
from .infrastructure.orchestration import JobManager

__all__ = [
    "MaterialAnalyzer",
    "ScriptGenerator",
    "JobManager",
]
