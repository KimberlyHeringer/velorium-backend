"""
Rotas de Score Financeiro
Arquivo: backend/app/routes/score.py

🔧 MODIFICADO: Regra 2.8 - Usa setup_logger em vez de logging diretamente
🔧 MODIFICADO: Regra 2.2 - Usa format_mongo_doc para padronizar respostas
🔧 MODIFICADO: Regra 3.1 - Score Financeiro com Cache
- Endpoint /current agora busca score do dia no histórico (cache)
- Se não existir score hoje, recalcula (primeiro acesso do dia)
- Worker diário às 03:00 mantém o cache atualizado
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
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
    from_cache: bool = False  # 🔧 NOVO: indica se veio do cache


# ========== ENDPOINTS ==========

@router.get("/current", response_model=ScoreResponse)
async def get_current_score(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Retorna o score atual do usuário (COM CACHE)
    
    🔧 REGRA 3.1: Score Financeiro com Cache
    - Busca o score do dia no score_history
    - Se não existir (primeiro acesso do dia), recalcula
    - O worker diário (03:00) mantém o cache atualizado
    """
    try:
        user_id = str(current_user.id)
        
        # 🔧 CALCULA INÍCIO E FIM DO DIA ATUAL (UTC)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # 🔧 BUSCA SCORE DO DIA NO HISTÓRICO (CACHE)
        cached_score = await db.score_history.find_one({
            "user_id": user_id,
            "date": {"$gte": today_start, "$lt": today_end}
        })
        
        if cached_score:
            # ✅ Cache hit: retorna o score já calculado
            logger.debug(f"✅ Cache hit para usuário {user_id}: score {cached_score.get('score', 0)}")
            return ScoreResponse(
                score=cached_score.get("score", 0),
                details=cached_score.get("details"),
                date=cached_score.get("date", now),
                from_cache=True
            )
        
        # 🔧 Cache miss: recalcula o score (primeiro acesso do dia)
        logger.info(f"🔄 Cache miss para usuário {user_id} - recalculando score...")
        result = await calculate_score(user_id, db)
        
        logger.info(f"✅ Score calculado para usuário {user_id}: {result.get('score', 0)}")
        return ScoreResponse(
            score=result.get("score", 0),
            details=result.get("details"),
            date=datetime.now(timezone.utc),
            from_cache=False
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter score para usuário {current_user.id}: {e}")
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
# 🔧 REGRA 3.1 (NOVO):
# ✅ Endpoint /current com cache (busca no score_history do dia)
# ✅ Cache hit → retorna imediatamente (sem recalcular)
# ✅ Cache miss → recalcula (primeiro acesso do dia)
# ✅ Campo from_cache indica se veio do cache (para debug)
# ✅ Worker diário (03:00) mantém cache atualizado
#
# 📌 Dívida técnica (pós-MVP):
#    - Cache com Redis para melhor performance
#    - Invalidação de cache por webhook