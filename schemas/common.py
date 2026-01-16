"""
Common schemas used across multiple endpoints.
"""
from typing import TypeVar, Generic, List, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    
    class Config:
        json_schema_extra = {"example": {"message": "Operation successful"}}


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str
    
    class Config:
        json_schema_extra = {"example": {"detail": "An error occurred"}}


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int
    has_next: bool
    has_prev: bool


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
