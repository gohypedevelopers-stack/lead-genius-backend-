"""
Persona repository.
"""
import uuid
from typing import List

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.models.persona import Persona
from backend.repositories.base import BaseRepository


class PersonaRepository(BaseRepository[Persona]):
    """Repository for Persona operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Persona, session)
    
    async def get_active(self, org_id: uuid.UUID) -> List[Persona]:
        """Get all active personas for an organization, ordered by priority."""
        query = select(Persona).where(
            Persona.org_id == org_id,
            Persona.is_active == True
        ).order_by(Persona.priority.desc())
        result = await self.session.exec(query)
        return result.all()
    
    async def get_by_name(self, org_id: uuid.UUID, name: str) -> Persona:
        """Get persona by name."""
        query = select(Persona).where(
            Persona.org_id == org_id,
            Persona.name == name
        )
        result = await self.session.exec(query)
        return result.first()
