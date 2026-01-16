"""
Scoring models - configurable lead scoring rules.
Allows dynamic scoring configuration per organization.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class ScoringRule(SQLModel, table=True):
    """
    Individual scoring rule for lead qualification.
    Allows building custom scoring systems.
    """
    __tablename__ = "scoring_rule"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    
    # Rule info
    name: str = Field(index=True)
    description: Optional[str] = None
    
    # Rule definition
    field: str  # lead field to evaluate: title, company_size, location, enrichment_status, etc.
    operator: str  # contains, equals, greater_than, less_than, in, not_in, exists, not_exists
    value: str  # value to compare against (can be JSON for 'in' operator)
    
    # Score impact
    score_delta: int = Field(default=10)  # Can be negative for deductions
    
    # Priority (higher priority rules evaluated first)
    priority: int = Field(default=1)
    
    # Status
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Default scoring rules that can be copied for new organizations
DEFAULT_SCORING_RULES = [
    {"name": "Has Title", "field": "title", "operator": "exists", "value": "", "score_delta": 10},
    {"name": "Has Email", "field": "email", "operator": "exists", "value": "", "score_delta": 15},
    {"name": "Email Verified", "field": "is_email_verified", "operator": "equals", "value": "true", "score_delta": 20},
    {"name": "Enriched", "field": "enrichment_status", "operator": "equals", "value": "enriched", "score_delta": 30},
    {"name": "Manager Title", "field": "title", "operator": "contains", "value": "manager", "score_delta": 20},
    {"name": "Director Title", "field": "title", "operator": "contains", "value": "director", "score_delta": 25},
    {"name": "VP Title", "field": "title", "operator": "contains", "value": "vp", "score_delta": 30},
]
