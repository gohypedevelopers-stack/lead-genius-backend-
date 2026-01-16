"""
Webhook schemas.
"""
import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, HttpUrl


class WebhookCreate(BaseModel):
    """Create a webhook subscription."""
    name: str
    url: str
    events: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "CRM Integration",
                "url": "https://api.mycrm.com/webhooks/leadgenius",
                "events": ["lead.created", "lead.enriched", "campaign.completed"]
            }
        }


class WebhookUpdate(BaseModel):
    """Update a webhook."""
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    """Webhook response."""
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery record."""
    id: uuid.UUID
    webhook_id: uuid.UUID
    event: str
    status: str
    status_code: Optional[int]
    error_message: Optional[str]
    attempts: int
    created_at: datetime
    delivered_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class WebhookTestResponse(BaseModel):
    """Result of webhook test."""
    success: bool
    status_code: Optional[int]
    response_time_ms: int
    error: Optional[str]
