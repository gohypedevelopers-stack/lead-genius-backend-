from datetime import datetime
from sqlmodel import Session, select
from typing import List, Dict, Any, Optional
import logging
import uuid

from backend.models.post_analysis import LinkedInPost, PostInteraction
from backend.models.lead import Lead
from backend.models.persona import Persona
from backend.services.apify_service import apify_service
from backend.services.ai_analysis_service import ai_analysis_service
from backend.database import engine
from backend.config import settings

logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(self):
        self.actor_id = "curious_programmer/linkedin-post-scraper"

    async def analyze_posts(self, post_urls: List[str], org_id: uuid.UUID, persona_id: Optional[uuid.UUID] = None):
        """
        Starts the analysis process for a list of URLs.
        1. Creates LinkedInPost records.
        2. Triggers Apify for each.
        """
        started_ids = []
        with Session(engine) as session:
            for url in post_urls:
                # Create DB Record
                post = LinkedInPost(
                    post_url=url,
                    status="processing",
                    org_id=org_id,
                    persona_id=persona_id
                )
                session.add(post)
                session.commit()
                session.refresh(post)
                
                # Trigger Apify
                run_input = {
                    "postUrl": url, 
                    "proxy": {"useApifyProxy": True}
                }
                result = apify_service.run_actor(
                    self.actor_id, 
                    run_input,
                    webhook_url=f"{settings.BACKEND_URL}{settings.API_PREFIX}/ingest/analysis/webhook"
                )
                
                if result["success"]:
                    post.apify_run_id = result["run_id"]
                    started_ids.append(post.id)
                else:
                    post.status = "failed"
                
                session.add(post)
                session.commit()
        
        return started_ids

    async def process_webhook(self, dataset_id: str, run_id: str):
        """
        Called when Apify finishes. Fetches data and processes interactions.
        NOW WITH AI ANALYSIS
        """
        items = apify_service.get_dataset_items(dataset_id)
        if not items:
            logger.warning(f"No items found for run {run_id}")
            return

        with Session(engine) as session:
            # Find the post by run_id
            statement = select(LinkedInPost).where(LinkedInPost.apify_run_id == run_id)
            post = session.exec(statement).first()
            
            if not post:
                logger.error(f"No LinkedInPost found for run {run_id}")
                return

            # Get Persona for matching
            persona = None
            if post.persona_id:
                persona = session.get(Persona, post.persona_id)

            # Update Post Metadata
            first_item = items[0]
            post_text = first_item.get("text", "")
            post.post_content = post_text
            post.author_name = first_item.get("author", {}).get("name")
            
            # AI: Analyze post content
            ai_post_analysis = ai_analysis_service.analyze_post_content(post_text)
            post.post_intent = ai_post_analysis.get("intent", "unknown")
            post.ai_insights = ai_post_analysis  # Store full AI results
            post.status = "completed"
            
            # Process Comments & Likes
            interactions_count = 0
            
            # 1. Process Comments (HIGH INTENT)
            comments = first_item.get("comments", [])
            for comment in comments:
                interaction = self._process_interaction(session, post, "COMMENT", comment, persona)
                if interaction:
                    interactions_count += 1
                    # Auto-create lead if high score
                    if interaction.classification == "high" and interaction.relevance_score >= 70:
                        self._create_lead_from_interaction(session, interaction, post)
            
            # 2. Process Likes (LOW INTENT)
            likes = first_item.get("likes", [])
            for like in likes:
                interaction = self._process_interaction(session, post, "LIKE", like, persona)
                if interaction:
                    interactions_count += 1
                
            post.total_comments = len(comments)
            post.total_likes = len(likes)
            session.add(post)
            session.commit()
            
            logger.info(f"Processed {interactions_count} interactions for post {post.id}")

    def _process_interaction(
        self, 
        session: Session, 
        post: LinkedInPost, 
        type: str, 
        data: Dict[str, Any],
        persona: Optional[Persona]
    ) -> Optional[PostInteraction]:
        """
        Evaluates a single interaction using AI and saves it.
        """
        author = data.get("author", {})
        name = author.get("name")
        headline = author.get("headline", "") or ""
        profile_url = author.get("profileUrl")
        comment_text = data.get("text", "")
        
        # Build persona definition for AI
        persona_def = {}
        if persona:
            persona_def = {
                "industries": persona.rules_json.get("industries", []),
                "job_titles": persona.rules_json.get("title_keywords", []),
                "seniority": persona.rules_json.get("seniority_levels", ["Manager", "Director", "VP", "C-level"]),
                "excluded": persona.rules_json.get("title_exclude", [])
            }
        
        # AI Evaluation
        ai_eval = ai_analysis_service.evaluate_profile(
            name=name,
            headline=headline,
            comment_text=comment_text,
            persona_definition=persona_def
        )
        
        # Base score
        relevance_score = 10 if type == "COMMENT" else 3
        
        # Add AI persona fit score
        relevance_score += ai_eval.get("persona_fit_score", 0) // 2  # Scale down
        
        # Intent boost
        if ai_eval.get("intent_from_comment") == "high":
            relevance_score += 20
        
        # Determine classification
        classification = "low"
        if ai_eval.get("role_category") == "irrelevant":
            classification = "irrelevant"
            relevance_score = 0
        elif relevance_score >= 70:
            classification = "high"
        elif relevance_score >= 40:
            classification = "medium"
        
        # Create Interaction Record
        interaction = PostInteraction(
            post_id=post.id,
            type=type,
            content=comment_text,
            actor_name=name,
            actor_headline=headline,
            actor_profile_url=profile_url,
            profile_type=ai_eval.get("profile_type", "individual"),
            seniority_level=ai_eval.get("seniority_level"),
            role_category=ai_eval.get("role_category"),
            classification=classification,
            relevance_score=relevance_score,
            ai_insights=ai_eval  # Store full AI evaluation
        )
        session.add(interaction)
        return interaction

    def _create_lead_from_interaction(self, session: Session, interaction: PostInteraction, post: LinkedInPost):
        """
        Auto-creates a Lead from a high-value interaction.
        Triggers Apollo enrichment if configured.
        """
        # Check if lead already exists
        existing = session.exec(
            select(Lead).where(Lead.linkedin_url == interaction.actor_profile_url)
        ).first()
        
        if existing:
            logger.info(f"Lead already exists for {interaction.actor_profile_url}")
            interaction.lead_id = existing.id
            return
        
        # Create new lead
        lead = Lead(
            org_id=post.org_id,
            name=interaction.actor_name or "Unknown",
            linkedin_url=interaction.actor_profile_url or "",
            title=interaction.actor_headline,
            score=interaction.relevance_score,
            source="linkedin_post_analysis",
            status="new",
            enrichment_status="pending",
            custom_fields={
                "discovered_from_post": str(post.id),
                "interaction_type": interaction.type,
                "ai_insights": interaction.ai_insights
            },
            tags=["ai_discovered", interaction.classification, interaction.type.lower()]
        )
        
        session.add(lead)
        session.commit()
        session.refresh(lead)
        
        interaction.lead_id = lead.id
        session.add(interaction)
        
        logger.info(f"Created Lead {lead.id} from interaction {interaction.id}")
        
        # Trigger Apollo enrichment if enabled and lead meets criteria
        if settings.APOLLO_AUTO_ENRICH and lead.score >= settings.APOLLO_MIN_SCORE_FOR_ENRICH:
            self._trigger_apollo_enrichment(lead.id)
    
    def _trigger_apollo_enrichment(self, lead_id: uuid.UUID):
        """
        Triggers Apollo enrichment for a lead (async call).
        """
        try:
            from backend.services.apollo_service import apollo_service
            
            with Session(engine) as session:
                lead = session.get(Lead, lead_id)
                if not lead:
                    return
                
                # Call Apollo API
                result = apollo_service.enrich_person(
                    linkedin_url=lead.linkedin_url,
                    first_name=lead.name.split()[0] if lead.name else None,
                    last_name=" ".join(lead.name.split()[1:]) if lead.name and len(lead.name.split()) > 1 else None,
                    company_name=lead.company
                )
                
                if result["success"]:
                    person_data = result["person"]
                    contact_info = apollo_service.extract_contact_info(person_data)
                    
                    # Update lead
                    if contact_info["primary_email"]:
                        lead.email = contact_info["primary_email"]
                        lead.is_email_verified = True
                    if contact_info["primary_phone"]:
                        lead.mobile_phone = contact_info["primary_phone"]
                    if contact_info["all_phones"]:
                        lead.phone_numbers = contact_info["all_phones"]
                    
                    lead.enrichment_status = "enriched"
                    lead.enriched_at = datetime.utcnow()
                    lead.apollo_enriched_at = datetime.utcnow()
                    lead.apollo_match_confidence = contact_info["confidence"]
                    lead.apollo_credits_used = result.get("credits_used", 1)
                    
                    session.add(lead)
                    session.commit()
                    logger.info(f"Auto-enriched lead {lead_id} via Apollo (score: {lead.score})")
                else:
                    logger.warning(f"Apollo auto-enrichment failed for lead {lead_id}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Failed to trigger Apollo enrichment: {str(e)}")

analysis_service = AnalysisService()

