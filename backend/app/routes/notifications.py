"""
Rotas de Notificações
Arquivo: backend/app/routes/notifications.py

🔧 REGRA 4.1: Endpoint para teste manual de notificações proativas
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.utils.logger import setup_logger
from workers.daily_notifications import send_daily_notification

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
    """
    Endpoint para TESTE MANUAL das notificações proativas.
    Envia uma notificação imediatamente para o usuário atual.
    """
    try:
        await send_daily_notification(str(current_user.id), db)
        logger.info(f"Notificação de teste enviada para usuário {current_user.id}")
        return TestNotificationResponse(
            success=True,
            message="Notificação de teste enviada! Verifique seu dispositivo."
        )
    except Exception as e:
        logger.error(f"Erro ao enviar notificação de teste: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao enviar notificação: {str(e)}"
        )


@router.get("/status", response_model=dict)
async def get_notification_status(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Retorna o status das notificações do usuário
    """
    user = await db.users.find_one({"_id": current_user.id})
    has_token = user.get("expo_push_token") is not None if user else False
    
    return {
        "push_enabled": has_token,
        "has_token": has_token,
        "platform": "android"  # ou detectar
    }