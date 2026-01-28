"""
Tests for app.services.use_cases.base
"""

import pytest
from app.services.use_cases.base import UseCase


class TestUseCase:
    """Test the UseCase abstract base class."""

    def test_cannot_instantiate_abstract(self):
        """Verify UseCase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            UseCase()

    def test_concrete_implementation(self):
        """Verify concrete implementation works."""
        class MockRequest: pass
        class MockResponse: pass
        
        class ConcreteUseCase(UseCase[MockRequest, MockResponse]):
            async def execute(self, request: MockRequest) -> MockResponse:
                return MockResponse()
        
        # This should not raise TypeError
        use_case = ConcreteUseCase()
        assert isinstance(use_case, UseCase)

    @pytest.mark.asyncio
    async def test_execute_called(self):
        """Verify execute method is callable as expected."""
        class MyUseCase(UseCase[str, int]):
            async def execute(self, request: str) -> int:
                return len(request)
        
        use_case = MyUseCase()
        result = await use_case.execute("hello")
        assert result == 5
