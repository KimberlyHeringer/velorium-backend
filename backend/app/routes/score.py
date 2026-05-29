"""
Rotas de Score Financeiro
Arquivo: backend/app/routes/score.py

🔧 MODIFICADO: Regra 2.8 - Usa setup_logger em vez de logging diretamente
🔧 MODIFICADO: Regra 2.2 - Usa format_mongo_doc para padronizar respostas
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, Dict

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.services.score_service import calculate_score
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import format_mongo_doc
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

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
        
        logger.info(f"Score atual calculado para usuário {current_user.id}: {result.get('score', 0)}")
        return ScoreResponse(
            score=result.get("score", 0),
            details=result.get("details"),
            date=datetime.now(timezone.utc)
        )
    except Exception as e:
        logger.error(f"Erro ao calcular score para usuário {current_user.id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro no score: {traceback.format_exc()}")
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
        
        # 🔧 CORREÇÃO 2.2: usando format_mongo_doc em vez de formatação manual
        formatted_items = [format_mongo_doc(item) for item in items]
        
        logger.debug(f"Histórico de score listado para usuário {current_user.id}: {len(formatted_items)} registros")
        return paginate(formatted_items, total, params).model_dump()
        
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de score para usuário {current_user.id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro no histórico: {traceback.format_exc()}")
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