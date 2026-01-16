"""
Leads API routes.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.lead_service import LeadService
from backend.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadFilter, LeadImportResponse
)
from backend.api.deps import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("/", response_model=LeadResponse, status_code=201)
async def create_lead(
    lead_data: LeadCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new lead with auto-scoring."""
    lead_service = LeadService(session)
    return await lead_service.create(
        current_user.current_org_id,
        current_user.id,
        lead_data
    )


@router.get("/")
async def list_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    source: Optional[str] = None,
    campaign_id: Optional[uuid.UUID] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    enrichment_status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List leads with filtering and pagination."""
    filters = LeadFilter(
        status=status,
        source=source,
        campaign_id=campaign_id,
        min_score=min_score,
        max_score=max_score,
        enrichment_status=enrichment_status,
        search=search
    )
    
    lead_service = LeadService(session)
    return await lead_service.list(current_user.current_org_id, filters, page, limit)


@router.get("/stats")
async def get_lead_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get lead statistics."""
    lead_service = LeadService(session)
    return await lead_service.get_stats(current_user.current_org_id)


@router.get("/export")
async def export_leads(
    status: Optional[str] = None,
    campaign_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Export leads to CSV."""
    filters = LeadFilter(status=status, campaign_id=campaign_id) if status or campaign_id else None
    
    lead_service = LeadService(session)
    csv_content = await lead_service.export(current_user.current_org_id, filters)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"}
    )


@router.post("/import", response_model=LeadImportResponse)
async def import_leads(
    file: UploadFile = File(...),
    campaign_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Import leads from CSV file."""
    content = await file.read()
    csv_content = content.decode("utf-8")
    
    lead_service = LeadService(session)
    return await lead_service.import_csv(
        current_user.current_org_id,
        current_user.id,
        csv_content,
        campaign_id
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a lead by ID."""
    lead_service = LeadService(session)
    return await lead_service.get(current_user.current_org_id, lead_id)


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    lead_data: LeadUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a lead."""
    lead_service = LeadService(session)
    return await lead_service.update(
        current_user.current_org_id,
        current_user.id,
        lead_id,
        lead_data
    )


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a lead."""
    lead_service = LeadService(session)
    await lead_service.delete(current_user.current_org_id, current_user.id, lead_id)


@router.post("/{lead_id}/enrich", response_model=LeadResponse)
async def enrich_lead(
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Enrich a lead with external data."""
    lead_service = LeadService(session)
    return await lead_service.enrich(
        current_user.current_org_id,
        current_user.id,
        lead_id
    )
