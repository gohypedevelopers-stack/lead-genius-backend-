"""
Campaign schemas.
"""
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class CampaignCreate(BaseModel):
    """Create a new campaign."""
    name: str
    description: Optional[str] = None
    type: str  # social, group, search, csv
    settings: Optional[Dict[str, Any]] = {}
    scheduled_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "LinkedIn Tech Leads Q1",
                "type": "social",
                "settings": {
                    "keywords": ["software engineer", "developer"],
                    "location": "San Francisco Bay Area",
                    "target_count": 100
                }
            }
        }


class CampaignUpdate(BaseModel):
    """Update an existing campaign."""
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None


class CampaignResponse(BaseModel):
    """Campaign response."""
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    type: str
    status: str
    settings: Dict[str, Any]
    leads_count: int
    qualified_leads_count: int
    contacted_count: int
    replied_count: int
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    paused_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    """Campaign statistics."""
    campaign_id: uuid.UUID
    leads_count: int
    qualified_leads_count: int
    contacted_count: int
    replied_count: int
    avg_score: float
    conversion_rate: float
    top_sources: list
    leads_by_status: dict
