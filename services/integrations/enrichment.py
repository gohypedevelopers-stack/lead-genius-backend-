"""
Enrichment provider implementations.
Mock provider included, ready for real providers.
"""
import asyncio
from typing import Dict, Any

from backend.services.integrations.base import EnrichmentProvider


class MockEnrichmentProvider(EnrichmentProvider):
    """
    Mock enrichment provider for development/testing.
    Returns fake data based on LinkedIn URL.
    """
    
    async def enrich(self, linkedin_url: str) -> Dict[str, Any]:
        """Mock enrichment - simulates API call delay."""
        # Simulate API latency
        await asyncio.sleep(0.5)
        
        # Check for error simulation
        if "error" in linkedin_url.lower():
            raise Exception("Enrichment failed - mock error")
        
        # Generate mock data based on URL
        username = linkedin_url.split("/")[-1] or "user"
        
        return {
            "work_email": f"{username}@company.com",
            "personal_email": f"{username}@gmail.com",
            "mobile_phone": "+1-555-0123",
            "company_size": "50-200",
            "company_industry": "Technology",
            "company_website": f"https://{username}corp.com",
            "location": "San Francisco, CA",
            "country": "United States",
            "city": "San Francisco",
            "twitter_handle": f"@{username}"
        }
    
    async def verify_email(self, email: str) -> bool:
        """Mock email verification."""
        await asyncio.sleep(0.2)
        
        # Simple mock validation
        return "@" in email and "." in email.split("@")[-1]


# Future providers (commented out, ready for implementation)
"""
class ApolloEnrichmentProvider(EnrichmentProvider):
    '''Apollo.io enrichment provider.'''
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.apollo.io/v1"
    
    async def enrich(self, linkedin_url: str) -> Dict[str, Any]:
        # Implement Apollo API call
        pass
    
    async def verify_email(self, email: str) -> bool:
        # Implement Apollo email verification
        pass


class ClearbitEnrichmentProvider(EnrichmentProvider):
    '''Clearbit enrichment provider.'''
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def enrich(self, linkedin_url: str) -> Dict[str, Any]:
        # Implement Clearbit API call
        pass
    
    async def verify_email(self, email: str) -> bool:
        # Implement Clearbit email verification
        pass
"""


# Provider factory
_current_provider: EnrichmentProvider = None


def get_enrichment_provider() -> EnrichmentProvider:
    """Get the current enrichment provider instance."""
    global _current_provider
    if _current_provider is None:
        # Default to mock provider
        # In production, read from config which provider to use
        _current_provider = MockEnrichmentProvider()
    return _current_provider


def set_enrichment_provider(provider: EnrichmentProvider) -> None:
    """Set the enrichment provider (for testing or switching providers)."""
    global _current_provider
    _current_provider = provider
