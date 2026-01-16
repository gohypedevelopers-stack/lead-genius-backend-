"""
Activity log model - audit trail for all actions.
Enables analytics and debugging.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class ActivityLog(SQLModel, table=True):
    """
    Activity log for tracking all significant actions.
    Used for audit trail, analytics, and dashboard activity feed.
    """
    __tablename__ = "activity_log"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    actor_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id", index=True)
    
    # Action details
    action: str = Field(index=True)  # created, updated, deleted, enriched, contacted, etc.
    entity_type: str = Field(index=True)  # lead, campaign, outreach, user, etc.
    entity_id: Optional[uuid.UUID] = None
    
    # Human-readable description
    description: Optional[str] = None
    
    # Additional metadata
    meta_data: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    # Example: {"old_status": "new", "new_status": "contacted", "lead_name": "John Doe"}
    
    # Request context (for debugging)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Action constants for consistency
class Actions:
    # Lead actions
    LEAD_CREATED = "lead_created"
    LEAD_UPDATED = "lead_updated"
    LEAD_DELETED = "lead_deleted"
    LEAD_ENRICHED = "lead_enriched"
    LEAD_IMPORTED = "leads_imported"
    
    # Campaign actions
    CAMPAIGN_CREATED = "campaign_created"
    CAMPAIGN_UPDATED = "campaign_updated"
    CAMPAIGN_DELETED = "campaign_deleted"
    CAMPAIGN_STARTED = "campaign_started"
    CAMPAIGN_PAUSED = "campaign_paused"
    CAMPAIGN_RESUMED = "campaign_resumed"
    CAMPAIGN_COMPLETED = "campaign_completed"
    
    # Outreach actions
    MESSAGE_CREATED = "message_created"
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_OPENED = "message_opened"
    MESSAGE_REPLIED = "message_replied"
    
    # User actions
    USER_REGISTERED = "user_registered"
    USER_LOGGED_IN = "user_logged_in"
    USER_UPDATED = "user_updated"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFIED = "email_verified"
