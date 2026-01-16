"""
Personas API routes.
"""
import uuid
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.persona_service import PersonaService
from backend.schemas.persona import PersonaCreate, PersonaUpdate, PersonaResponse
from backend.api.deps import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.post("/", response_model=PersonaResponse, status_code=201)
async def create_persona(
    persona_data: PersonaCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new persona/ICP."""
    persona_service = PersonaService(session)
    return await persona_service.create(current_user.current_org_id, persona_data)


@router.get("/")
async def list_personas(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List personas."""
    persona_service = PersonaService(session)
    personas = await persona_service.list(current_user.current_org_id, active_only)
    return {"items": personas, "total": len(personas)}


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a persona by ID."""
    persona_service = PersonaService(session)
    return await persona_service.get(current_user.current_org_id, persona_id)


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: uuid.UUID,
    persona_data: PersonaUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a persona."""
    persona_service = PersonaService(session)
    return await persona_service.update(current_user.current_org_id, persona_id, persona_data)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a persona."""
    persona_service = PersonaService(session)
    await persona_service.delete(current_user.current_org_id, persona_id)
