"""
API schemas for analysis endpoints

Request/Response models for document analysis operations.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class AnalysisRequest(BaseModel):
    """Request to analyze an uploaded file"""
    file_id: str


class TopicSuggestion(BaseModel):
    """A suggested video topic from analysis"""
    index: int
    title: str
    description: str
    estimated_duration: int  # seconds
    complexity: str  # "beginner", "intermediate", "advanced"
    subtopics: List[str]
    prerequisites: List[str]
    learning_objectives: List[str]


class AnalysisResult(BaseModel):
    """Result of analyzing a material"""
    file_id: str
    analysis_id: str
    summary: str
    main_subject: str
    difficulty_level: str
    key_concepts: List[str]
    detected_math_elements: int
    suggested_topics: List[TopicSuggestion]
