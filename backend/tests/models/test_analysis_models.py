
from app.models.analysis import AnalysisRequest, AnalysisResult, TopicSuggestion

def test_analysis_request():
    req = AnalysisRequest(file_id="123")
    assert req.file_id == "123"

def test_analysis_result_structure():
    suggestion = TopicSuggestion(
        index=1,
        title="Topic 1",
        description="Desc",
        estimated_duration=60,
        complexity="beginner",
        subtopics=["sub1"],
        prerequisites=[],
        learning_objectives=[]
    )
    
    res = AnalysisResult(
        file_id="f1",
        analysis_id="a1",
        summary="Sum",
        main_subject="Math",
        difficulty_level="Easy",
        key_concepts=["A", "B"],
        detected_math_elements=5,
        suggested_topics=[suggestion]
    )
    
    assert res.file_id == "f1"
    assert len(res.suggested_topics) == 1
    assert res.suggested_topics[0].complexity == "beginner"
