"""
Rotas de Conquistas do Usuário (sincronização)
Arquivo: backend/app/routes/achievements.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.achievement import AchievementCreate, AchievementResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/achievements", tags=["Conquistas"])


def format_achievement_doc(ach: dict) -> dict:
    if ach and "_id" in ach:
        ach["id"] = str(ach.pop("_id"))
    return ach


@router.get("/", response_model=List[AchievementResponse])
async def get_achievements(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna todas as conquistas do usuário"""
    cursor = db.achievements.find({"user_id": str(current_user.id)}).sort("date", -1)
    achievements = await cursor.to_list(length=100)
    return [format_achievement_doc(a) for a in achievements]


@router.post("/", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    ach_data: AchievementCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova conquista (usado para sincronizar do frontend)"""
    ach_dict = ach_data.model_dump()
    ach_dict["user_id"] = str(current_user.id)
    ach_dict["date"] = datetime.now(timezone.utc)
    result = await db.achievements.insert_one(ach_dict)
    created = await db.achievements.find_one({"_id": result.inserted_id})
    return format_achievement_doc(created)


@router.post("/sync", response_model=dict)
async def sync_achievements(
    achievements: List[AchievementCreate],
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Sincroniza múltiplas conquistas do frontend (evita duplicatas).
    Útil ao fazer login para subir conquistas locais que não estão no backend.
    """
    user_id = str(current_user.id)
    inserted = 0
    for ach in achievements:
        # Verifica se já existe conquista idêntica (type + month + name)
        query = {"user_id": user_id, "type": ach.type}
        if ach.month:
            query["month"] = ach.month
        if ach.name:
            query["name"] = ach.name
        existing = await db.achievements.find_one(query)
        if not existing:
            ach_dict = ach.model_dump()
            ach_dict["user_id"] = user_id
            ach_dict["date"] = datetime.now(timezone.utc)
            await db.achievements.insert_one(ach_dict)
            inserted += 1
    return {"synced": inserted, "message": f"{inserted} novas conquistas sincronizadas"}


@router.delete("/{achievement_id}", response_model=dict)
async def delete_achievement(
    achievement_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma conquista (caso o usuário queira limpar)"""
    result = await db.achievements.delete_one({
        "_id": ObjectId(achievement_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conquista não encontrada")
    return {"message": "Conquista removida com sucesso"}