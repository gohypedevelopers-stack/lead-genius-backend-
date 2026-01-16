"""
Pagination utilities for Lead Genius API.
Provides consistent pagination across all list endpoints.
"""
from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = 1
    limit: int = 20
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit
    
    class Config:
        json_schema_extra = {
            "example": {"page": 1, "limit": 20}
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int
    has_next: bool
    has_prev: bool
    
    class Config:
        from_attributes = True


def create_paginated_response(
    items: List[T], 
    total: int, 
    page: int, 
    limit: int
) -> dict:
    """
    Create a paginated response dictionary.
    
    Args:
        items: List of items for current page
        total: Total count of all items
        page: Current page number
        limit: Items per page
    
    Returns:
        Dictionary with pagination metadata
    """
    pages = (total + limit - 1) // limit if limit > 0 else 0
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1
    }


async def paginate_query(
    session: AsyncSession,
    query,
    model,
    page: int = 1,
    limit: int = 20
) -> dict:
    """
    Execute a paginated query.
    
    Args:
        session: Database session
        query: SQLModel select query
        model: Model class for counting
        page: Page number (1-indexed)
        limit: Items per page
    
    Returns:
        Paginated response dictionary
    """
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.exec(count_query)
    total = total_result.one()
    
    # Apply pagination
    offset = (page - 1) * limit
    paginated_query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await session.exec(paginated_query)
    items = result.all()
    
    return create_paginated_response(items, total, page, limit)
