"""
Lead service - lead management with scoring.
"""
import uuid
import csv
import io
from typing import Optional, List
from datetime import datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from backend.core.exceptions import raise_not_found, raise_forbidden
from backend.repositories.lead_repo import LeadRepository
from backend.repositories.activity_repo import ActivityLogRepository
from backend.repositories.persona_repo import PersonaRepository
from backend.repositories.scoring_repo import ScoringRuleRepository
from backend.models.lead import Lead
from backend.models.activity import Actions
from backend.schemas.lead import LeadCreate, LeadUpdate, LeadFilter, LeadImportResponse


class LeadService:
    """Service for lead operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.lead_repo = LeadRepository(session)
        self.activity_repo = ActivityLogRepository(session)
        self.persona_repo = PersonaRepository(session)
        self.scoring_repo = ScoringRuleRepository(session)
    
    async def create(
        self, 
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        lead_data: LeadCreate
    ) -> Lead:
        """Create a new lead with auto-scoring."""
        # Prepare data
        data = lead_data.model_dump()
        data["org_id"] = org_id
        data["source"] = "manual"
        
        # Create lead
        lead = await self.lead_repo.create(data)
        
        # Calculate score
        score = await self._calculate_score(org_id, lead)
        if score > 0:
            await self.lead_repo.update_score(lead.id, score)
            lead.score = score
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.LEAD_CREATED,
            entity_type="lead",
            entity_id=lead.id,
            description=f"Lead '{lead.name}' created",
            meta_data={"name": lead.name, "company": lead.company}
        )
        
        return lead
    
    async def get(self, org_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
        """Get a lead by ID."""
        lead = await self.lead_repo.get(lead_id)
        if not lead or lead.org_id != org_id:
            raise_not_found("Lead", str(lead_id))
        return lead
    
    async def list(
        self,
        org_id: uuid.UUID,
        filters: Optional[LeadFilter] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """List leads with filtering and pagination."""
        return await self.lead_repo.search(org_id, filters, page, limit)
    
    async def update(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        lead_id: uuid.UUID,
        lead_data: LeadUpdate
    ) -> Lead:
        """Update a lead."""
        # Verify lead belongs to org
        lead = await self.lead_repo.get(lead_id)
        if not lead or lead.org_id != org_id:
            raise_not_found("Lead", str(lead_id))
        
        # Update
        update_data = lead_data.model_dump(exclude_unset=True)
        updated_lead = await self.lead_repo.update(lead_id, update_data)
        
        # Recalculate score if relevant fields changed
        score_fields = ["title", "company", "company_size", "location", "enrichment_status"]
        if any(f in update_data for f in score_fields):
            new_score = await self._calculate_score(org_id, updated_lead)
            await self.lead_repo.update_score(lead_id, new_score)
            updated_lead.score = new_score
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.LEAD_UPDATED,
            entity_type="lead",
            entity_id=lead_id,
            description=f"Lead '{lead.name}' updated",
            meta_data={"changes": list(update_data.keys())}
        )
        
        return updated_lead
    
    async def delete(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        lead_id: uuid.UUID
    ) -> bool:
        """Delete a lead."""
        lead = await self.lead_repo.get(lead_id)
        if not lead or lead.org_id != org_id:
            raise_not_found("Lead", str(lead_id))
        
        lead_name = lead.name
        success = await self.lead_repo.delete(lead_id)
        
        if success:
            await self.activity_repo.log(
                org_id=org_id,
                actor_id=user_id,
                action=Actions.LEAD_DELETED,
                entity_type="lead",
                entity_id=lead_id,
                description=f"Lead '{lead_name}' deleted"
            )
        
        return success
    
    async def enrich(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        lead_id: uuid.UUID
    ) -> Lead:
        """Enrich a lead with external data."""
        lead = await self.lead_repo.get(lead_id)
        if not lead or lead.org_id != org_id:
            raise_not_found("Lead", str(lead_id))
        
        # Mock enrichment (replace with real provider later)
        from backend.services.integrations.enrichment import get_enrichment_provider
        provider = get_enrichment_provider()
        
        try:
            enrichment_data = await provider.enrich(lead.linkedin_url)
            lead = await self.lead_repo.mark_enriched(lead_id, enrichment_data, "enriched")
            
            # Recalculate score
            new_score = await self._calculate_score(org_id, lead)
            await self.lead_repo.update_score(lead_id, new_score)
            lead.score = new_score
            
        except Exception as e:
            lead = await self.lead_repo.mark_enriched(lead_id, {}, "failed")
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.LEAD_ENRICHED,
            entity_type="lead",
            entity_id=lead_id,
            description=f"Lead '{lead.name}' enriched",
            meta_data={"status": lead.enrichment_status}
        )
        
        return lead
    
    async def import_csv(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        csv_content: str,
        campaign_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None
    ) -> LeadImportResponse:
        """Import leads from CSV content."""
        reader = csv.DictReader(io.StringIO(csv_content))
        
        imported = 0
        failed = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):  # start=2 because of header
            try:
                # Map CSV columns to lead fields
                lead_data = {
                    "name": row.get("name") or row.get("Name") or "",
                    "linkedin_url": row.get("linkedin_url") or row.get("LinkedIn") or "",
                    "email": row.get("email") or row.get("Email"),
                    "title": row.get("title") or row.get("Title"),
                    "company": row.get("company") or row.get("Company"),
                    "location": row.get("location") or row.get("Location"),
                    "org_id": org_id,
                    "source": "csv",
                    "campaign_id": campaign_id,
                    "tags": tags or []
                }
                
                # Validate required fields
                if not lead_data["name"] or not lead_data["linkedin_url"]:
                    raise ValueError("name and linkedin_url are required")
                
                # Check for duplicates
                existing = await self.lead_repo.get_by_linkedin_url(org_id, lead_data["linkedin_url"])
                if existing:
                    raise ValueError("Duplicate LinkedIn URL")
                
                lead = await self.lead_repo.create(lead_data)
                
                # Calculate score
                score = await self._calculate_score(org_id, lead)
                if score > 0:
                    await self.lead_repo.update_score(lead.id, score)
                
                imported += 1
                
            except Exception as e:
                failed += 1
                errors.append({"row": row_num, "error": str(e)})
        
        # Log activity
        await self.activity_repo.log(
            org_id=org_id,
            actor_id=user_id,
            action=Actions.LEAD_IMPORTED,
            entity_type="lead",
            description=f"Imported {imported} leads from CSV",
            meta_data={"imported": imported, "failed": failed}
        )
        
        return LeadImportResponse(
            total_rows=imported + failed,
            imported=imported,
            failed=failed,
            errors=errors[:10]  # Limit errors returned
        )
    
    async def export(
        self,
        org_id: uuid.UUID,
        filters: Optional[LeadFilter] = None
    ) -> str:
        """Export leads to CSV format."""
        leads = await self.lead_repo.export(org_id, filters)
        
        output = io.StringIO()
        fieldnames = [
            "name", "linkedin_url", "email", "title", "company",
            "location", "score", "status", "source", "created_at"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for lead in leads:
            writer.writerow({
                "name": lead.name,
                "linkedin_url": lead.linkedin_url,
                "email": lead.email,
                "title": lead.title,
                "company": lead.company,
                "location": lead.location,
                "score": lead.score,
                "status": lead.status,
                "source": lead.source,
                "created_at": lead.created_at.isoformat()
            })
        
        return output.getvalue()
    
    async def get_stats(self, org_id: uuid.UUID) -> dict:
        """Get lead statistics."""
        return await self.lead_repo.get_stats(org_id)
    
    async def _calculate_score(self, org_id: uuid.UUID, lead: Lead) -> int:
        """Calculate lead score based on rules."""
        rules = await self.scoring_repo.get_active(org_id)
        
        score = 0
        for rule in rules:
            if self._evaluate_rule(lead, rule):
                score += rule.score_delta
        
        # Also check persona matching
        personas = await self.persona_repo.get_active(org_id)
        for persona in personas:
            if self._match_persona(lead, persona):
                score += persona.score_bonus
                break  # Only match first persona
        
        return max(0, min(100, score))  # Clamp between 0-100
    
    def _evaluate_rule(self, lead: Lead, rule) -> bool:
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
    
    def _match_persona(self, lead: Lead, persona) -> bool:
        """Check if lead matches persona rules."""
        rules = persona.rules_json
        
        # Check title keywords
        if "title_keywords" in rules and lead.title:
            title_lower = lead.title.lower()
            if not any(kw.lower() in title_lower for kw in rules["title_keywords"]):
                return False
        
        # Check title exclusions
        if "title_exclude" in rules and lead.title:
            title_lower = lead.title.lower()
            if any(ex.lower() in title_lower for ex in rules["title_exclude"]):
                return False
        
        # Check company size
        if "company_size_min" in rules and lead.company_size:
            try:
                size = int(lead.company_size.split("-")[0])
                if size < rules["company_size_min"]:
                    return False
            except:
                pass
        
        return True
