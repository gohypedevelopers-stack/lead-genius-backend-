"""
Persona model - ideal customer profile matching.
Rule-based lead qualification.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class Persona(SQLModel, table=True):
    """
    Persona/ICP definition for lead qualification.
    Contains rules for matching leads.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    
    # Persona info
    name: str = Field(index=True)
    description: Optional[str] = None
    
    # Priority for scoring (higher priority personas give more points)
    priority: int = Field(default=1)  # 1-10
    
    # Matching rules (JSONB for flexibility)
    rules_json: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    # Example rules: {
    #   "title_keywords": ["manager", "director", "vp"],
    #   "title_exclude": ["intern", "junior"],
    #   "company_size_min": 50,
    #   "company_size_max": 500,
    #   "industries": ["technology", "saas"],
    #   "locations": ["United States", "Canada"]
    # }
    
    # Score contribution when matched
    score_bonus: int = Field(default=50)
    
    # Status
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
