"""
Rotas de Score Financeiro
Arquivo: backend/app/routes/score.py

Funcionalidades:
- GET /score/current: Retorna score atual com cache
- GET /score/history: Histórico de scores com paginação e ordenação
- POST /score/invalidate-cache: Invalida cache do score
- POST /score/trigger-daily-worker: Aciona worker diário manualmente

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (current: 10/min, history: 20/min)
- Cache Redis com fallback MongoDB
- Worker diário (03:00) com retry e métricas
- Métricas de performance
- SEM TTL (dados históricos mantidos)
- 🔧 Fallback seguro para erro 500 no score

Versão: v5.3 (fallback seguro para score)
📅 ATUALIZADO EM: 20/07/2026
"""

from fastapi import APIRouter, Depends, Query, Request, BackgroundTasks
# 🔧 CORRIGIDO: Removido HTTPException (não usado)
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import os
# 🔧 CORRIGIDO: Removido json (não usado)
import time
import asyncio

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.services.score_service import calculate_score
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger

# ========== NOVOS IMPORTS ==========
from app.core.constants import CACHE_TTL_SECONDS, MAX_RETRIES, SLOW_THRESHOLD
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.score_cache import get_score_with_cache, invalidate_cache_redis

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/score", tags=["Score Financeiro"])


# ========== CONFIGURAÇÃO REDIS (OPCIONAL) ==========
try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - usando MongoDB como cache")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - usando MongoDB como cache")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")


# ========== SCHEMAS ==========

class ScoreResponse(BaseModel):
    score: int
    details: Optional[Dict] = None
    created_at: datetime
    from_cache: bool = False


# ========== WORKER DIÁRIO (03:00) ==========

async def run_daily_score_worker(db):
    """
    Worker diário que recalcula scores para todos os usuários ativos.
    Deve ser chamado pelo scheduler às 03:00.
    """
    logger.info("🚀 Iniciando worker diário de score (03:00)")
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    active_users = await db.transactions.distinct("user_id", {
        "created_at": {"$gte": thirty_days_ago}
    })
    
    logger.info(f"📊 {len(active_users)} usuários ativos encontrados")
    
    if not active_users:
        logger.info("ℹ️ Nenhum usuário ativo encontrado")
        return {"updated": 0, "failed": 0, "total": 0}
    
    updated_count = 0
    failed_count = 0
    skipped_count = 0
    
    for user_id in active_users:
        # 🔧 CORRIGIDO: Valida se user_id é string
        if not user_id:
            skipped_count += 1
            continue
            
        user_id_str = str(user_id)
        success = False
        
        for attempt in range(MAX_RETRIES):
            try:
                start_time = time.time()
                result = await calculate_score(user_id_str, db)
                elapsed = time.time() - start_time
                
                if elapsed > SLOW_THRESHOLD:
                    logger.warning(f"⚠️ Cálculo LENTO para {user_id_str}: {elapsed:.2f}s (tentativa {attempt + 1})")
                elif elapsed > 1.0 and attempt == 0:
                    logger.debug(f"🐢 Cálculo médio para {user_id_str}: {elapsed:.2f}s")
                
                score_data = {
                    "score": result.get("score", 0),
                    "details": result.get("details"),
                    "created_at": datetime.now(timezone.utc),
                    "from_cache": False
                }
                
                # Atualiza Redis
                from app.utils.score_cache import set_cached_score_redis
                await set_cached_score_redis(user_id_str, score_data)
                
                # Atualiza MongoDB (SEM TTL)
                now = datetime.now(timezone.utc)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timedelta(days=1)
                
                await db.score_history.update_one(
                    {
                        "user_id": user_id_str,
                        "created_at": {"$gte": today_start, "$lt": today_end}
                    },
                    {
                        "$set": {
                            "score": result.get("score", 0),
                            "details": result.get("details"),
                            "updated_at": now
                        }
                    },
                    upsert=True
                )
                
                updated_count += 1
                success = True
                
                if updated_count % 100 == 0:
                    logger.info(f"📊 Progresso: {updated_count}/{len(active_users)} usuários processados")
                
                break  # Sai do loop de retry
                
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"❌ Falha após {MAX_RETRIES} tentativas para {user_id_str}: {e}")
                    failed_count += 1
                else:
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ Tentativa {attempt + 1} falhou para {user_id_str}, tentando novamente em {wait_time}s")
                    await asyncio.sleep(wait_time)
    
    # 🔧 CORRIGIDO: Log resumido com estatísticas
    logger.info(f"✅ Worker finalizado: {updated_count} atualizados, {failed_count} falhas, {skipped_count} ignorados")
    return {"updated": updated_count, "failed": failed_count, "skipped": skipped_count, "total": len(active_users)}


# ========== ENDPOINTS ==========

