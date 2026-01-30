from datetime import datetime
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Any, Optional
import logging
import uuid
import asyncio

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
        self.async_session_maker = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    async def analyze_posts(self, post_urls: List[str], org_id: uuid.UUID, campaign_id: Optional[uuid.UUID] = None, persona_id: Optional[uuid.UUID] = None):
        """
        Starts the analysis process for a list of URLs.
        Triggers a multi-step Apify workflow in the background.
        """
        started_ids = []
        async with self.async_session_maker() as session:
            for url in post_urls:
                # Create DB Record
                post = LinkedInPost(
                    post_url=url,
                    status="processing",
                    org_id=org_id,
                    persona_id=persona_id
                )
                session.add(post)
                await session.commit()
                await session.refresh(post)
                started_ids.append(post.id)
                
                # Trigger Workflow in Background
                asyncio.create_task(self._execute_apify_workflow(post.id, url, org_id, campaign_id, persona_id))
        
        return started_ids

    async def _execute_apify_workflow(self, post_id: uuid.UUID, url: str, org_id: uuid.UUID, campaign_id: Optional[uuid.UUID], persona_id: Optional[uuid.UUID]):
        """
        Executes the 3-step Apify workflow:
        1. Post Details
        2. Comments
        3. Reactions
        """
        logger.info(f"Starting Apify Workflow for Post {post_id}")
        
        try:
            # --- STEP 1: Post Details ---
            logger.info("Step 1: Fetching Post Details...")
            dataset_id = await apify_service.call_actor(
                "apimaestro/linkedin-post-detail",
                {"post_urls": [url]}
            )
            
            if not dataset_id:
                raise Exception("Failed to fetch Post Details from Apify (Step 1 failed). Check Apify logs or credits.")
            
            post_content = ""
            author_name = "Unknown"
            
            if dataset_id:
                items = await apify_service.get_dataset_items_async(dataset_id)
                if items:
                    data = items[0]
                    post_content = data.get("text", "") or data.get("post", {}).get("text", "")
                    author_name = data.get("author", {}).get("name", "Unknown")
                    
                    # Update Post Logic
                    async with self.async_session_maker() as session:
                        post = await session.get(LinkedInPost, post_id)
                        if post:
                            post.post_content = post_content
                            post.author_name = author_name
                            
                            # AI Analysis
                            ai_post_analysis = ai_analysis_service.analyze_post_content(post_content)
                            post.post_intent = ai_post_analysis.get("intent", "unknown")
                            post.ai_insights = ai_post_analysis
                            session.add(post)
                            await session.commit()

            # --- STEP 2: Comments ---
            logger.info("Step 2: Fetching Comments...")
            comments_dataset_id = await apify_service.call_actor(
                "apimaestro/linkedin-post-comments-replies-engagements-scraper-no-cookies",
                {
                    "postIds": [url],
                    "page_number": 1,
                    "sortOrder": "most relevant",
                    "limit": 2
                }
            )
            
            comments = []
            if comments_dataset_id:
                comments = await apify_service.get_dataset_items_async(comments_dataset_id)
                logger.info(f"Fetched {len(comments)} comments.")

            # --- STEP 3: Reactions ---
            logger.info("Step 3: Fetching Reactions...")
            reactions_dataset_id = await apify_service.call_actor(
                "apimaestro/linkedin-post-reactions",
                {
                    "post_urls": [url],
                    "page_number": 1,
                    "reaction_type": "ALL",
                    "limit": 5
                }
            )
            
            likes = []
            if reactions_dataset_id:
                likes = await apify_service.get_dataset_items_async(reactions_dataset_id)
                logger.info(f"Fetched {len(likes)} reactions.")

            # --- Processing ---
            new_leads_count = 0
            async with self.async_session_maker() as session:
                post = await session.get(LinkedInPost, post_id)
                if not post:
                    return

                persona = await session.get(Persona, persona_id) if persona_id else None
                interactions_count = 0
                
                # Process Comments
                for comment in comments:
                    try:
                        normalized_comment = {
                            "text": comment.get("text") or comment.get("comment", ""),
                            "author": {
                                "name": comment.get("author", {}).get("name"),
                                "headline": comment.get("author", {}).get("headline"),
                                "profileUrl": comment.get("author", {}).get("profile_url")
                            }
                        }
                        interaction = self._process_interaction(session, post, "COMMENT", normalized_comment, persona)
                        if interaction:
                            interactions_count += 1
                            # Temporary: Lower threshold to 30 to allow leads without OpenAI (fallback score is ~35)
                            if interaction.relevance_score >= 30:
                                was_created = await self._create_lead_from_interaction(session, interaction, post, campaign_id)
                                if was_created:
                                    new_leads_count += 1
                    except Exception as e:
                        logger.error(f"Error processing comment: {e}")

                # Process Likes
                for like in likes:
                    try:
                        normalized_like = {
                            "text": "",
                            "author": {
                                "name": like.get("reactor", {}).get("name"),
                                "headline": like.get("reactor", {}).get("headline"),
                                "profileUrl": like.get("reactor", {}).get("profile_url")
                            }
                        }
                        interaction = self._process_interaction(session, post, "LIKE", normalized_like, persona)
                        if interaction:
                            interactions_count += 1
                    except Exception as e:
                         logger.error(f"Error processing like: {e}")

                post.total_comments = len(comments)
                post.total_likes = len(likes)
                post.status = "completed"
                session.add(post)
                
                # UPDATE CAMPAIGN STATUS
                if campaign_id:
                    from backend.models.campaign import Campaign
                    campaign = await session.get(Campaign, campaign_id)
                    if campaign:
                        campaign.status = "completed"
                        campaign.leads_count = (campaign.leads_count or 0) + new_leads_count
                        session.add(campaign)
                        logger.info(f"Updated Campaign {campaign_id}: status=completed, leads={campaign.leads_count}")

                await session.commit()
                
            logger.info(f"Workflow Complete for Post {post_id}")

        except Exception as e:
            logger.error(f"Workflow Failed for Post {post_id}: {str(e)}")
            async with self.async_session_maker() as session:
                post = await session.get(LinkedInPost, post_id)
                if post:
                    post.status = "failed"
                    session.add(post)
                    await session.commit()
                # Fail campaign if needed
                if campaign_id:
                    from backend.models.campaign import Campaign
                    campaign = await session.get(Campaign, campaign_id)
                    if campaign:
                        campaign.status = "failed"
                        session.add(campaign)
                        await session.commit()

    async def process_webhook(self, dataset_id: str, run_id: str):
        """
        Legacy webhook handler.
        """
        pass

    async def process_manual_data(self, data: Dict[str, Any], org_id: uuid.UUID) -> Dict[str, Any]:
        """
        Process data sent manually from the extension.
        """
        url = data.get("url")
        extracted_data = data.get("extracted_data", {})
        
        print(f"  > Processing Manual Data for: {url}")
        
        # 1. Create or Get Post Record
        async with self.async_session_maker() as session:
            # Check if post exists
            statement = select(LinkedInPost).where(
                LinkedInPost.post_url == url, 
                LinkedInPost.org_id == org_id
            )
            result = await session.exec(statement)
            post = result.first()
            
            if not post:
                print("  > Creating new LinkedInPost record...")
                post = LinkedInPost(
                    post_url=url,
                    status="processing",
                    org_id=org_id
                )
                session.add(post)
                await session.commit()
                await session.refresh(post)
            else:
                print(f"  > Found existing LinkedInPost record: {post.id}")
            
            # 2. Update Metadata
            post.post_content = extracted_data.get("text", "")
            post.author_name = extracted_data.get("author", {}).get("name")
            
            # AI Analysis
            print("  > Running AI Analysis on post content...")
            ai_post_analysis = ai_analysis_service.analyze_post_content(post.post_content)
            post.post_intent = ai_post_analysis.get("intent", "unknown")
            post.ai_insights = ai_post_analysis
            post.status = "completed"
            
            # 3. Process Interactions
            interactions_count = 0
            new_leads = 0
            
            comments = extracted_data.get("comments", [])
            print(f"  > Processing {len(comments)} comments...")
            for comment in comments:
                interaction = self._process_interaction(session, post, "COMMENT", comment, None)
                if interaction:
                    interactions_count += 1
                    # Temporary: Lower threshold to 30
                    if interaction.relevance_score >= 30:
                        was_created = await self._create_lead_from_interaction(session, interaction, post, None) # No campaign ID for manual
                        if was_created:
                            new_leads += 1

            likes = extracted_data.get("likes", [])
            print(f"  > Processing {len(likes)} likes...")
            for like in likes:
                interaction = self._process_interaction(session, post, "LIKE", like, None)
                if interaction:
                    interactions_count += 1
            
            post.total_comments = len(comments)
            post.total_likes = len(likes)
            session.add(post)
            await session.commit()
            
            print(f"  > DONE. Processed {interactions_count} interactions. Created {new_leads} new leads.")
            
            return {
                "success": True,
                "post_id": str(post.id),
                "interactions_processed": interactions_count,
                "leads_created": new_leads
            }

    def _process_interaction(
        self, 
        session: AsyncSession, 
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

    async def _create_lead_from_interaction(self, session: AsyncSession, interaction: PostInteraction, post: LinkedInPost, campaign_id: Optional[uuid.UUID] = None) -> bool:
        """
        Auto-creates a Lead from a high-value interaction.
        Triggers Apollo enrichment if configured.
        Returns: True if a NEW lead was created, False if existing/failed.
        """
        # Check if lead already exists
        result = await session.exec(
            select(Lead).where(Lead.linkedin_url == interaction.actor_profile_url)
        )
        existing = result.first()
        
        if existing:
            logger.info(f"Lead already exists for {interaction.actor_profile_url}")
            interaction.lead_id = existing.id
            return False
        
        # Create new lead
        lead = Lead(
            org_id=post.org_id,
            campaign_id=campaign_id,  # Link to campaign if provided
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
        await session.commit()
        await session.refresh(lead)
        
        interaction.lead_id = lead.id
        session.add(interaction)
        
        logger.info(f"Created Lead {lead.id} from interaction {interaction.id}")
        
        # Trigger Apollo enrichment if enabled and lead meets criteria
        if settings.APOLLO_AUTO_ENRICH and lead.score >= settings.APOLLO_MIN_SCORE_FOR_ENRICH:
            await self._trigger_apollo_enrichment(lead.id)
            
        return True
    
    async def _trigger_apollo_enrichment(self, lead_id: uuid.UUID):
        """
        Triggers Apollo enrichment for a lead (async call).
        """
        try:
            from backend.services.apollo_service import apollo_service
            
            async with self.async_session_maker() as session:
                lead = await session.get(Lead, lead_id)
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
                    await session.commit()
                    logger.info(f"Auto-enriched lead {lead_id} via Apollo (score: {lead.score})")
                else:
                    logger.warning(f"Apollo auto-enrichment failed for lead {lead_id}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Failed to trigger Apollo enrichment: {str(e)}")

analysis_service = AnalysisService()

