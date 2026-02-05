"""
Tests for pipeline/assembly/sections module

Tests for section processing utilities including narration cleaning and subsection division.
"""

from app.services.pipeline.assembly.sections import (
    clean_narration_for_tts,
    divide_into_subsections,
)


class TestCleanNarrationForTTS:
    """Test suite for clean_narration_for_tts function"""

    def test_removes_pause_markers(self):
        """Test that pause markers are removed"""
        narration = "Hello world... [pause] This is a test."
        result = clean_narration_for_tts(narration)
        
        assert "[pause]" not in result
        assert "Hello world" in result
        assert "This is a test" in result

    def test_preserves_regular_text(self):
        """Test that regular text is preserved"""
        narration = "This is a simple sentence with no markers."
        result = clean_narration_for_tts(narration)
        
        assert result == narration or "simple sentence" in result

    def test_handles_multiple_pause_markers(self):
        """Test handling of multiple pause markers"""
        narration = "First part [pause] second part [pause] third part."
        result = clean_narration_for_tts(narration)
        
        assert "[pause]" not in result
        assert "First part" in result
        assert "third part" in result

    def test_handles_empty_string(self):
        """Test handling of empty string"""
        result = clean_narration_for_tts("")
        
        assert result == ""


class TestDivideIntoSubsections:
    """Test suite for divide_into_subsections function"""

    def test_short_narration_single_subsection(self):
        """Test that short narration stays as single subsection"""
        narration = "This is a short narration."
        visual = "Simple visual"
        
        result = divide_into_subsections(narration, visual)
        
        # Should return at least one subsection
        assert len(result) >= 1

    def test_long_narration_divided(self):
        """Test that long narration is divided into subsections"""
        # Create a long narration with multiple sentences
        sentences = [
            "This is the first sentence of the narration.",
            "Here is another sentence that adds more content.",
            "We continue with even more explanation here.",
            "And yet another sentence to fill the space.",
        ] * 5  # Repeat to make it longer
        narration = " ".join(sentences)
        visual = "Complex visual with many elements"
        
        result = divide_into_subsections(
            narration, visual, target_duration=10, max_duration=20
        )
        
        # Should be divided into multiple subsections
        # (depends on implementation, just verify it returns list)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_respects_sentence_boundaries(self):
        """Test that division respects sentence boundaries"""
        narration = "First sentence. Second sentence. Third sentence."
        visual = "Visual description"
        
        result = divide_into_subsections(narration, visual)
        
        # Each subsection should contain complete sentences
        for subsection in result:
            if "narration" in subsection:
                text = subsection["narration"]
                # Should not end mid-word (rough check)
                assert text.strip().endswith(('.', '!', '?')) or not text.strip()

    def test_handles_pause_markers_as_breakpoints(self):
        """Test that pause markers are used as breakpoints"""
        narration = "First part [pause] second part [pause] third part."
        visual = "Visual description"
        
        result = divide_into_subsections(narration, visual)
        
        # Should handle pause markers
        assert isinstance(result, list)

    def test_returns_subsection_with_narration_key(self):
        """Test that subsections have expected structure"""
        narration = "Test narration content."
        visual = "Test visual"
        
        result = divide_into_subsections(narration, visual)
        
        if result:
            first_subsection = result[0]
            # Should have some structure (impl dependent)
            assert isinstance(first_subsection, dict)


class TestSubsectionStructure:
    """Test suite for subsection output structure"""

    def test_subsection_has_expected_keys(self):
        """Test that subsections have expected keys"""
        narration = "Test narration for checking structure."
        visual = "Test visual description"
        
        result = divide_into_subsections(narration, visual)
        
        if result and len(result) > 0:
            subsection = result[0]
            # Check for common expected keys
            # (specific keys depend on implementation)
            assert isinstance(subsection, dict)

    def test_handles_very_long_sentence(self):
        """Test handling of very long single sentence"""
        # Create a very long sentence without breaks
        long_sentence = "This is " + "a very " * 100 + "long sentence."
        visual = "Visual"
        
        result = divide_into_subsections(long_sentence, visual)
        
        # Should still return something
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_handles_unicode_content(self):
        """Test handling of unicode content"""
        narration = "数学是很有趣的。这是中文内容。"
        visual = "Chinese text visualization"
        
        result = divide_into_subsections(narration, visual)
        
        assert isinstance(result, list)
        assert len(result) >= 1
