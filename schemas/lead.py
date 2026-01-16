"""
Lead schemas.
"""
import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr


class LeadCreate(BaseModel):
    """Create a new lead."""
    name: str
    linkedin_url: str
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    location: Optional[str] = None
    tags: Optional[List[str]] = []
    notes: Optional[str] = None
    custom_fields: Optional[dict] = {}
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "linkedin_url": "https://linkedin.com/in/johndoe",
                "title": "Software Engineer",
                "company": "TechCorp",
                "email": "john@techcorp.com",
                "tags": ["hot-lead", "tech"]
            }
        }


class LeadUpdate(BaseModel):
    """Update an existing lead."""
    name: Optional[str] = None
    linkedin_url: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    work_email: Optional[str] = None
    personal_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    twitter_handle: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    custom_fields: Optional[dict] = None


class LeadResponse(BaseModel):
    """Lead response."""
    id: uuid.UUID
    org_id: uuid.UUID
    campaign_id: Optional[uuid.UUID]
    name: str
    linkedin_url: str
    title: Optional[str]
    company: Optional[str]
    email: Optional[str]
    work_email: Optional[str]
    personal_email: Optional[str]
    mobile_phone: Optional[str]
    twitter_handle: Optional[str]
    location: Optional[str]
    country: Optional[str]
    city: Optional[str]
    company_size: Optional[str]
    company_industry: Optional[str]
    score: int
    status: str
    source: str
    is_email_verified: bool
    enrichment_status: str
    enriched_at: Optional[datetime]
    tags: List[str]
    notes: Optional[str]
    custom_fields: dict
    created_at: datetime
    updated_at: datetime
    last_contacted_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class LeadFilter(BaseModel):
    """Lead filtering options."""
    status: Optional[str] = None
    source: Optional[str] = None
    campaign_id: Optional[uuid.UUID] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    enrichment_status: Optional[str] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None  # Search in name, email, company
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


class LeadImportRequest(BaseModel):
    """CSV import request metadata."""
    campaign_id: Optional[uuid.UUID] = None
    source: str = "csv"
    tags: Optional[List[str]] = []


class LeadImportResponse(BaseModel):
    """CSV import result."""
    total_rows: int
    imported: int
    failed: int
    errors: List[dict]


class LeadBulkActionRequest(BaseModel):
    """Bulk action on leads."""
    lead_ids: List[uuid.UUID]
    action: str  # delete, update_status, add_tag, remove_tag
    value: Optional[str] = None  # For status or tag
