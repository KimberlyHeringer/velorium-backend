# app/routes/score.py
from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.services.score_service import calculate_score

router = APIRouter(prefix="/score", tags=["Score Financeiro"])

@router.get("/current")
async def get_current_score(current_user: UserResponse = Depends(get_current_user)):
    """Retorna o score atual do usuário (calculado com base em transações, perfil e metas)"""
    db = get_database()
    result = await calculate_score(current_user.id, db)
    return result

@router.get("/history")
async def get_score_history(
    limit: int = 30,
    current_user: UserResponse = Depends(get_current_user)
):
    """Retorna o histórico de score dos últimos N dias (padrão 30)"""
    db = get_database()
    history = await db.score_history.find(
        {"user_id": current_user.id}
    ).sort("date", -1).limit(limit).to_list(limit)
    # Converter ObjectId para string e formatar datas
    for h in history:
        h["_id"] = str(h["_id"])
        h["date"] = h["date"].isoformat()
    return {"history": history}