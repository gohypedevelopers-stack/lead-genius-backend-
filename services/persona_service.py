"""
Persona service - ICP management.
"""
import uuid
from typing import Optional, List

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.core.exceptions import raise_not_found
from backend.repositories.persona_repo import PersonaRepository
from backend.models.persona import Persona
from backend.schemas.persona import PersonaCreate, PersonaUpdate


class PersonaService:
    """Service for persona operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.persona_repo = PersonaRepository(session)
    
    async def create(
        self,
        org_id: uuid.UUID,
        persona_data: PersonaCreate
    ) -> Persona:
        """Create a new persona."""
        data = persona_data.model_dump()
        data["org_id"] = org_id
        return await self.persona_repo.create(data)
    
    async def get(self, org_id: uuid.UUID, persona_id: uuid.UUID) -> Persona:
        """Get a persona by ID."""
        persona = await self.persona_repo.get(persona_id)
        if not persona or persona.org_id != org_id:
            raise_not_found("Persona", str(persona_id))
        return persona
    
    async def list(self, org_id: uuid.UUID, active_only: bool = True) -> List[Persona]:
        """List personas for an organization."""
        if active_only:
            return await self.persona_repo.get_active(org_id)
        return await self.persona_repo.list(org_id)
    
    async def update(
        self,
        org_id: uuid.UUID,
        persona_id: uuid.UUID,
        persona_data: PersonaUpdate
    ) -> Persona:
        """Update a persona."""
        persona = await self.persona_repo.get(persona_id)
        if not persona or persona.org_id != org_id:
            raise_not_found("Persona", str(persona_id))
        
        update_data = persona_data.model_dump(exclude_unset=True)
        return await self.persona_repo.update(persona_id, update_data)
    
    async def delete(self, org_id: uuid.UUID, persona_id: uuid.UUID) -> bool:
        """Delete a persona."""
        persona = await self.persona_repo.get(persona_id)
        if not persona or persona.org_id != org_id:
            raise_not_found("Persona", str(persona_id))
        
        return await self.persona_repo.delete(persona_id)
