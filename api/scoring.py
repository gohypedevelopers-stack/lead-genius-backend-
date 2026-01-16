"""
Scoring API routes.
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.database import get_session
from backend.services.scoring_service import ScoringService
from backend.schemas.scoring import (
    ScoringRuleCreate, ScoringRuleUpdate, ScoringRuleResponse,
    RecalculateRequest, RecalculateResponse
)
from backend.schemas.common import MessageResponse
from backend.api.deps import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.post("/rules/", response_model=ScoringRuleResponse, status_code=201)
async def create_scoring_rule(
    rule_data: ScoringRuleCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new scoring rule."""
    scoring_service = ScoringService(session)
    return await scoring_service.create_rule(current_user.current_org_id, rule_data)


@router.get("/rules/")
async def list_scoring_rules(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """List scoring rules."""
    scoring_service = ScoringService(session)
    rules = await scoring_service.list_rules(current_user.current_org_id, active_only)
    return {"items": rules, "total": len(rules)}


@router.get("/rules/{rule_id}", response_model=ScoringRuleResponse)
async def get_scoring_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a scoring rule by ID."""
    scoring_service = ScoringService(session)
    return await scoring_service.get_rule(current_user.current_org_id, rule_id)


@router.patch("/rules/{rule_id}", response_model=ScoringRuleResponse)
async def update_scoring_rule(
    rule_id: uuid.UUID,
    rule_data: ScoringRuleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a scoring rule."""
    scoring_service = ScoringService(session)
    return await scoring_service.update_rule(current_user.current_org_id, rule_id, rule_data)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_scoring_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a scoring rule."""
    scoring_service = ScoringService(session)
    await scoring_service.delete_rule(current_user.current_org_id, rule_id)


@router.post("/rules/defaults", response_model=MessageResponse)
async def create_default_rules(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create default scoring rules for the organization."""
    scoring_service = ScoringService(session)
    rules = await scoring_service.create_default_rules(current_user.current_org_id)
    return MessageResponse(message=f"Created {len(rules)} default scoring rules")


@router.post("/recalculate", response_model=RecalculateResponse)
async def recalculate_scores(
    request: RecalculateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Recalculate lead scores."""
    scoring_service = ScoringService(session)
    return await scoring_service.recalculate_all(
        current_user.current_org_id,
        request.lead_ids
    )
