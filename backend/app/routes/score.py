"""
Rotas de Score Financeiro
Arquivo: backend/app/routes/score.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, Dict
import logging

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.services.score_service import calculate_score
from app.utils.pagination import PaginationParams, paginate_query, paginate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/score", tags=["Score Financeiro"])


# ========== SCHEMAS ==========

class ScoreResponse(BaseModel):
    score: int
    details: Optional[Dict] = None
    date: datetime


# ========== ENDPOINTS ==========

@router.get("/current", response_model=ScoreResponse)
async def get_current_score(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Retorna o score atual do usuário"""
    try:
        result = await calculate_score(current_user.id, db)
        
        return ScoreResponse(
            score=result.get("score", 0),
            details=result.get("details"),
            date=datetime.now(timezone.utc)
        )
    except Exception as e:
        logger.error(f"Erro ao calcular score para usuário {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao calcular score financeiro. Tente novamente mais tarde."
        )


@router.get("/history", response_model=dict)
async def get_score_history(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(30, ge=1, le=100, description="Itens por página (máx 100)"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Retorna o histórico de scores do usuário com paginação"""
    try:
        params = PaginationParams(page=page, limit=limit)
        query = {"user_id": str(current_user.id)}

        items, total = await paginate_query(
            db.score_history, query, params, sort=[("date", -1)]
        )
        
        # Formatar resposta
        formatted_items = []
        for item in items:
            formatted_items.append({
                "id": str(item["_id"]),
                "score": item.get("score", 0),
                "date": item.get("date"),
                "details": item.get("details")
            })
        
        return paginate(formatted_items, total, params)
        
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de score para usuário {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar histórico de score."
        )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Usa Depends(get_database) (consistência)
# ✅ Valida limit (máximo 100)
# ✅ Adicionado response_model para /current
# ✅ Removida conversão manual de date para string no histórico
# ✅ Adicionado try/except com logging
#
# 📌 Dívida técnica (pós-MVP):
#    - Cache do score (evitar recalcular toda requisição)
#    - Worker diário para recalcular score em lote
#    - Paginação com skip/offset no histórico