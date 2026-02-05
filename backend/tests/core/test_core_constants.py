"""
Tests for core/constants module

Tests for shared constants including language mappings.
"""

from app.core.constants import LANGUAGE_NAMES, get_language_name


class TestLanguageNames:
    """Test suite for LANGUAGE_NAMES dictionary"""

    def test_language_names_not_empty(self):
        """Test that LANGUAGE_NAMES is populated"""
        assert len(LANGUAGE_NAMES) > 0

    def test_language_names_contains_common_languages(self):
        """Test that common languages are included"""
        expected_languages = ["en", "fr", "es", "de", "zh", "ja", "ko"]
        
        for lang_code in expected_languages:
            assert lang_code in LANGUAGE_NAMES, f"Missing language: {lang_code}"

    def test_language_names_values_are_strings(self):
        """Test that all values are non-empty strings"""
        for code, name in LANGUAGE_NAMES.items():
            assert isinstance(code, str), f"Code should be string: {code}"
            assert isinstance(name, str), f"Name should be string: {name}"
            assert len(name) > 0, f"Name should not be empty for: {code}"

    def test_language_names_codes_are_lowercase(self):
        """Test that all language codes are lowercase"""
        for code in LANGUAGE_NAMES.keys():
            assert code == code.lower(), f"Code should be lowercase: {code}"

    def test_language_names_english(self):
        """Test English language entry"""
        assert LANGUAGE_NAMES.get("en") == "English"

    def test_language_names_armenian(self):
        """Test Armenian language entry (specific to this project)"""
        assert LANGUAGE_NAMES.get("hy") == "Armenian"


class TestGetLanguageName:
    """Test suite for get_language_name function"""

    def test_known_language_code(self):
        """Test getting name for known language code"""
        assert get_language_name("en") == "English"
        assert get_language_name("fr") == "French"
        assert get_language_name("es") == "Spanish"

    def test_unknown_language_code_returns_uppercase(self):
        """Test that unknown codes return uppercase version"""
        result = get_language_name("xyz")
        assert result == "XYZ"

    def test_unknown_language_code_preserves_case_in_uppercase(self):
        """Test unknown code returns proper uppercase"""
        result = get_language_name("abc")
        assert result == "ABC"

    def test_empty_string(self):
        """Test empty string input"""
        result = get_language_name("")
        assert result == ""

    def test_all_known_codes(self):
        """Test all codes in LANGUAGE_NAMES return correct name"""
        for code, expected_name in LANGUAGE_NAMES.items():
            result = get_language_name(code)
            assert result == expected_name, f"Mismatch for {code}: expected {expected_name}, got {result}"
