"""
Rotas de Notificações
Arquivo: backend/app/routes/notifications.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notificações"])


class TestNotificationResponse(BaseModel):
    success: bool
    message: str


@router.post("/test-daily", response_model=TestNotificationResponse)
async def test_daily_notification(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Endpoint para TESTE MANUAL (em desenvolvimento)"""
    return TestNotificationResponse(
        success=False,
        message="Funcionalidade em desenvolvimento. Tente novamente em breve."
    )


@router.get("/status", response_model=dict)
async def get_notification_status(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Retorna o status das notificações do usuário"""
    user = await db.users.find_one({"_id": current_user.id})
    has_token = user.get("expo_push_token") is not None if user else False
    
    return {
        "push_enabled": has_token,
        "has_token": has_token,
        "platform": "android"
    }