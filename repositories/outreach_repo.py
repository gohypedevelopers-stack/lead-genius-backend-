"""
Outreach repository for messages and templates.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func

from backend.models.outreach import OutreachMessage, MessageTemplate
from backend.repositories.base import BaseRepository
from backend.core.pagination import create_paginated_response


class OutreachMessageRepository(BaseRepository[OutreachMessage]):
    """Repository for OutreachMessage operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(OutreachMessage, session)
    
    async def get_by_lead(
        self, 
        org_id: uuid.UUID, 
        lead_id: uuid.UUID,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """Get all messages for a specific lead."""
        query = select(OutreachMessage).where(
            OutreachMessage.org_id == org_id,
            OutreachMessage.lead_id == lead_id
        )
        
        # Get total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.exec(count_query)
        total = total_result.one()
        
        # Paginate
        query = query.order_by(OutreachMessage.created_at.desc())
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        result = await self.session.exec(query)
        items = result.all()
        
        return create_paginated_response(items, total, page, limit)
    
    async def get_scheduled(self, org_id: uuid.UUID) -> List[OutreachMessage]:
        """Get all scheduled messages that are due."""
        query = select(OutreachMessage).where(
            OutreachMessage.org_id == org_id,
            OutreachMessage.status == "scheduled",
            OutreachMessage.scheduled_at <= datetime.utcnow()
        )
        result = await self.session.exec(query)
        return result.all()
    
    async def update_status(
        self, 
        message_id: uuid.UUID, 
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[OutreachMessage]:
        """Update message status with appropriate timestamps."""
        message = await self.get(message_id)
        if not message:
            return None
        
        message.status = status
        message.updated_at = datetime.utcnow()
        
        if status == "sent":
            message.sent_at = datetime.utcnow()
        elif status == "delivered":
            message.delivered_at = datetime.utcnow()
        elif status == "opened":
            message.opened_at = datetime.utcnow()
        elif status == "replied":
            message.replied_at = datetime.utcnow()
        elif status == "failed":
            message.error_message = error_message
            message.retry_count += 1
        
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message
    
    async def count_by_status(self, org_id: uuid.UUID) -> dict:
        """Count messages by status."""
        counts = {}
        for status in ["pending", "scheduled", "sent", "failed", "delivered", "opened", "replied"]:
            count = await self.count(org_id, {"status": status})
            counts[status] = count
        return counts


class MessageTemplateRepository(BaseRepository[MessageTemplate]):
    """Repository for MessageTemplate operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(MessageTemplate, session)
    
    async def get_active(self, org_id: uuid.UUID) -> List[MessageTemplate]:
        """Get all active templates."""
        query = select(MessageTemplate).where(
            MessageTemplate.org_id == org_id,
            MessageTemplate.is_active == True
        ).order_by(MessageTemplate.name)
        result = await self.session.exec(query)
        return result.all()
    
    async def get_by_channel(self, org_id: uuid.UUID, channel: str) -> List[MessageTemplate]:
        """Get templates for a specific channel."""
        query = select(MessageTemplate).where(
            MessageTemplate.org_id == org_id,
            MessageTemplate.channel == channel,
            MessageTemplate.is_active == True
        )
        result = await self.session.exec(query)
        return result.all()
