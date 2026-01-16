"""
Campaign repository.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func

from backend.models.campaign import Campaign
from backend.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    """Repository for Campaign operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Campaign, session)
    
    async def update_status(self, campaign_id: uuid.UUID, status: str) -> Optional[Campaign]:
        """Update campaign status with appropriate timestamps."""
        campaign = await self.get(campaign_id)
        if not campaign:
            return None
        
        campaign.status = status
        campaign.updated_at = datetime.utcnow()
        
        # Set appropriate timestamp based on status
        if status == "active":
            if not campaign.started_at:
                campaign.started_at = datetime.utcnow()
            campaign.paused_at = None
            campaign.last_resumed_at = datetime.utcnow()
        elif status == "paused":
            campaign.paused_at = datetime.utcnow()
        elif status == "completed":
            campaign.completed_at = datetime.utcnow()
        
        self.session.add(campaign)
        await self.session.commit()
        await self.session.refresh(campaign)
        return campaign
    
    async def increment_leads_count(self, campaign_id: uuid.UUID, count: int = 1) -> bool:
        """Increment leads count for a campaign."""
        campaign = await self.get(campaign_id)
        if campaign:
            campaign.leads_count += count
            campaign.updated_at = datetime.utcnow()
            self.session.add(campaign)
            await self.session.commit()
            return True
        return False
    
    async def get_active(self, org_id: uuid.UUID) -> List[Campaign]:
        """Get all active campaigns for an organization."""
        query = select(Campaign).where(
            Campaign.org_id == org_id,
            Campaign.status == "active"
        )
        result = await self.session.exec(query)
        return result.all()
    
    async def get_stats(self, campaign_id: uuid.UUID) -> dict:
        """Get statistics for a specific campaign."""
        campaign = await self.get(campaign_id)
        if not campaign:
            return {}
        
        return {
            "campaign_id": campaign_id,
            "leads_count": campaign.leads_count,
            "qualified_leads_count": campaign.qualified_leads_count,
            "contacted_count": campaign.contacted_count,
            "replied_count": campaign.replied_count,
            "status": campaign.status,
            "started_at": campaign.started_at,
            "completed_at": campaign.completed_at
        }
    
    async def count_by_status(self, org_id: uuid.UUID, status: str) -> int:
        """Count campaigns by status."""
        return await self.count(org_id, {"status": status})
