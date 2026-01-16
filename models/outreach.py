"""
Outreach models - messages and templates.
Supports scheduled sending, templates, and LinkedIn integration.
"""
import uuid
from datetime import datetime
from typing import Optional, List

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class MessageTemplate(SQLModel, table=True):
    """
    Template for outreach messages.
    Supports variables for personalization.
    """
    __tablename__ = "message_template"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    
    # Template info
    name: str = Field(index=True)
    channel: str = Field(default="linkedin")  # linkedin, email
    subject: Optional[str] = None  # For email
    content: str
    
    # Variables available in template (e.g., ["name", "company", "title"])
    variables: List[str] = Field(default=[], sa_column=Column(JSONB))
    
    # Status
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OutreachMessage(SQLModel, table=True):
    """
    Individual outreach message sent to a lead.
    Tracks status, scheduling, and send method (manual, extension, api).
    """
    __tablename__ = "outreach_message"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    lead_id: uuid.UUID = Field(foreign_key="lead.id", index=True)
    template_id: Optional[uuid.UUID] = Field(default=None, foreign_key="message_template.id")
    
    # Message content
    channel: str = Field(default="linkedin", index=True)  # linkedin, email
    subject: Optional[str] = None  # For email
    message: str
    
    # Send method - how the message will be/was sent
    send_method: str = Field(default="manual", index=True)  # manual, extension, api
    
    # Status
    status: str = Field(default="pending", index=True)  
    # pending, queued, sending, sent, delivered, opened, replied, failed
    
    # LinkedIn tracking (for API integration)
    linkedin_profile_url: Optional[str] = None
    linkedin_message_id: Optional[str] = None  # ID from LinkedIn API
    
    # Scheduling
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = Field(default=0)
    
    # Extension tracking
    extension_session_id: Optional[str] = None  # Track which extension session
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

