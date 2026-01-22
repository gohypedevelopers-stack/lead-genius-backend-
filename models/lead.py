"""
Lead model - core entity for lead generation.
Enhanced with tags and proper timestamps.
"""
import uuid
from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class Lead(SQLModel, table=True):
    """
    Lead entity - represents a potential customer/contact.
    Scoped to organization and optionally to a campaign.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    campaign_id: Optional[uuid.UUID] = Field(default=None, foreign_key="campaign.id", index=True)
    
    # Basic info
    name: str = Field(index=True)
    linkedin_url: str = Field(index=True)
    title: Optional[str] = None
    company: Optional[str] = Field(default=None, index=True)
    
    # Contact info
    email: Optional[str] = Field(default=None, index=True)
    work_email: Optional[str] = None
    personal_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    
    # Phone numbers (Apollo enrichment)
    phone_numbers: List[dict] = Field(default=[], sa_column=Column(JSONB))
    # Example: [{"number": "+1234567890", "type": "mobile", "verified": true}]
    
    # Social
    twitter_handle: Optional[str] = None
    
    # Location
    location: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    
    # Company info (from enrichment)
    company_size: Optional[str] = None
    company_industry: Optional[str] = None
    company_website: Optional[str] = None
    
    # Qualification
    score: int = Field(default=0, index=True)
    status: str = Field(default="new", index=True)  # new, contacted, replied, qualified, closed, lost
    
    # Source tracking
    source: str = Field(default="manual", index=True)  # manual, linkedin, csv, campaign
    
    # Enrichment
    is_email_verified: bool = Field(default=False)
    enrichment_status: str = Field(default="pending")  # pending, enriched, failed
    enriched_at: Optional[datetime] = None
    
    # Apollo.io specific enrichment
    apollo_enriched_at: Optional[datetime] = None
    apollo_match_confidence: Optional[float] = None  # 0-1
    apollo_credits_used: int = Field(default=0)
    
    # Tags for organization
    tags: List[str] = Field(default=[], sa_column=Column(JSONB))
    
    # Custom data (for flexibility)
    custom_fields: dict = Field(default={}, sa_column=Column(JSONB))
    
    # Notes
    notes: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_contacted_at: Optional[datetime] = None
