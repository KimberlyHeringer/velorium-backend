"""
Rotas de Conquistas do Usuário (sincronização)
Arquivo: backend/app/routes/achievements.py

🔧 MODIFICADO: Regra 2.2 - Removido format_doc local, usando format_mongo_doc
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.achievement import AchievementCreate, AchievementResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import format_mongo_doc

router = APIRouter(prefix="/achievements", tags=["Conquistas"])


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def get_achievements(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna todas as conquistas do usuário com paginação"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}

    items, total = await paginate_query(
        db.achievements, query, params, sort=[("date", -1)]
    )
    
    # 🔧 CORREÇÃO: usando format_mongo_doc (Regra 2.2)
    formatted_items = [format_mongo_doc(item) for item in items]
    
    return paginate(formatted_items, total, params).model_dump()


@router.post("/", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    ach_data: AchievementCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova conquista"""
    ach_dict = ach_data.model_dump()
    ach_dict["user_id"] = str(current_user.id)
    ach_dict["date"] = datetime.now(timezone.utc)
    result = await db.achievements.insert_one(ach_dict)
    created = await db.achievements.find_one({"_id": result.inserted_id})
    # 🔧 CORREÇÃO: usando format_mongo_doc (Regra 2.2)
    return format_mongo_doc(created)


@router.post("/sync", response_model=dict)
async def sync_achievements(
    achievements: List[AchievementCreate],
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Sincroniza múltiplas conquistas do frontend"""
    user_id = str(current_user.id)
    inserted = 0
    for ach in achievements:
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
    """Remove uma conquista"""
    result = await db.achievements.delete_one({
        "_id": ObjectId(achievement_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conquista não encontrada")
    return {"message": "Conquista removida com sucesso"}