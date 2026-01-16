"""
Scoring schemas.
"""
import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ScoringRuleCreate(BaseModel):
    """Create a scoring rule."""
    name: str
    description: Optional[str] = None
    field: str
    operator: str  # contains, equals, greater_than, less_than, in, not_in, exists, not_exists
    value: str
    score_delta: int = 10
    priority: int = 1
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Manager Title Bonus",
                "field": "title",
                "operator": "contains",
                "value": "manager",
                "score_delta": 20,
                "priority": 1
            }
        }


class ScoringRuleUpdate(BaseModel):
    """Update a scoring rule."""
    name: Optional[str] = None
    description: Optional[str] = None
    field: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[str] = None
    score_delta: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class ScoringRuleResponse(BaseModel):
    """Scoring rule response."""
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    field: str
    operator: str
    value: str
    score_delta: int
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RecalculateRequest(BaseModel):
    """Request to recalculate lead scores."""
    lead_ids: Optional[list[uuid.UUID]] = None  # None means all leads


class RecalculateResponse(BaseModel):
    """Result of score recalculation."""
    total_updated: int
    avg_score_before: float
    avg_score_after: float
