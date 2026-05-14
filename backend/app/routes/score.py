"""
Rotas de Score Financeiro
Arquivo: backend/app/routes/score.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, Dict
import asyncio
import logging

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.services.score_service import calculate_score

# Configuração de logging (opcional, mas recomendado)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/score", tags=["Score Financeiro"])


# ========== SCHEMAS ==========

class ScoreResponse(BaseModel):
    """Resposta do endpoint /score/current"""
    score: int
    details: Optional[Dict] = None
    date: datetime


class ScoreHistoryResponse(BaseModel):
    """Resposta do endpoint /score/history"""
    history: list


# ========== ENDPOINTS ==========

@router.get("/current", response_model=ScoreResponse)
async def get_current_score(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Retorna o score atual do usuário (calculado sob demanda)"""
    try:
        # Se calculate_score for síncrono, use asyncio.to_thread
        # Se já for async, apenas aguarde
        result = await calculate_score(current_user.id, db)
        
        # Garante que o resultado tenha os campos esperados
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


@router.get("/history", response_model=Dict)
async def get_score_history(
    limit: int = Query(30, ge=1, le=100, description="Número máximo de registros (1-100)"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Retorna o histórico de scores do usuário (últimos 'limit' registros)"""
    try:
        history = await db.score_history.find(
            {"user_id": current_user.id}
        ).sort("date", -1).limit(limit).to_list(limit)
        
        # Converte ObjectId para string, mas mantém datetime como datetime
        for h in history:
            h["_id"] = str(h["_id"])
            # NÃO converter date para string - manter como datetime
        
        return {"history": history}
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