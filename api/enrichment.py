from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import logging
import uuid
from datetime import datetime
from sqlmodel import Session, select

from backend.services.apollo_service import apollo_service
from backend.models.lead import Lead
from backend.database import engine
from backend.config import settings

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])
logger = logging.getLogger(__name__)

class EnrichRequest(BaseModel):
    lead_id: str  # UUID as string

class BulkEnrichRequest(BaseModel):
    lead_ids: List[str]  # Max 10

@router.post("/apollo/single")
async def enrich_single_lead(request: EnrichRequest, background_tasks: BackgroundTasks):
    """
    Enrich a single lead using Apollo.io API.
    Returns immediately and processes in background.
    """
    try:
        lead_uuid = uuid.UUID(request.lead_id)
        
        # Queue enrichment as background task
        background_tasks.add_task(_enrich_lead_task, lead_uuid)
        
        return {
            "status": "queued",
            "lead_id": str(lead_uuid),
            "message": "Enrichment started in background"
        }
    except Exception as e:
        logger.error(f"Failed to queue enrichment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/apollo/bulk")
async def enrich_bulk_leads(request: BulkEnrichRequest, background_tasks: BackgroundTasks):
    """
    Enrich up to 10 leads using Apollo.io bulk API.
    """
    if len(request.lead_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 leads per bulk request")
    
    try:
        lead_uuids = [uuid.UUID(lid) for lid in request.lead_ids]
        
        background_tasks.add_task(_bulk_enrich_task, lead_uuids)
        
        return {
            "status": "queued",
            "count": len(lead_uuids),
            "message": "Bulk enrichment started"
        }
    except Exception as e:
        logger.error(f"Failed to queue bulk enrichment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{lead_id}")
async def get_enrichment_status(lead_id: str):
    """
    Get enrichment status for a lead.
    """
    try:
        lead_uuid = uuid.UUID(lead_id)
        
        with Session(engine) as session:
            lead = session.get(Lead, lead_uuid)
            
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
            
            return {
                "lead_id": str(lead.id),
                "enrichment_status": lead.enrichment_status,
                "apollo_enriched_at": lead.apollo_enriched_at.isoformat() if lead.apollo_enriched_at else None,
                "apollo_confidence": lead.apollo_match_confidence,
                "has_email": bool(lead.email),
                "has_phone": bool(lead.mobile_phone or lead.phone_numbers),
                "credits_used": lead.apollo_credits_used
            }
    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Background tasks

def _enrich_lead_task(lead_id: uuid.UUID):
    """
    Background task to enrich a single lead.
    """
    try:
        with Session(engine) as session:
            lead = session.get(Lead, lead_id)
            
            if not lead:
                logger.error(f"Lead {lead_id} not found for enrichment")
                return
            
            # Call Apollo API
            result = apollo_service.enrich_person(
                linkedin_url=lead.linkedin_url,
                email=lead.email,
                first_name=lead.name.split()[0] if lead.name else None,
                last_name=" ".join(lead.name.split()[1:]) if lead.name and len(lead.name.split()) > 1 else None,
                company_name=lead.company
            )
            
            if result["success"]:
                person_data = result["person"]
                contact_info = apollo_service.extract_contact_info(person_data)
                
                # Update lead with enriched data
                if contact_info["primary_email"] and not lead.email:
                    lead.email = contact_info["primary_email"]
                    lead.is_email_verified = True
                
                if contact_info["primary_phone"] and not lead.mobile_phone:
                    lead.mobile_phone = contact_info["primary_phone"]
                
                # Store all phone numbers
                if contact_info["all_phones"]:
                    lead.phone_numbers = contact_info["all_phones"]
                
                # Update title if not present
                if person_data.get("title") and not lead.title:
                    lead.title = person_data["title"]
                
                # Update company info
                org = person_data.get("organization", {})
                if org:
                    if not lead.company and org.get("name"):
                        lead.company = org["name"]
                    if not lead.company_website and org.get("website_url"):
                        lead.company_website = org["website_url"]
                    if not lead.company_industry and org.get("industry"):
                        lead.company_industry = org["industry"]
                
                # Update enrichment metadata
                lead.enrichment_status = "enriched"
                lead.enriched_at = datetime.utcnow()
                lead.apollo_enriched_at = datetime.utcnow()
                lead.apollo_match_confidence = contact_info["confidence"]
                lead.apollo_credits_used += result.get("credits_used", 1)
                
                logger.info(f"Successfully enriched lead {lead_id} via Apollo")
            else:
                # Enrichment failed
                lead.enrichment_status = "failed"
                logger.warning(f"Apollo enrichment failed for lead {lead_id}: {result.get('error')}")
            
            session.add(lead)
            session.commit()
    
    except Exception as e:
        logger.error(f"Enrichment task failed for lead {lead_id}: {str(e)}")

def _bulk_enrich_task(lead_ids: List[uuid.UUID]):
    """
    Background task to bulk enrich leads.
    """
    try:
        with Session(engine) as session:
            leads = session.exec(
                select(Lead).where(Lead.id.in_(lead_ids))
            ).all()
            
            if not leads:
                logger.error("No leads found for bulk enrichment")
                return
            
            # Build bulk request
            people = []
            for lead in leads:
                person = {}
                if lead.linkedin_url:
                    person["linkedin_url"] = lead.linkedin_url
                if lead.email:
                    person["email"] = lead.email
                if lead.name:
                    name_parts = lead.name.split()
                    person["first_name"] = name_parts[0]
                    if len(name_parts) > 1:
                        person["last_name"] = " ".join(name_parts[1:])
                if lead.company:
                    person["organization_name"] = lead.company
                
                people.append(person)
            
            # Call Apollo bulk API
            result = apollo_service.bulk_enrich(people)
            
            if result["success"]:
                matches = result["matches"]
                credits_per_lead = result["credits_used"] // len(leads) if leads else 0
                
                for idx, lead in enumerate(leads):
                    if idx < len(matches):
                        match = matches[idx]
                        if match:
                            contact_info = apollo_service.extract_contact_info(match)
                            
                            # Update lead (same logic as single enrichment)
                            if contact_info["primary_email"] and not lead.email:
                                lead.email = contact_info["primary_email"]
                            if contact_info["primary_phone"] and not lead.mobile_phone:
                                lead.mobile_phone = contact_info["primary_phone"]
                            if contact_info["all_phones"]:
                                lead.phone_numbers = contact_info["all_phones"]
                            
                            lead.enrichment_status = "enriched"
                            lead.apollo_enriched_at = datetime.utcnow()
                            lead.apollo_match_confidence = contact_info["confidence"]
                            lead.apollo_credits_used += credits_per_lead
                        else:
                            lead.enrichment_status = "failed"
                    
                    session.add(lead)
                
                session.commit()
                logger.info(f"Bulk enriched {len(matches)} leads via Apollo")
            else:
                logger.error(f"Apollo bulk enrichment failed: {result.get('error')}")
    
    except Exception as e:
        logger.error(f"Bulk enrichment task failed: {str(e)}")
