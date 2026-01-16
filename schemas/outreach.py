"""
Outreach schemas.
"""
import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


# Message Template schemas
class TemplateCreate(BaseModel):
    """Create a message template."""
    name: str
    channel: str = "linkedin"  # linkedin, email
    subject: Optional[str] = None  # For email
    content: str
    variables: Optional[List[str]] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Initial Outreach",
                "channel": "linkedin",
                "content": "Hi {{name}}, I noticed your work at {{company}}...",
                "variables": ["name", "company"]
            }
        }


class TemplateUpdate(BaseModel):
    """Update a message template."""
    name: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    """Message template response."""
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    channel: str
    subject: Optional[str]
    content: str
    variables: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Outreach Message schemas
class OutreachCreate(BaseModel):
    """Create an outreach message."""
    lead_id: uuid.UUID
    channel: str = "linkedin"
    subject: Optional[str] = None  # For email
    message: str
    template_id: Optional[uuid.UUID] = None
    scheduled_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "lead_id": "550e8400-e29b-41d4-a716-446655440000",
                "channel": "linkedin",
                "message": "Hi John, I noticed your work at TechCorp..."
            }
        }


class OutreachResponse(BaseModel):
    """Outreach message response."""
    id: uuid.UUID
    org_id: uuid.UUID
    lead_id: uuid.UUID
    template_id: Optional[uuid.UUID]
    channel: str
    subject: Optional[str]
    message: str
    status: str
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    replied_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OutreachFilter(BaseModel):
    """Outreach filtering options."""
    lead_id: Optional[uuid.UUID] = None
    channel: Optional[str] = None
    status: Optional[str] = None
    template_id: Optional[uuid.UUID] = None
