"""
Campaign model - lead generation campaign management.
Enhanced with pause/resume and analytics support.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class Campaign(SQLModel, table=True):
    """
    Campaign entity - represents a lead generation campaign.
    Supports various types: social, group, search, csv.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    
    # Basic info
    name: str = Field(index=True)
    description: Optional[str] = None
    
    # Type and status
    type: str = Field(index=True)  # social, group, search, csv
    status: str = Field(default="draft", index=True)  # draft, active, paused, processing, completed, failed
    
    # Campaign settings (flexible JSONB)
    settings: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    # Example settings: {
    #   "keywords": ["software engineer"],
    #   "location": "San Francisco",
    #   "target_count": 100,
    #   "filters": {...}
    # }
    
    # Analytics
    leads_count: int = Field(default=0)
    qualified_leads_count: int = Field(default=0)
    contacted_count: int = Field(default=0)
    replied_count: int = Field(default=0)
    
    # Scheduling
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Pause/Resume
    paused_at: Optional[datetime] = None
    last_resumed_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