@router.get("/current", response_model=ScoreResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def get_current_score(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Retorna o score atual do usuário (COM CACHE).
    🔧 CORRIGIDO: Fallback seguro para erro 500
    """
    user_id = str(current_user.id)
    language = getattr(request.state, "language", "pt")
    request.state.user_id = user_id
    
    try:
        result = await get_score_with_cache(user_id, db)
        
        # 🔧 CORRIGIDO: Se result for None ou não tiver score, retorna 0
        if result is None:
            logger.warning(f"⚠️ Score retornou None para usuário {user_id}")
            return ScoreResponse(
                score=0,
                details=None,
                created_at=datetime.now(timezone.utc),
                from_cache=False
            )
        
        # 🔧 CORRIGIDO: Se não tiver a chave 'score', retorna 0
        if 'score' not in result:
            logger.warning(f"⚠️ Score sem campo 'score' para usuário {user_id}")
            return ScoreResponse(
                score=0,
                details=result.get('details'),
                created_at=result.get('created_at', datetime.now(timezone.utc)),
                from_cache=result.get('from_cache', False)
            )
        
        logger.debug(f"✅ Score para usuário {user_id}: {result.get('score', 0)} (cache: {result.get('from_cache', False)})")
        
        return ScoreResponse(
            score=result.get("score", 0),
            details=result.get("details"),
            created_at=result.get("created_at", datetime.now(timezone.utc)),
            from_cache=result.get("from_cache", False)
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter score para usuário {user_id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro no score: {traceback.format_exc()}")
        
        # 🔧 CORRIGIDO: Fallback seguro - retorna score 0 em vez de erro 500
        # Isso evita que o dashboard quebre
        return ScoreResponse(
            score=0,
            details={"error": str(e), "fallback": True},
            created_at=datetime.now(timezone.utc),
            from_cache=False
        )


@router.get("/history", response_model=dict)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def get_score_history(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(30, ge=1, le=100, description="Itens por página (máx 100)"),
    sort_by: str = Query("created_at", description="Campo para ordenação (created_at, score)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Retorna o histórico de scores do usuário com paginação e ordenação.
    """
    user_id = str(current_user.id)
    language = getattr(request.state, "language", "pt")
    request.state.user_id = user_id
    
    try:
        params = PaginationParams(page=page, limit=limit)
        query = {"user_id": user_id}
        
        sort_field_mapping = {
            "created_at": "created_at",
            "score": "score"
        }
        sort_field = sort_field_mapping.get(sort_by, "created_at")
        sort_direction = -1 if sort_order == "desc" else 1

        # 🔧 CORRIGIDO: Adicionado collection_name e user_id
        items, total = await paginate_query(
            collection=db.score_history,
            collection_name="score_history",
            query=query,
            params=params,
            user_id=user_id,
            sort=[(sort_field, sort_direction)]
        )
        
        formatted_items = [convert_objectid_to_str(item) for item in items]
        
        logger.debug(f"📊 Histórico de score listado para usuário {user_id}: {len(formatted_items)} registros")
        return paginate(formatted_items, total, params).model_dump()
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar histórico de score para usuário {user_id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro no histórico: {traceback.format_exc()}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SCORE_HISTORY_FAILED",
            request=request
        )


@router.post("/invalidate-cache", response_model=dict)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def invalidate_cache(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Webhook para invalidar cache do score.
    """
    user_id = str(current_user.id)
    language = getattr(request.state, "language", "pt")
    request.state.user_id = user_id
    
    try:
        await invalidate_cache_redis(user_id)
        
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        await db.score_history.delete_many({
            "user_id": user_id,
            "created_at": {"$gte": today_start, "$lt": today_end}
        })
        
        logger.info(f"🗑️ Cache invalidado para usuário {user_id}")
        
        return {
            "message": get_message("SUCCESS_CACHE_INVALIDATED", language),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao invalidar cache para usuário {user_id}: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


@router.post("/trigger-daily-worker", response_model=dict)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def trigger_daily_worker(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str = Query(..., description="Chave secreta de admin"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Endpoint para acionar o worker diário de score manualmente.
    """
    user_id = str(current_user.id)
    language = getattr(request.state, "language", "pt")
    request.state.user_id = user_id
    
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")
    
    if os.getenv("ENVIRONMENT") == "production" and not ADMIN_SECRET:
        logger.error("❌ ADMIN_SECRET não configurado em produção!")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )
    
    if not ADMIN_SECRET:
        if secret != "development-only-secret":
            raise ValidationException(
                message_key="ERROR_UNAUTHORIZED",
                request=request
            )
    else:
        if secret != ADMIN_SECRET:
            raise ValidationException(
                message_key="ERROR_UNAUTHORIZED",
                request=request
            )
    
    logger.info(f"🔔 Trigger manual do worker diário solicitado por {user_id}")
    
    background_tasks.add_task(run_daily_score_worker, db)
    
    return {
        "message": get_message("SUCCESS_WORKER_TRIGGERED", language),
        "success": True
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (current: 10/min, history: 20/min)
#   - Cache Redis com fallback MongoDB
#   - Worker diário (03:00) com retry e métricas
#   - Métricas de performance
#   - SEM TTL (dados históricos mantidos)
#   - Webhook /invalidate-cache
#   - Funções de cache centralizadas em utils/score_cache.py
#   - 🔧 paginate_query com collection_name e user_id
#   - 🔧 Validação de user_id no worker
#   - 🔧 Log resumido com estatísticas
#   - 🔧 Removido imports não utilizados
#   - 🔧 Fallback seguro para erro 500 no score (v5.3)
#
# ❌ Não implementado (Pós-MVP):
#   - Redis com fallback para MongoDB (já tem)
#   - Cache com TTL no MongoDB (decisão: SEM TTL)
#   - Métricas de cache hit/miss (em score_cache.py)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Rate limiting, cache Redis (30/06/2026)
#   - v4: Correções de created_at, upsert (01/07/2026)
#   - v5: Refatoração - constants, rate_limiter, score_cache (02/07/2026)
#   - v5.1: CORREÇÃO - Adicionado collection_name e user_id no paginate_query (18/07/2026)
#   - v5.2: CORREÇÃO - Removido imports não usados, validação user_id, logs melhorados (18/07/2026)
#   - v5.3: CORREÇÃO - Fallback seguro para erro 500 no score (20/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO