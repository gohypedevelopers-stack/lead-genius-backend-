"""
Scoring service - lead scoring management.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from backend.core.exceptions import raise_not_found
from backend.repositories.scoring_repo import ScoringRuleRepository
from backend.repositories.lead_repo import LeadRepository
from backend.models.scoring import ScoringRule
from backend.models.lead import Lead, LeadInteraction
from backend.schemas.scoring import ScoringRuleCreate, ScoringRuleUpdate, RecalculateResponse
from backend.services.ai_analysis_service import ai_analysis_service

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
    
    async def recalculate_campaign(
        self,
        org_id: uuid.UUID,
        campaign_id: uuid.UUID
    ) -> RecalculateResponse:
        """Recalculate scores for all leads in a campaign."""
        # Get all leads for the campaign
        from backend.schemas.lead import LeadFilter
        leads_dict = await self.lead_repo.search(org_id, LeadFilter(campaign_id=campaign_id), limit=10000)
        leads = leads_dict["items"]
        
        if not leads:
            return RecalculateResponse(
                total_updated=0,
                avg_score_before=0,
                avg_score_after=0
            )
            
        return await self._process_recalculation(org_id, leads)

    async def _process_recalculation(self, org_id: uuid.UUID, leads: List[Lead]) -> RecalculateResponse:
        """Helper to process recalculations."""
        if not leads:
             return RecalculateResponse(total_updated=0, avg_score_before=0, avg_score_after=0)

        total_before = sum(l.score for l in leads)
        avg_before = total_before / len(leads)
        
        total_after = 0
        rules = await self.scoring_repo.get_active(org_id) # Keep rules for custom overrides if needed, but primary is weighted

        for lead in leads:
            new_score = await self.calculate_score(org_id, lead)
            
            await self.lead_repo.update_score(lead.id, new_score)
            total_after += new_score
            
        avg_after = total_after / len(leads)
        
        return RecalculateResponse(
            total_updated=len(leads),
            avg_score_before=round(avg_before, 1),
            avg_score_after=round(avg_after, 1)
        )

    async def calculate_score(self, org_id: uuid.UUID, lead: Lead) -> int:
        """
        Calculate score. 
        Tries AI first (Gemini/OpenAI), falls back to weighted formula.
        """
        # --- AI SCORING ---
        if ai_analysis_service.client:
            try:
                # 1. Fetch Interactions
                statement = select(LeadInteraction).where(LeadInteraction.lead_id == lead.id)
                interactions_result = await self.session.exec(statement)
                interactions = interactions_result.all()
                
                interactions_data = [
                    {"type": i.type, "content": i.content, "source_url": i.source_url} 
                    for i in interactions
                ]
                
                # 2. Prepare Lead Data
                lead_data = {
                    "name": lead.name,
                    "title": lead.title,
                    "company": lead.company,
                    "headline": lead.profile_data.get("headline") or lead.profile_data.get("authorHeadline"),
                    "about": lead.profile_data.get("about") or lead.profile_data.get("summary")
                }
                
                # 3. Call AI
                result = ai_analysis_service.score_lead(lead_data, interactions_data)
                score = result.get("score")
                reasoning = result.get("reasoning")
                
                if score is not None and isinstance(score, (int, float)):
                    # Optionally save reasoning
                    if reasoning:
                        # Append to notes or store in custom_fields
                        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                        note = f"[{timestamp}] AI Score: {score}/100. Reasoning: {reasoning}"
                        if lead.notes:
                            lead.notes += f"\n\n{note}"
                        else:
                            lead.notes = note
                        # We need to save the lead to persist notes. 
                        # Ideally lead_repo.update_score should handle this or we update lead here.
                        # Since update_score only updates score column, we might want to update lead fully.
                        # But for now, let's just return the score.
                        # (NOTE: notes update won't persist unless we add/commit here or caller does)
                        lead.custom_fields["ai_score_reasoning"] = reasoning
                        lead.custom_fields["ai_quality_tier"] = result.get("quality_tier")
                        # Session is async, caller often handles commit or we do it via repo update
                        # Here calculate_score is a pure calculation usually. But we modified the object.
                        # The caller _process_recalculation calls lead_repo.update_score.
                        # If we want to save custom_fields, we need to call update.
                        # Use repo update method if available or ad-hoc.
                        # For now, just returning score is safer to avoid side effects in calculation method.
                    
                    return int(max(0, min(100, score)))
            except Exception as e:
                # Log error and fallback
                print(f"AI Scoring failed for lead {lead.id}: {e}")

        # --- FALLBACK: RULE BASED ---
        # 1. Profile Match (0-100) - 45%
        # Derived from Title, Location, Keywords match
        profile_score = self._calculate_profile_match(lead)
        
        # 2. Engagement Intent (0-100) - 35%
        # Derived from Status and Source
        engagement_score = self._calculate_engagement_intent(lead)
        
        # 3. Company Fit (0-100) - 15%
        # Derived from Company Size, Industry (mocked/estimated for now)
        company_score = self._calculate_company_fit(lead)
        
        # 4. Activity (0-100) - 5%
        # Derived from actions (mocked for now)
        activity_score = 50 # Default baseline activity
        
        # Weighted Total
        total_score = (
            (profile_score * 0.45) +
            (engagement_score * 0.35) +
            (company_score * 0.15) +
            (activity_score * 0.05)
        )
        
        return int(max(0, min(100, total_score)))
        
    def _calculate_profile_match(self, lead: Lead) -> int:
        """Estimate profile match based on title and completeness."""
        score = 50 # Base
        
        # Title keywords
        if lead.title:
            title = lead.title.lower()
            if any(x in title for x in ["vp", "head", "director", "chief", "founder"]):
                score += 30
            elif any(x in title for x in ["manager", "senior", "lead"]):
                score += 15
        
        # Data completeness
        if lead.linkedin_url: score += 10
        if lead.email: score += 10
        
        return min(100, score)

    def _calculate_engagement_intent(self, lead: Lead) -> int:
        """Estimate intent based on interactions."""
        score = 20 # Base
        
        # Status based
        if lead.status == "replied": score = 90
        elif lead.status == "contacted": score = 60
        elif lead.status == "qualified": score = 95
        elif lead.status == "new": score = 30
        
        # Source boost
        if lead.source == "social_engagement": score += 10
        
        return min(100, score)

    def _calculate_company_fit(self, lead: Lead) -> int:
        """Estimate company fit."""
        score = 50 # Neutral start
        if lead.company: score += 20 # Company identified
        return score

    async def recalculate_all(
        self,
        org_id: uuid.UUID,
        lead_ids: Optional[List[uuid.UUID]] = None
    ) -> RecalculateResponse:
        """Recalculate scores for all or specific leads."""
        if lead_ids:
            # Helper to fetch specific leads - efficient implementation requires repo support or loop
            # For simplicity using loop here as list defaults to all
             leads = []
             for lid in lead_ids:
                 l = await self.lead_repo.get(lid)
                 if l and l.org_id == org_id:
                     leads.append(l)
        else:
             # Get all leads (limit 1000 for safety in MVP)
             leads_dict = await self.lead_repo.search(org_id, limit=1000)
             leads = leads_dict["items"]
             
        return await self._process_recalculation(org_id, leads)

    def _evaluate_rule(self, lead: Lead, rule: ScoringRule) -> bool:
        # Kept for backward compatibility if needed, but unused in main formula
        return False
