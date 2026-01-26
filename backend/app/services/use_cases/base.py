"""
Base use case class following Clean Architecture principles.

Each use case encapsulates a single business operation and is completely
independent of HTTP, database, or other infrastructure details. This enables:

    - Independent testing without mocks or test fixtures
    - Reusability from different contexts (HTTP, CLI, webhooks, etc.)
    - Clear input/output contracts via request/response objects
    - Simple composition and orchestration of multiple use cases

Example:
    Define a use case for uploading files:
    
    >>> class FileUploadUseCase(UseCase[FileUploadRequest, FileUploadResponse]):
    ...     async def execute(self, request: FileUploadRequest) -> FileUploadResponse:
    ...         # Business logic here
    ...         pass
    
    Use it from different contexts:
    
    >>> # In HTTP route
    >>> use_case = FileUploadUseCase()
    >>> response = await use_case.execute(request)
    
    >>> # In CLI
    >>> use_case = FileUploadUseCase()
    >>> response = await use_case.execute(request)
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class UseCase(ABC, Generic[RequestT, ResponseT]):
    """
    Base use case abstract class.
    
    All use cases must inherit from this class and implement the execute() method.
    Use cases should contain pure business logic without any knowledge of HTTP,
    database, or other infrastructure details.
    
    Type Parameters:
        RequestT: Type of the input request object
        ResponseT: Type of the output response object
    
    Example:
        >>> T_Req = TypeVar('T_Req')
        >>> T_Resp = TypeVar('T_Resp')
        >>> class MyUseCase(UseCase[T_Req, T_Resp]):
        ...     async def execute(self, request: T_Req) -> T_Resp:
        ...         # Implementation
        ...         pass
    """

    @abstractmethod
    async def execute(self, request: RequestT) -> ResponseT:
        """
        Execute the use case and return a response.
        
        This method contains all business logic for the operation. It should be
        completely independent of HTTP, database, or other infrastructure details.
        
        Args:
            request: Request object containing all required input data
            
        Returns:
            Response object containing operation results
            
        Raises:
            Exceptions specific to the business logic (e.g., ValidationError,
            NotFoundError, etc.). HTTP exceptions should NOT be raised here;
            that's the route's responsibility to convert to HTTP responses.
        """
        pass
