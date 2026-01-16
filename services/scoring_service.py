"""
Scoring service - lead scoring management.
"""
import uuid
from typing import Optional, List

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.core.exceptions import raise_not_found
from backend.repositories.scoring_repo import ScoringRuleRepository
from backend.repositories.lead_repo import LeadRepository
from backend.models.scoring import ScoringRule
from backend.models.lead import Lead
from backend.schemas.scoring import ScoringRuleCreate, ScoringRuleUpdate, RecalculateResponse


class ScoringService:
    """Service for scoring operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.scoring_repo = ScoringRuleRepository(session)
        self.lead_repo = LeadRepository(session)
    
    async def create_rule(
        self,
        org_id: uuid.UUID,
        rule_data: ScoringRuleCreate
    ) -> ScoringRule:
        """Create a new scoring rule."""
        data = rule_data.model_dump()
        data["org_id"] = org_id
        return await self.scoring_repo.create(data)
    
    async def get_rule(self, org_id: uuid.UUID, rule_id: uuid.UUID) -> ScoringRule:
        """Get a scoring rule by ID."""
        rule = await self.scoring_repo.get(rule_id)
        if not rule or rule.org_id != org_id:
            raise_not_found("Scoring Rule", str(rule_id))
        return rule
    
    async def list_rules(self, org_id: uuid.UUID, active_only: bool = True) -> List[ScoringRule]:
        """List scoring rules for an organization."""
        if active_only:
            return await self.scoring_repo.get_active(org_id)
        return await self.scoring_repo.list(org_id)
    
    async def update_rule(
        self,
        org_id: uuid.UUID,
        rule_id: uuid.UUID,
        rule_data: ScoringRuleUpdate
    ) -> ScoringRule:
        """Update a scoring rule."""
        rule = await self.scoring_repo.get(rule_id)
        if not rule or rule.org_id != org_id:
            raise_not_found("Scoring Rule", str(rule_id))
        
        update_data = rule_data.model_dump(exclude_unset=True)
        return await self.scoring_repo.update(rule_id, update_data)
    
    async def delete_rule(self, org_id: uuid.UUID, rule_id: uuid.UUID) -> bool:
        """Delete a scoring rule."""
        rule = await self.scoring_repo.get(rule_id)
        if not rule or rule.org_id != org_id:
            raise_not_found("Scoring Rule", str(rule_id))
        
        return await self.scoring_repo.delete(rule_id)
    
    async def create_default_rules(self, org_id: uuid.UUID) -> List[ScoringRule]:
        """Create default scoring rules for a new organization."""
        return await self.scoring_repo.create_defaults(org_id)
    
    async def calculate_score(self, org_id: uuid.UUID, lead: Lead) -> int:
        """Calculate score for a single lead."""
        rules = await self.scoring_repo.get_active(org_id)
        
        score = 0
        for rule in rules:
            if self._evaluate_rule(lead, rule):
                score += rule.score_delta
        
        return max(0, min(100, score))  # Clamp between 0-100
    
    async def recalculate_all(
        self,
        org_id: uuid.UUID,
        lead_ids: Optional[List[uuid.UUID]] = None
    ) -> RecalculateResponse:
        """Recalculate scores for all or specific leads."""
        rules = await self.scoring_repo.get_active(org_id)
        
        # Get leads to recalculate
        if lead_ids:
            leads = [await self.lead_repo.get(lid) for lid in lead_ids]
            leads = [l for l in leads if l and l.org_id == org_id]
        else:
            leads = await self.lead_repo.list(org_id)
        
        if not leads:
            return RecalculateResponse(
                total_updated=0,
                avg_score_before=0,
                avg_score_after=0
            )
        
        # Calculate averages
        total_before = sum(l.score for l in leads)
        avg_before = total_before / len(leads) if leads else 0
        
        # Recalculate scores
        total_after = 0
        for lead in leads:
            new_score = 0
            for rule in rules:
                if self._evaluate_rule(lead, rule):
                    new_score += rule.score_delta
            
            new_score = max(0, min(100, new_score))
            await self.lead_repo.update_score(lead.id, new_score)
            total_after += new_score
        
        avg_after = total_after / len(leads) if leads else 0
        
        return RecalculateResponse(
            total_updated=len(leads),
            avg_score_before=round(avg_before, 1),
            avg_score_after=round(avg_after, 1)
        )
    
    def _evaluate_rule(self, lead: Lead, rule: ScoringRule) -> bool:
        """Evaluate a single scoring rule against a lead."""
        field_value = getattr(lead, rule.field, None)
        
        if rule.operator == "exists":
            return field_value is not None and field_value != ""
        elif rule.operator == "not_exists":
            return field_value is None or field_value == ""
        elif rule.operator == "equals":
            return str(field_value).lower() == rule.value.lower()
        elif rule.operator == "contains":
            return field_value and rule.value.lower() in str(field_value).lower()
        elif rule.operator == "greater_than":
            try:
                return float(field_value or 0) > float(rule.value)
            except:
                return False
        elif rule.operator == "less_than":
            try:
                return float(field_value or 0) < float(rule.value)
            except:
                return False
        
        return False
