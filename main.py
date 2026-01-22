"""
Lead Genius Backend - FastAPI Application
Main entry point with all routes configured.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.database import init_db

# Import all API routers
from backend.api import auth, users, leads, campaigns, outreach, personas, scoring, dashboard, organizations, extension, linkedin, apify, analysis, enrichment

# Import models to ensure they are registered with SQLModel
from backend.models import (
    User, Organization, OrganizationMember,
    RefreshToken, PasswordResetToken, EmailVerificationToken,
    Lead, Campaign,
    OutreachMessage, MessageTemplate,
    Persona, ScoringRule,
    ActivityLog, Webhook, WebhookDelivery,
    LinkedInCredential, LinkedInPreference
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="Lead Genius API",
    description="AI-powered lead generation and intelligence platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(organizations.router)  # Multi-org support
app.include_router(leads.router)
app.include_router(campaigns.router)
app.include_router(outreach.router)
app.include_router(personas.router)
app.include_router(scoring.router)
app.include_router(dashboard.router)
app.include_router(extension.router)  # Chrome extension API
app.include_router(linkedin.router)   # LinkedIn API integration
app.include_router(apify.router)      # Apify integration
app.include_router(analysis.router)   # Post Analysis
app.include_router(enrichment.router) # Apollo enrichment


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Lead Genius API is running",
        "version": "2.3.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "2.3.0"
    }

