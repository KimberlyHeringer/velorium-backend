"""
Modelo de Conquistas do Usuário (sincronizado)
Arquivo: backend/app/models/achievement.py
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class Achievement(BaseModel):
    """Modelo de uma conquista desbloqueada pelo usuário"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    type: str            # month_closed, goal_completed, etc.
    month: Optional[str] = None   # para conquistas de mês fechado (MM/YYYY)
    name: Optional[str] = None    # nome da conquista
    description: str               # texto descritivo
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    automatica: bool = True       # conquista automática ou manual?


class AchievementCreate(BaseModel):
    type: str
    month: Optional[str] = None
    name: Optional[str] = None
    description: str
    automatica: bool = True


class AchievementResponse(Achievement):
    id: str