"""
Scoring rule repository.
"""
import uuid
from typing import List

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.models.scoring import ScoringRule, DEFAULT_SCORING_RULES
from backend.repositories.base import BaseRepository


class ScoringRuleRepository(BaseRepository[ScoringRule]):
    """Repository for ScoringRule operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ScoringRule, session)
    
    async def get_active(self, org_id: uuid.UUID) -> List[ScoringRule]:
        """Get all active scoring rules, ordered by priority."""
        query = select(ScoringRule).where(
            ScoringRule.org_id == org_id,
            ScoringRule.is_active == True
        ).order_by(ScoringRule.priority.desc())
        result = await self.session.exec(query)
        return result.all()
    
    async def create_defaults(self, org_id: uuid.UUID) -> List[ScoringRule]:
        """Create default scoring rules for a new organization."""
        rules = []
        for rule_data in DEFAULT_SCORING_RULES:
            rule = ScoringRule(
                org_id=org_id,
                **rule_data
            )
            self.session.add(rule)
            rules.append(rule)
        
        await self.session.commit()
        for rule in rules:
            await self.session.refresh(rule)
        
        return rules
