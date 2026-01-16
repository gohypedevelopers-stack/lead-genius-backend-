"""
Campaigns API routes.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.campaign_service import CampaignService
from backend.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse, CampaignStats
from backend.schemas.common import MessageResponse
from backend.api.deps import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new campaign."""
    campaign_service = CampaignService(session)
    return await campaign_service.create(
        current_user.current_org_id,
        current_user.id,
        campaign_data
    )


@router.get("/")
async def list_campaigns(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List campaigns with optional status filter."""
    campaign_service = CampaignService(session)
    return await campaign_service.list(current_user.current_org_id, status, page, limit)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a campaign by ID."""
    campaign_service = CampaignService(session)
    return await campaign_service.get(current_user.current_org_id, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    campaign_data: CampaignUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a campaign."""
    campaign_service = CampaignService(session)
    return await campaign_service.update(
        current_user.current_org_id,
        current_user.id,
        campaign_id,
        campaign_data
    )


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a campaign (draft/failed only)."""
    campaign_service = CampaignService(session)
    await campaign_service.delete(current_user.current_org_id, current_user.id, campaign_id)


@router.post("/{campaign_id}/run", response_model=CampaignResponse)
async def run_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Start/run a campaign."""
    campaign_service = CampaignService(session)
    return await campaign_service.run(
        current_user.current_org_id,
        current_user.id,
        campaign_id
    )


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Pause an active campaign."""
    campaign_service = CampaignService(session)
    return await campaign_service.pause(
        current_user.current_org_id,
        current_user.id,
        campaign_id
    )


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Resume a paused campaign."""
    campaign_service = CampaignService(session)
    return await campaign_service.resume(
        current_user.current_org_id,
        current_user.id,
        campaign_id
    )


@router.get("/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get campaign statistics."""
    campaign_service = CampaignService(session)
    return await campaign_service.get_stats(current_user.current_org_id, campaign_id)
