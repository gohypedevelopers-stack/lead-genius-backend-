"""
Outreach service - messaging and templates.
"""
import uuid
from typing import Optional, List
from datetime import datetime
import re

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.core.exceptions import raise_not_found
from backend.repositories.outreach_repo import OutreachMessageRepository, MessageTemplateRepository
from backend.repositories.lead_repo import LeadRepository
from backend.repositories.activity_repo import ActivityLogRepository
from backend.models.outreach import OutreachMessage, MessageTemplate
from backend.models.activity import Actions
from backend.schemas.outreach import OutreachCreate, TemplateCreate, TemplateUpdate


class OutreachService:
    """Service for outreach operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.message_repo = OutreachMessageRepository(session)
        self.template_repo = MessageTemplateRepository(session)
        self.lead_repo = LeadRepository(session)
        self.activity_repo = ActivityLogRepository(session)
    
    # Message operations
    async def create_message(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        message_data: OutreachCreate
    ) -> OutreachMessage:
        """Create an outreach message."""
        # Verify lead exists and belongs to org
        lead = await self.lead_repo.get(message_data.lead_id)
        if not lead or lead.org_id != org_id:
            raise_not_found("Lead", str(message_data.lead_id))
        
        data = message_data.model_dump()
        data["org_id"] = org_id
        
        # Set status based on scheduling
        if message_data.scheduled_at and message_data.scheduled_at > datetime.utcnow():
            data["status"] = "scheduled"
        else:
            data["status"] = "pending"
        
        message = await self.message_repo.create(data)
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.MESSAGE_CREATED,
            entity_type="outreach",
            entity_id=message.id,
            description=f"Message created for lead '{lead.name}'",
            meta_data={"channel": message.channel, "lead_id": str(lead.id)}
        )
        
        return message
    
    async def list_messages(
        self,
        org_id: uuid.UUID,
        lead_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """List outreach messages with filters."""
        if lead_id:
            return await self.message_repo.get_by_lead(org_id, lead_id, page, limit)
        
        filters = {}
        if status:
            filters["status"] = status
        
        return await self.message_repo.list_paginated(
            org_id=org_id,
            filters=filters,
            page=page,
            limit=limit
        )
    
    async def get_message(self, org_id: uuid.UUID, message_id: uuid.UUID) -> OutreachMessage:
        """Get a message by ID."""
        message = await self.message_repo.get(message_id)
        if not message or message.org_id != org_id:
            raise_not_found("Message", str(message_id))
        return message
    
    async def send_message(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        message_id: uuid.UUID
    ) -> OutreachMessage:
        """Send a pending message (mock implementation)."""
        message = await self.message_repo.get(message_id)
        if not message or message.org_id != org_id:
            raise_not_found("Message", str(message_id))
        
        # Mock sending (replace with real provider later)
        try:
            # In real implementation, call LinkedIn API or email provider
            message = await self.message_repo.update_status(message_id, "sent")
            
            # Update lead last_contacted_at
            await self.lead_repo.update_status(message.lead_id, "contacted")
            
            await self.activity_repo.log(
                org_id=org_id,
                actor_id=user_id,
                action=Actions.MESSAGE_SENT,
                entity_type="outreach",
                entity_id=message_id,
                description="Message sent"
            )
            
        except Exception as e:
            message = await self.message_repo.update_status(message_id, "failed", str(e))
        
        return message
    
    # Template operations
    async def create_template(
        self,
        org_id: uuid.UUID,
        template_data: TemplateCreate
    ) -> MessageTemplate:
        """Create a message template."""
        data = template_data.model_dump()
        data["org_id"] = org_id
        
        # Extract variables from content
        variables = self._extract_variables(data["content"])
        data["variables"] = variables
        
        return await self.template_repo.create(data)
    
    async def list_templates(
        self,
        org_id: uuid.UUID,
        channel: Optional[str] = None
    ) -> List[MessageTemplate]:
        """List message templates."""
        if channel:
            return await self.template_repo.get_by_channel(org_id, channel)
        return await self.template_repo.get_active(org_id)
    
    async def get_template(self, org_id: uuid.UUID, template_id: uuid.UUID) -> MessageTemplate:
        """Get a template by ID."""
        template = await self.template_repo.get(template_id)
        if not template or template.org_id != org_id:
            raise_not_found("Template", str(template_id))
        return template
    
    async def update_template(
        self,
        org_id: uuid.UUID,
        template_id: uuid.UUID,
        template_data: TemplateUpdate
    ) -> MessageTemplate:
        """Update a template."""
        template = await self.template_repo.get(template_id)
        if not template or template.org_id != org_id:
            raise_not_found("Template", str(template_id))
        
        update_data = template_data.model_dump(exclude_unset=True)
        
        # Re-extract variables if content changed
        if "content" in update_data:
            update_data["variables"] = self._extract_variables(update_data["content"])
        
        return await self.template_repo.update(template_id, update_data)
    
    async def delete_template(self, org_id: uuid.UUID, template_id: uuid.UUID) -> bool:
        """Delete a template."""
        template = await self.template_repo.get(template_id)
        if not template or template.org_id != org_id:
            raise_not_found("Template", str(template_id))
        
        return await self.template_repo.delete(template_id)
    
    async def render_template(
        self,
        org_id: uuid.UUID,
        template_id: uuid.UUID,
        lead_id: uuid.UUID
    ) -> str:
        """Render a template with lead data."""
        template = await self.template_repo.get(template_id)
        if not template or template.org_id != org_id:
            raise_not_found("Template", str(template_id))
        
        lead = await self.lead_repo.get(lead_id)
        if not lead or lead.org_id != org_id:
            raise_not_found("Lead", str(lead_id))
        
        # Replace variables
        content = template.content
        replacements = {
            "name": lead.name,
            "first_name": lead.name.split()[0] if lead.name else "",
            "company": lead.company or "",
            "title": lead.title or "",
            "location": lead.location or ""
        }
        
        for var, value in replacements.items():
            content = content.replace(f"{{{{{var}}}}}", value)
        
        return content
    
    def _extract_variables(self, content: str) -> List[str]:
        """Extract {{variable}} patterns from content."""
        pattern = r'\{\{(\w+)\}\}'
        return list(set(re.findall(pattern, content)))
