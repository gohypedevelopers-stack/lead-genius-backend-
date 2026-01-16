"""
Campaign service - campaign management.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.core.exceptions import raise_not_found, raise_validation_error
from backend.repositories.campaign_repo import CampaignRepository
from backend.repositories.lead_repo import LeadRepository
from backend.repositories.activity_repo import ActivityLogRepository
from backend.models.campaign import Campaign
from backend.models.lead import Lead
from backend.models.activity import Actions
from backend.schemas.campaign import CampaignCreate, CampaignUpdate


class CampaignService:
    """Service for campaign operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.campaign_repo = CampaignRepository(session)
        self.lead_repo = LeadRepository(session)
        self.activity_repo = ActivityLogRepository(session)
    
    async def create(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        campaign_data: CampaignCreate
    ) -> Campaign:
        """Create a new campaign."""
        data = campaign_data.model_dump()
        data["org_id"] = org_id
        
        campaign = await self.campaign_repo.create(data)
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.CAMPAIGN_CREATED,
            entity_type="campaign",
            entity_id=campaign.id,
            description=f"Campaign '{campaign.name}' created"
        )
        
        return campaign
    
    async def get(self, org_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign:
        """Get a campaign by ID."""
        campaign = await self.campaign_repo.get(campaign_id)
        if not campaign or campaign.org_id != org_id:
            raise_not_found("Campaign", str(campaign_id))
        return campaign
    
    async def list(
        self,
        org_id: uuid.UUID,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """List campaigns with optional status filter."""
        filters = {}
        if status:
            filters["status"] = status
        
        return await self.campaign_repo.list_paginated(
            org_id=org_id,
            filters=filters,
            page=page,
            limit=limit
        )
    
    async def update(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        campaign_id: uuid.UUID,
        campaign_data: CampaignUpdate
    ) -> Campaign:
        """Update a campaign."""
        campaign = await self.campaign_repo.get(campaign_id)
        if not campaign or campaign.org_id != org_id:
            raise_not_found("Campaign", str(campaign_id))
        
        update_data = campaign_data.model_dump(exclude_unset=True)
        updated_campaign = await self.campaign_repo.update(campaign_id, update_data)
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.CAMPAIGN_UPDATED,
            entity_type="campaign",
            entity_id=campaign_id,
            description=f"Campaign '{campaign.name}' updated"
        )
        
        return updated_campaign
    
    async def delete(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        campaign_id: uuid.UUID
    ) -> bool:
        """Delete a campaign."""
        campaign = await self.campaign_repo.get(campaign_id)
        if not campaign or campaign.org_id != org_id:
            raise_not_found("Campaign", str(campaign_id))
        
        # Only allow deleting draft campaigns
        if campaign.status not in ["draft", "failed"]:
            raise_validation_error("Can only delete draft or failed campaigns")
        
        campaign_name = campaign.name
        success = await self.campaign_repo.delete(campaign_id)
        
        if success:
            await self.activity_repo.log(
                org_id=org_id,
                actor_id=user_id,
                action=Actions.CAMPAIGN_DELETED,
                entity_type="campaign",
                entity_id=campaign_id,
                description=f"Campaign '{campaign_name}' deleted"
            )
        
        return success
    
    async def run(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        campaign_id: uuid.UUID
    ) -> Campaign:
        """Start/run a campaign."""
        campaign = await self.campaign_repo.get(campaign_id)
        if not campaign or campaign.org_id != org_id:
            raise_not_found("Campaign", str(campaign_id))
        
        if campaign.status not in ["draft", "paused"]:
            raise_validation_error(f"Cannot run campaign in '{campaign.status}' status")
        
        # Update status to processing
        campaign = await self.campaign_repo.update_status(campaign_id, "processing")
        
        # Mock lead generation (replace with real extraction later)
        mock_leads = await self._generate_mock_leads(campaign)
        
        for lead_data in mock_leads:
            lead_data["org_id"] = org_id
            lead_data["campaign_id"] = campaign_id
            lead_data["source"] = campaign.type
            await self.lead_repo.create(lead_data)
        
        # Update campaign with results
        await self.campaign_repo.increment_leads_count(campaign_id, len(mock_leads))
        campaign = await self.campaign_repo.update_status(campaign_id, "completed")
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.CAMPAIGN_STARTED,
            entity_type="campaign",
            entity_id=campaign_id,
            description=f"Campaign '{campaign.name}' executed",
            meta_data={"leads_generated": len(mock_leads)}
        )
        
        return campaign
    
    async def pause(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        campaign_id: uuid.UUID
    ) -> Campaign:
        """Pause an active campaign."""
        campaign = await self.campaign_repo.get(campaign_id)
        if not campaign or campaign.org_id != org_id:
            raise_not_found("Campaign", str(campaign_id))
        
        if campaign.status != "active":
            raise_validation_error("Can only pause active campaigns")
        
        campaign = await self.campaign_repo.update_status(campaign_id, "paused")
        
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.CAMPAIGN_PAUSED,
            entity_type="campaign",
            entity_id=campaign_id,
            description=f"Campaign '{campaign.name}' paused"
        )
        
        return campaign
    
    async def resume(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        campaign_id: uuid.UUID
    ) -> Campaign:
        """Resume a paused campaign."""
        campaign = await self.campaign_repo.get(campaign_id)
        if not campaign or campaign.org_id != org_id:
            raise_not_found("Campaign", str(campaign_id))
        
        if campaign.status != "paused":
            raise_validation_error("Can only resume paused campaigns")
        
        campaign = await self.campaign_repo.update_status(campaign_id, "active")
        
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.CAMPAIGN_RESUMED,
            entity_type="campaign",
            entity_id=campaign_id,
            description=f"Campaign '{campaign.name}' resumed"
        )
        
        return campaign
    
    async def get_stats(self, org_id: uuid.UUID, campaign_id: uuid.UUID) -> dict:
        """Get campaign statistics."""
        campaign = await self.campaign_repo.get(campaign_id)
        if not campaign or campaign.org_id != org_id:
            raise_not_found("Campaign", str(campaign_id))
        
        return await self.campaign_repo.get_stats(campaign_id)
    
    async def _generate_mock_leads(self, campaign: Campaign) -> List[dict]:
        """Generate mock leads for testing (replace with real extraction)."""
        settings = campaign.settings
        target_count = settings.get("target_count", 3)
        
        leads = []
        for i in range(min(target_count, 5)):  # Cap at 5 for mock
            leads.append({
                "name": f"Lead {i+1} from {campaign.name}",
                "linkedin_url": f"https://linkedin.com/in/lead-{campaign.id}-{i+1}",
                "title": settings.get("keywords", ["Professional"])[0] if settings.get("keywords") else "Professional",
                "company": f"Company {i+1}",
                "location": settings.get("location", "Remote"),
                "status": "new"
            })
        
        return leads
