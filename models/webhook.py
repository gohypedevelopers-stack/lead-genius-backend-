"""
Webhook models - event dispatch for integrations.
Allows external systems to subscribe to events.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class Webhook(SQLModel, table=True):
    """
    Webhook subscription for event notifications.
    External systems can receive real-time updates.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="organization.id", index=True)
    
    # Webhook config
    name: str
    url: str
    secret: str  # For signature verification
    
    # Events to subscribe to
    events: List[str] = Field(default=[], sa_column=Column(JSONB))
    # Example: ["lead.created", "lead.enriched", "campaign.completed"]
    
    # Status
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WebhookDelivery(SQLModel, table=True):
    """
    Record of webhook delivery attempts.
    Tracks success/failure for debugging.
    """
    __tablename__ = "webhook_delivery"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    webhook_id: uuid.UUID = Field(foreign_key="webhook.id", index=True)
    
    # Event info
    event: str
    payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    
    # Delivery status
    status: str = Field(default="pending")  # pending, success, failed
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    
    # Retry tracking
    attempts: int = Field(default=0)
    next_retry_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None


# Available webhook events
class WebhookEvents:
    # Leads
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    LEAD_DELETED = "lead.deleted"
    LEAD_ENRICHED = "lead.enriched"
    LEAD_QUALIFIED = "lead.qualified"
    
    # Campaigns
    CAMPAIGN_CREATED = "campaign.created"
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_COMPLETED = "campaign.completed"
    CAMPAIGN_FAILED = "campaign.failed"
    
    # Outreach
    MESSAGE_SENT = "message.sent"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_REPLIED = "message.replied"
