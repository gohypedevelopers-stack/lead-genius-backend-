import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class Lead(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id") # Should link to organization
    
    campaign_id: Optional[uuid.UUID] = Field(default=None) # Link to campaign
    
    name: str = Field(index=True)
    linkedin_url: str = Field(index=True)
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    score: int = Field(default=0)
    status: str = Field(default="new") # new, contacted, replied, qualified, closed
    source: str = Field(default="manual")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Enrichment fields
    location: Optional[str] = None
    company_size: Optional[str] = None
    work_email: Optional[str] = None
    personal_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    twitter_handle: Optional[str] = None
    is_email_verified: bool = Field(default=False)
    enrichment_status: str = Field(default="pending") # pending, enriched, failed
