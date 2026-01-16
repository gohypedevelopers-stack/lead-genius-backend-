"""
Lead repository with search and bulk operations.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from sqlmodel import select, or_, and_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func

from backend.models.lead import Lead
from backend.repositories.base import BaseRepository
from backend.schemas.lead import LeadFilter
from backend.core.pagination import create_paginated_response


class LeadRepository(BaseRepository[Lead]):
    """Repository for Lead operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Lead, session)
    
    async def search(
        self,
        org_id: uuid.UUID,
        filters: Optional[LeadFilter] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        """Search leads with advanced filtering."""
        query = select(Lead).where(Lead.org_id == org_id)
        
        if filters:
            if filters.status:
                query = query.where(Lead.status == filters.status)
            if filters.source:
                query = query.where(Lead.source == filters.source)
            if filters.campaign_id:
                query = query.where(Lead.campaign_id == filters.campaign_id)
            if filters.min_score is not None:
                query = query.where(Lead.score >= filters.min_score)
            if filters.max_score is not None:
                query = query.where(Lead.score <= filters.max_score)
            if filters.enrichment_status:
                query = query.where(Lead.enrichment_status == filters.enrichment_status)
            if filters.created_after:
                query = query.where(Lead.created_at >= filters.created_after)
            if filters.created_before:
                query = query.where(Lead.created_at <= filters.created_before)
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        Lead.name.ilike(search_term),
                        Lead.email.ilike(search_term),
                        Lead.company.ilike(search_term),
                        Lead.title.ilike(search_term)
                    )
                )
            if filters.tags:
                # Check if any of the filter tags are in lead's tags
                for tag in filters.tags:
                    query = query.where(Lead.tags.contains([tag]))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.exec(count_query)
        total = total_result.one()
        
        # Apply ordering and pagination
        query = query.order_by(Lead.created_at.desc())
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        result = await self.session.exec(query)
        items = result.all()
        
        return create_paginated_response(items, total, page, limit)
    
    async def bulk_create(self, org_id: uuid.UUID, leads_data: List[dict]) -> List[Lead]:
        """Create multiple leads at once."""
        leads = []
        for data in leads_data:
            data['org_id'] = org_id
            lead = Lead(**data)
            self.session.add(lead)
            leads.append(lead)
        
        await self.session.commit()
        for lead in leads:
            await self.session.refresh(lead)
        
        return leads
    
    async def get_by_linkedin_url(self, org_id: uuid.UUID, linkedin_url: str) -> Optional[Lead]:
        """Get lead by LinkedIn URL (for deduplication)."""
        query = select(Lead).where(
            Lead.org_id == org_id,
            Lead.linkedin_url == linkedin_url
        )
        result = await self.session.exec(query)
        return result.first()
    
    async def get_by_email(self, org_id: uuid.UUID, email: str) -> Optional[Lead]:
        """Get lead by email (for deduplication)."""
        query = select(Lead).where(
            Lead.org_id == org_id,
            Lead.email == email
        )
        result = await self.session.exec(query)
        return result.first()
    
    async def update_score(self, lead_id: uuid.UUID, score: int) -> bool:
        """Update lead score."""
        lead = await self.get(lead_id)
        if lead:
            lead.score = score
            lead.updated_at = datetime.utcnow()
            self.session.add(lead)
            await self.session.commit()
            return True
        return False
    
    async def update_status(self, lead_id: uuid.UUID, status: str) -> bool:
        """Update lead status."""
        lead = await self.get(lead_id)
        if lead:
            lead.status = status
            lead.updated_at = datetime.utcnow()
            if status == "contacted":
                lead.last_contacted_at = datetime.utcnow()
            self.session.add(lead)
            await self.session.commit()
            return True
        return False
    
    async def mark_enriched(
        self, 
        lead_id: uuid.UUID, 
        enrichment_data: dict,
        status: str = "enriched"
    ) -> Optional[Lead]:
        """Update lead with enrichment data."""
        lead = await self.get(lead_id)
        if not lead:
            return None
        
        # Update enrichment fields
        for field, value in enrichment_data.items():
            if hasattr(lead, field) and value is not None:
                setattr(lead, field, value)
        
        lead.enrichment_status = status
        lead.enriched_at = datetime.utcnow()
        lead.updated_at = datetime.utcnow()
        
        self.session.add(lead)
        await self.session.commit()
        await self.session.refresh(lead)
        return lead
    
    async def get_stats(self, org_id: uuid.UUID) -> dict:
        """Get lead statistics for dashboard."""
        # Total leads
        total = await self.count(org_id)
        
        # By status
        status_counts = {}
        for status in ["new", "contacted", "replied", "qualified", "closed", "lost"]:
            count = await self.count(org_id, {"status": status})
            status_counts[status] = count
        
        # By enrichment status
        enriched = await self.count(org_id, {"enrichment_status": "enriched"})
        
        # Average score
        avg_query = select(func.avg(Lead.score)).where(Lead.org_id == org_id)
        result = await self.session.exec(avg_query)
        avg_score = result.one() or 0
        
        # Qualified (score >= 80)
        qualified_query = select(func.count()).where(
            Lead.org_id == org_id,
            Lead.score >= 80
        )
        result = await self.session.exec(qualified_query)
        qualified = result.one()
        
        return {
            "total": total,
            "qualified": qualified,
            "enriched": enriched,
            "avg_score": round(float(avg_score), 1),
            "by_status": status_counts
        }
    
    async def export(self, org_id: uuid.UUID, filters: Optional[LeadFilter] = None) -> List[Lead]:
        """Export all leads matching filters."""
        query = select(Lead).where(Lead.org_id == org_id)
        
        if filters:
            if filters.status:
                query = query.where(Lead.status == filters.status)
            if filters.campaign_id:
                query = query.where(Lead.campaign_id == filters.campaign_id)
        
        query = query.order_by(Lead.created_at.desc())
        result = await self.session.exec(query)
        return result.all()
