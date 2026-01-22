import requests
import logging
from typing import Optional, Dict, Any, List
from backend.config import settings

logger = logging.getLogger(__name__)

class ApolloService:
    """
    Apollo.io enrichment service for extracting verified emails and phone numbers.
    API Docs: https://docs.apollo.io/reference/people-enrichment
    """
    
    def __init__(self):
        self.api_key = settings.APOLLO_API_KEY
        self.base_url = "https://api.apollo.io/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }
    
    def enrich_person(
        self,
        linkedin_url: Optional[str] = None,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company_name: Optional[str] = None,
        company_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich a single person using Apollo API.
        
        Args:
            linkedin_url: LinkedIn profile URL
            email: Known email (if available)
            first_name, last_name: Person's name
            company_name, company_domain: Company info
        
        Returns:
            {
                "success": bool,
                "person": {
                    "email": str,
                    "emails": [{"value": str, "type": str, "status": str}],
                    "phone_numbers": [{"raw_number": str, "sanitized_number": str, "type": str}],
                    "title": str,
                    "seniority": str,
                    "departments": [],
                    "organization": {...},
                    "linkedin_url": str
                },
                "credits_used": int
            }
        """
        if not self.api_key:
            logger.warning("Apollo API key not configured")
            return {"success": False, "error": "API key not configured"}
        
        # Build request payload
        payload = {
            "api_key": self.api_key,
            "reveal_personal_emails": True,
            "reveal_phone_number": True
        }
        
        # Add available identifiers
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url
        if email:
            payload["email"] = email
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if company_name:
            payload["organization_name"] = company_name
        if company_domain:
            payload["domain"] = company_domain
        
        try:
            response = requests.post(
                f"{self.base_url}/people/match",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                person = data.get("person")
                
                if person:
                    return {
                        "success": True,
                        "person": person,
                        "credits_used": data.get("credits_used", 1)
                    }
                else:
                    return {
                        "success": False,
                        "error": "No match found",
                        "credits_used": 0
                    }
            
            elif response.status_code == 429:
                # Rate limited
                logger.warning("Apollo API rate limit exceeded")
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "retry_after": response.headers.get("Retry-After", 60)
                }
            
            elif response.status_code == 402:
                # Credits exhausted
                logger.error("Apollo API credits exhausted")
                return {
                    "success": False,
                    "error": "Credits exhausted"
                }
            
            else:
                logger.error(f"Apollo API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}"
                }
        
        except requests.exceptions.Timeout:
            logger.error("Apollo API timeout")
            return {"success": False, "error": "Request timeout"}
        
        except Exception as e:
            logger.error(f"Apollo enrichment failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def bulk_enrich(self, people: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enrich up to 10 people at once.
        
        Args:
            people: List of person dicts with identifiers
        
        Returns:
            {
                "success": bool,
                "matches": [...],
                "credits_used": int
            }
        """
        if not self.api_key:
            return {"success": False, "error": "API key not configured"}
        
        if len(people) > 10:
            return {"success": False, "error": "Maximum 10 people per bulk request"}
        
        payload = {
            "api_key": self.api_key,
            "reveal_personal_emails": True,
            "reveal_phone_number": True,
            "details": people
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/people/bulk_match",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "matches": data.get("matches", []),
                    "credits_used": data.get("credits_used", len(people))
                }
            else:
                logger.error(f"Apollo bulk enrichment error: {response.status_code}")
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}"
                }
        
        except Exception as e:
            logger.error(f"Apollo bulk enrichment failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def extract_contact_info(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize contact information from Apollo response.
        
        Returns:
            {
                "primary_email": str,
                "all_emails": [{value, type, verified}],
                "primary_phone": str,
                "all_phones": [{number, type}],
                "confidence": float
            }
        """
        result = {
            "primary_email": None,
            "all_emails": [],
            "primary_phone": None,
            "all_phones": [],
            "confidence": 0.0
        }
        
        # Extract emails
        if person_data.get("email"):
            result["primary_email"] = person_data["email"]
        
        emails = person_data.get("emails", [])
        for email_obj in emails:
            result["all_emails"].append({
                "value": email_obj.get("email"),
                "type": email_obj.get("type", "work"),
                "verified": email_obj.get("status") == "verified"
            })
        
        # Extract phone numbers
        phone_numbers = person_data.get("phone_numbers", [])
        if phone_numbers:
            result["primary_phone"] = phone_numbers[0].get("sanitized_number")
        
        for phone_obj in phone_numbers:
            result["all_phones"].append({
                "number": phone_obj.get("sanitized_number"),
                "raw": phone_obj.get("raw_number"),
                "type": phone_obj.get("type", "mobile")
            })
        
        # Confidence based on data completeness
        confidence = 0.0
        if result["primary_email"]:
            confidence += 0.5
        if result["primary_phone"]:
            confidence += 0.3
        if person_data.get("title"):
            confidence += 0.1
        if person_data.get("organization"):
            confidence += 0.1
        
        result["confidence"] = min(confidence, 1.0)
        
        return result

apollo_service = ApolloService()
