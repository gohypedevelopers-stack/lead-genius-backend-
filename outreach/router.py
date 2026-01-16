from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.database import get_session
from backend.outreach.models import OutreachMessage
from backend.users.models import User
from backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/outreach", tags=["outreach"])

@router.post("/", response_model=OutreachMessage)
async def create_outreach_message(
    message_data: OutreachMessage,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    # In real app verify lead belongs to user's org
    # For now just save it
    message_data.status = "pending" # mocked
    
    session.add(message_data)
    await session.commit()
    await session.refresh(message_data)
    
    return message_data
