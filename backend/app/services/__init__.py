"""
Services package - Core business logic and integrations

Organized modules by responsibility:

Core Analysis:
	- analysis: Material analysis (PDF, images, text)
    
Script Generation:
	- script_generation: Modular video script creation with two-phase approach
    
Code Generation & Rendering:
	- manim_generator: Animation code generation
	- video_generator: Video rendering and generation
    
LLM Integration:
	- gemini/: Unified Gemini API client and helpers
    
Support Services:
	- parsing/: JSON/code parsing utilities
	- job_manager: Job status and progress tracking
	- translation_service: Video translation
	- tts_engine: Text-to-speech
	- visual_qc: Video quality control

Architecture Principles:
	- Single Responsibility: Each module/file does one thing
	- Dependency Injection: Services accept dependencies
	- Async-first: All I/O operations use async/await
	- Error Recovery: Robust error handling and fallbacks
	- Cost Tracking: Integrated cost monitoring
"""

# Main entry points
from .analysis import MaterialAnalyzer
from .script_generation import ScriptGenerator
from .job_manager import JobManager

__all__ = [
	"MaterialAnalyzer",
	"ScriptGenerator", 
	"JobManager",
]
