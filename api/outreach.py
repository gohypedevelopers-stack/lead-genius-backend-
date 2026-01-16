"""
Outreach API routes - messages and templates.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.outreach_service import OutreachService
from backend.schemas.outreach import (
    OutreachCreate, OutreachResponse,
    TemplateCreate, TemplateUpdate, TemplateResponse
)
from backend.api.deps import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


# Message endpoints
@router.post("/", response_model=OutreachResponse, status_code=201)
async def create_message(
    message_data: OutreachCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create an outreach message."""
    outreach_service = OutreachService(session)
    return await outreach_service.create_message(
        current_user.current_org_id,
        current_user.id,
        message_data
    )


@router.get("/")
async def list_messages(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    lead_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List outreach messages."""
    outreach_service = OutreachService(session)
    return await outreach_service.list_messages(
        current_user.current_org_id,
        lead_id,
        status,
        page,
        limit
    )


@router.get("/lead/{lead_id}")
async def get_messages_by_lead(
    lead_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all messages for a specific lead."""
    outreach_service = OutreachService(session)
    return await outreach_service.list_messages(
        current_user.current_org_id,
        lead_id,
        None,
        page,
        limit
    )


@router.get("/{message_id}", response_model=OutreachResponse)
async def get_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a message by ID."""
    outreach_service = OutreachService(session)
    return await outreach_service.get_message(current_user.current_org_id, message_id)


@router.post("/{message_id}/send", response_model=OutreachResponse)
async def send_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Send a pending message."""
    outreach_service = OutreachService(session)
    return await outreach_service.send_message(
        current_user.current_org_id,
        current_user.id,
        message_id
    )


# Template endpoints
@router.post("/templates/", response_model=TemplateResponse, status_code=201)
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a message template."""
    outreach_service = OutreachService(session)
    return await outreach_service.create_template(
        current_user.current_org_id,
        template_data
    )


@router.get("/templates/")
async def list_templates(
    channel: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List message templates."""
    outreach_service = OutreachService(session)
    templates = await outreach_service.list_templates(current_user.current_org_id, channel)
    return {"items": templates, "total": len(templates)}


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a template by ID."""
    outreach_service = OutreachService(session)
    return await outreach_service.get_template(current_user.current_org_id, template_id)


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    template_data: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a template."""
    outreach_service = OutreachService(session)
    return await outreach_service.update_template(
        current_user.current_org_id,
        template_id,
        template_data
    )


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a template."""
    outreach_service = OutreachService(session)
    await outreach_service.delete_template(current_user.current_org_id, template_id)


@router.post("/templates/{template_id}/render")
async def render_template(
    template_id: uuid.UUID,
    lead_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Render a template with lead data."""
    outreach_service = OutreachService(session)
    content = await outreach_service.render_template(
        current_user.current_org_id,
        template_id,
        lead_id
    )
    return {"content": content}
