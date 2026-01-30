from openai import OpenAI
import google.generativeai as genai
from backend.config import settings
import logging
import json
import time

logger = logging.getLogger(__name__)

class AIAnalysisService:
    def __init__(self):
        self.provider = "openai"
        self.client = None
        self.model = settings.AI_MODEL
        
        # Initialize Gemini if configured (preferred or if OpenAI missing)
        if hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.client = genai.GenerativeModel(settings.AI_MODEL)
                self.provider = "gemini"
                logger.info("AI Service initialized with Gemini")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

        # Fallback/Default to OpenAI if Gemini not set but OpenAI is
        if not self.client and settings.OPENAI_API_KEY:
            try:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.provider = "openai"
                logger.info("AI Service initialized with OpenAI")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")

    def _generate_content(self, prompt: str, json_mode: bool = True) -> str:
        """Helper to generate content from either provider."""
        if not self.client:
            raise ValueError("AI Client not initialized")

        if self.provider == "gemini":
            # Gemini generation
            max_retries = 3
            base_delay = 60 # Seconds
            
            for attempt in range(max_retries):
                try:
                    # For JSON mode in Gemini, it's often best to just ask strict JSON in prompt
                    # and maybe strip markdown blocks.
                    response = self.client.generate_content(prompt)
                    text = response.text
                    # Clean markdown code blocks if present
                    if text.startswith("```json"):
                        text = text[7:]
                    if text.startswith("```"):
                        text = text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    return text.strip()
                except Exception as e:
                    is_rate_limit = "429" in str(e) or "quota" in str(e).lower()
                    if is_rate_limit and attempt < max_retries - 1:
                        logger.warning(f"Gemini Rate Limit Hit. Waiting {base_delay}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(base_delay)
                    else:
                        logger.error(f"Gemini generation failed: {e}")
                        raise

        else:
            # OpenAI generation
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.2
            )
            return response.choices[0].message.content

    def score_lead(self, lead_data: dict, interactions: list) -> dict:
        """
        Score a lead based on profile and interactions using AI.
        Returns JSON with score (0-100) and reasoning.
        """
        if not self.client:
            return {"score": 50, "reasoning": "AI not configured, using neutral score."}

        prompt = f"""
        Act as a B2B Sales Scoring Expert. Evaluate this lead validation score (0-100).
        
        LEAD PROFILE:
        Name: {lead_data.get('name')}
        Title: {lead_data.get('title')}
        Company: {lead_data.get('company')}
        Headline: {lead_data.get('headline', '')}
        About: {lead_data.get('about', '')} (truncated)
        
        INTERACTIONS:
        {json.dumps(interactions, default=str)}
        
        SCORING CRITERIA:
        1. ICP Fit (40%): Is this a decision maker (VP, C-Level, Director) in a relevant industry?
        2. Engagement (40%): Did they comment or react? Comments are high intent.
        3. Completeness (20%): Do we have email, LinkedIn URL, etc?
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "score": <integer 0-100>,
            "reasoning": "<concise explanation of the score>",
            "quality_tier": "<High/Medium/Low>"
        }}
        """
        
        try:
            result_text = self._generate_content(prompt)
            return json.loads(result_text)
        except Exception as e:
            logger.error(f"AI scoring failed: {e}")
            return {"score": 50, "reasoning": "AI scoring failed, check logs."}

    def analyze_post_content(self, post_text: str, customer_product: str = "") -> dict:
        """Uses AI to analyze post content."""
        if not self.client:
            logger.warning("OpenAI not configured, skipping AI analysis")
            return {"intent": "unknown", "topics": [], "relevance_score": 50, "summary": ""}
        
        prompt = f"""Analyze this LinkedIn post and return a JSON response:

Post: "{post_text}"
Customer Product/Service: "{customer_product or 'General B2B SaaS'}"

Return JSON with:
- intent: one of [problem, solution_seeking, discussion, success_story, promotion, question]
- topics: list of 3-5 main topics/keywords
- relevance_score: 0-100 how relevant to customer's product
- summary: one-line summary
"""
        try:
            result_text = self._generate_content(prompt)
            return json.loads(result_text)
        except Exception as e:
            logger.error(f"AI post analysis failed: {e}")
            return {"intent": "unknown", "topics": [], "relevance_score": 50, "summary": ""}
    
    def evaluate_profile(self, name: str, headline: str, comment_text: str, persona_definition: dict) -> dict:
        """AI-powered profile evaluation."""
        if not self.client:
            return self._fallback_evaluation(headline)
        
        prompt = f"""Evaluate this LinkedIn profile interaction:

Name: {name}
Headline: {headline}
Their Comment: "{comment_text}"

Target Persona:
- Industries: {persona_definition.get('industries', [])}
- Job Titles: {persona_definition.get('job_titles', [])}
- Seniority: {persona_definition.get('seniority', [])}

Return JSON with:
- profile_type: "individual" or "company"
- role_category: e.g., "decision_maker", "influencer", "end_user", "irrelevant"
- seniority_level: "C-level", "VP", "Director", "Manager", "IC", "Student"
- industry_match: true/false
- intent_from_comment: "high" (asking, seeking solution), "medium" (sharing opinion), "low" (general engagement)
- persona_fit_score: 0-100
- reasoning: brief explanation
"""
        
        try:
            result_text = self._generate_content(prompt)
            return json.loads(result_text)
        except Exception as e:
            logger.error(f"AI profile evaluation failed: {e}")
            return self._fallback_evaluation(headline)
    
    def _fallback_evaluation(self, headline: str) -> dict:
        """Simple rule-based fallback if AI fails"""
        seniority = "IC"
        if any(x in headline for x in ["CEO", "Founder", "President"]):
            seniority = "C-level"
        elif any(x in headline for x in ["VP", "Vice President"]):
            seniority = "VP"
        elif "Director" in headline:
            seniority = "Director"
        elif "Manager" in headline:
            seniority = "Manager"
        
        excluded = any(x in headline.lower() for x in ["student", "recruiter", "intern"])
        
        return {
            "profile_type": "company" if "Company" in headline or "Ltd" in headline else "individual",
            "role_category": "irrelevant" if excluded else "influencer",
            "seniority_level": seniority,
            "industry_match": False,
            "intent_from_comment": "medium",
            "persona_fit_score": 0 if excluded else 50,
            "reasoning": "Fallback evaluation (AI unavailable)"
        }

ai_analysis_service = AIAnalysisService()
