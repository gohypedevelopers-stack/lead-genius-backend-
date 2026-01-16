"""
Base interfaces for integration providers.
Abstract base classes for third-party service integrations.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class EnrichmentProvider(ABC):
    """Base interface for lead enrichment providers (Apollo, Clearbit, etc.)"""
    
    @abstractmethod
    async def enrich(self, linkedin_url: str) -> Dict[str, Any]:
        """
        Enrich a lead using their LinkedIn URL.
        
        Returns:
            Dictionary with enrichment data:
            {
                "work_email": str,
                "personal_email": str,
                "mobile_phone": str,
                "company_size": str,
                "company_industry": str,
                "location": str,
                etc.
            }
        """
        pass
    
    @abstractmethod
    async def verify_email(self, email: str) -> bool:
        """Verify if an email is valid and deliverable."""
        pass


class EmailProvider(ABC):
    """Base interface for email providers (SendGrid, SES, etc.)"""
    
    @abstractmethod
    async def send(
        self, 
        to: str, 
        subject: str, 
        body: str,
        from_email: Optional[str] = None
    ) -> bool:
        """Send an email."""
        pass
    
    @abstractmethod
    async def send_template(
        self,
        to: str,
        template_id: str,
        variables: Dict[str, Any]
    ) -> bool:
        """Send an email using a template."""
        pass


class LinkedInProvider(ABC):
    """Base interface for LinkedIn integration."""
    
    @abstractmethod
    async def send_message(
        self, 
        profile_url: str, 
        message: str
    ) -> bool:
        """Send a LinkedIn message."""
        pass
    
    @abstractmethod
    async def get_profile(self, profile_url: str) -> Dict[str, Any]:
        """Get LinkedIn profile data."""
        pass


class WebhookDispatcher(ABC):
    """Base interface for webhook dispatching."""
    
    @abstractmethod
    async def dispatch(
        self,
        url: str,
        event: str,
        payload: Dict[str, Any],
        secret: str
    ) -> bool:
        """Dispatch a webhook."""
        pass
