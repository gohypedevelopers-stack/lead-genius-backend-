from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from backend.services.apify_service import apify_service
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

router = APIRouter(prefix="/ingest/apify", tags=["Apify Integration"])
logger = logging.getLogger(__name__)

class ScrapeRequest(BaseModel):
    actor_id: str
    run_input: Dict[str, Any]

@router.post("/trigger")
async def trigger_scrape(request: ScrapeRequest):
    """
    Manually trigger an Apify scrape.
    Example Actor IDs:
    - LinkedIn: 'curious_programmer/linkedin-profile-scraper'
    - Google Maps: 'compass/google-maps-scraper'
    """
    result = apify_service.run_actor(request.actor_id, request.run_input)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/webhook")
async def apify_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint called by Apify when a run completes.
    Payload typically contains {"eventType": "ACTOR.RUN.SUCCEEDED", "resource": {...}}
    """
    payload = await request.json()
    logger.info(f"Received Apify webhook: {payload}")
    
    event_type = payload.get("eventType")
    resource = payload.get("resource", {})
    run_id = resource.get("id")
    dataset_id = resource.get("defaultDatasetId")

    if event_type == "ACTOR.RUN.SUCCEEDED" and dataset_id:
        # Fetching data can be slow, so we do it in the background
        background_tasks.add_task(process_apify_dataset, dataset_id, run_id)
    
    return {"status": "received"}

async def process_apify_dataset(dataset_id: str, run_id: str):
    """
    Background task to fetch and process data from Apify.
    """
    logger.info(f"Processing dataset {dataset_id} for run {run_id}")
    items = apify_service.get_dataset_items(dataset_id)
    logger.info(f"Retrieved {len(items)} items from Apify run {run_id}")
    
    # Save to CampaignRun
    from backend.database import get_session
    from backend.campaigns.run_models import CampaignRun
    from sqlmodel import select
    from datetime import datetime

    session_gen = get_session()
    session = next(session_gen)
    
    try:
        statement = select(CampaignRun).where(CampaignRun.apify_run_id == run_id)
        run_record = session.exec(statement).first()
        
        if run_record:
            run_record.result_data = {"items": items}
            run_record.status = "completed"
            run_record.completed_at = datetime.utcnow()
            session.add(run_record)
            session.commit()
            logger.info(f"Saved execution data for run {run_id}")
            
            # Update Campaign status as well
            if run_record.campaign_id:
                # Need to import Campaign to update it
                from backend.models.campaign import Campaign
                from backend.models.lead import Lead, LeadInteraction
                
                campaign = session.get(Campaign, run_record.campaign_id)
                if campaign:
                    # Process items to create Leads and Interactions
                    new_leads_count = 0
                    
                    for item in items:
                        # 1. IDENTIFY THE PERSON
                        linkedin_url = (
                            item.get("authorProfileUrl") or 
                            item.get("profileUrl") or 
                            item.get("url") or
                            item.get("linkedInUrl")
                        )
                        
                        if not linkedin_url:
                            continue

                        # 2. DETERMINE INTERACTION TYPE
                        # 'text' usually implies a comment. 'reactionType' implies a reaction.
                        interaction_type = "unknown"
                        if "text" in item and item.get("type") != "Post": # It's likely a comment
                            interaction_type = "comment"
                        elif "reactionType" in item:
                            interaction_type = "reaction"
                        elif item.get("type") == "Post" or "postContent" in item: # It's the post author
                            interaction_type = "post_author"
                        else:
                            interaction_type = "profile_visit" # Default fallback for just a profile scrape

                        # 3. UPSERT LEAD (Save Everything)
                        # Check if lead already exists
                        lead = session.exec(
                            select(Lead).where(
                                Lead.campaign_id == campaign.id,
                                Lead.linkedin_url == linkedin_url
                            )
                        ).first()

                        name = (
                            item.get("authorFullName") or 
                            item.get("fullName") or 
                            item.get("name") or 
                            item.get("title") or 
                            "Unknown Lead"
                        )
                        
                        title = (
                            item.get("authorHeadline") or 
                            item.get("headline") or 
                            item.get("subTitle")
                        )

                        if not lead:
                            lead = Lead(
                                org_id=campaign.org_id,
                                campaign_id=campaign.id,
                                name=name,
                                linkedin_url=linkedin_url,
                                title=title,
                                source="apify_cloud",
                                status="new",
                                profile_data=item # SAVE EVERYTHING: Full parsed item
                            )
                            session.add(lead)
                            new_leads_count += 1
                        else:
                            # Update existing lead with new enriched data if available
                            # Merge logic: favor new non-empty data
                            if len(str(item)) > len(str(lead.profile_data or "")):
                                lead.profile_data = item
                            if title and not lead.title:
                                lead.title = title
                            session.add(lead)
                        
                        # Flush to get lead.id
                        session.flush()

                        # 4. RECORD INTERACTION (The Signal)
                        # Only record if it's a meaningful interaction (not just a profile scrape of a static list)
                        if interaction_type in ["comment", "reaction", "post_author"]:
                            content = item.get("text") or item.get("postContent")
                            source_url = item.get("url") or item.get("permalink")
                            
                            interaction = LeadInteraction(
                                lead_id=lead.id,
                                campaign_id=campaign.id,
                                type=interaction_type,
                                content=content,
                                source_url=source_url,
                                raw_data=item # SAVE EVERYTHING: The specific event data
                            )
                            session.add(interaction)

                    # Update campaign stats
                    campaign.leads_count += new_leads_count
                    if campaign.status != "completed":
                        campaign.status = "active"
                    
                    session.add(campaign)
                    session.commit()
                    logger.info(f"Created {new_leads_count} new leads for campaign {campaign.id}")

        else:
            logger.warning(f"No CampaignRun found for run_id {run_id}")
            
    except Exception as e:
        logger.error(f"Error saving run results: {e}")
    finally:
        session.close()
