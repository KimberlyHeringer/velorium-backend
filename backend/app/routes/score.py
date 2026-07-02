"""
Rotas de Score Financeiro
Arquivo: backend/app/routes/score.py

🔧 CORRIGIDO (v5 - FINAL):
- MODIFICADO: Regra 2.8 - Usa setup_logger em vez de logging diretamente
- MODIFICADO: Regra 2.2 - Usa format_mongo_doc para padronizar respostas
- MODIFICADO: Regra 3.1 - Score Financeiro com Cache
- Endpoint /current agora busca score do dia no histórico (cache)
- Se não existir score hoje, recalcula (primeiro acesso do dia)
- Worker diário às 03:00 mantém o cache atualizado

🆕 MELHORIAS ADICIONADAS (v3):
- 🔧 Substituído format_mongo_doc por convert_objectid_to_str (padronização)
- 🆕 I18n completo com I18nHTTPException e get_message()
- 🆕 Adicionado request: Request em todos os endpoints
- 🆕 Adicionado rate limiting (current: 10/min, history: 20/min)
- 🆕 Adicionada ordenação personalizada no histórico (sort_by, sort_order)
- 🆕 Cache com Redis (opcional, fallback para MongoDB)
- 🆕 Webhook para invalidar cache (/invalidate-cache)
- 🆕 Worker diário às 03:00 (run_daily_score_worker)

🔧 CORREÇÕES DO DESENVOLVEDOR (v4):
- 🔧 CORRIGIDO: Usa created_at em vez de date no cache (campo correto)
- 🔧 CORRIGIDO: Upsert no MongoDB para evitar duplicatas
- 🔧 CORRIGIDO: Busca de usuários ativos via transações

🆕 MELHORIAS ADICIONADAS (v5):
- 🆕 Métricas de performance (tempo de cálculo)
- 🆕 Retry no worker (3 tentativas com backoff exponencial)
- ❌ SEM TTL no MongoDB (dados históricos são valiosos)

📋 DECISÕES DOCUMENTADAS:
- ✅ Redis opcional: se não configurado, usa MongoDB como fallback
- ✅ Webhook para invalidar cache quando dados mudam
- ✅ Worker diário às 03:00 mantém cache atualizado
- ✅ Rate limiting para proteger endpoints
- ✅ Ordenação personalizada no histórico
- ✅ Métricas de performance para monitoramento
- ✅ Retry no worker para resiliência
- ❌ SEM TTL: Dados históricos de score são mantidos para análise

📋 LIMITAÇÕES CONHECIDAS:
- Redis: requer configuração de REDIS_URL no ambiente
- Se Redis não estiver disponível, fallback para MongoDB
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import os
import json
import time
import asyncio

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.services.score_service import calculate_score
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter

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


# ========== CONSTANTES ==========
CACHE_TTL_SECONDS = 86400  # 24 horas
MAX_RETRIES = 3  # Número máximo de tentativas no worker
SLOW_THRESHOLD = 2.0  # Segundos para considerar cálculo lento


# ========== SCHEMAS ==========

class ScoreResponse(BaseModel):
    score: int
    details: Optional[Dict] = None
    created_at: datetime
    from_cache: bool = False


class CacheInvalidateRequest(BaseModel):
    user_id: str
    reason: Optional[str] = None


# ========== FUNÇÕES AUXILIARES ==========

def get_user_rate_limit_key(request: Request) -> str:
    """
    Gera chave de rate limiting por usuário.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"score:user:{user_id}"
    
    client_ip = request.client.host if request.client else "unknown"
    return f"score:ip:{client_ip}"


async def get_cached_score_redis(user_id: str) -> Optional[Dict]:
    """
    Busca score do cache Redis.
    """
    if not redis_client:
        return None
    
    try:
        key = f"score:{user_id}"
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"⚠️ Erro ao buscar score no Redis: {e}")
        return None


async def set_cached_score_redis(user_id: str, score_data: Dict):
    """
    Armazena score no cache Redis.
    """
    if not redis_client:
        return
    
    try:
        key = f"score:{user_id}"
        await redis_client.setex(
            key,
            CACHE_TTL_SECONDS,
            json.dumps(score_data, default=str)
        )
        logger.debug(f"💾 Score armazenado no Redis para usuário {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao armazenar score no Redis: {e}")


async def invalidate_cache_redis(user_id: str):
    """
    Invalida cache Redis para um usuário.
    """
    if not redis_client:
        return
    
    try:
        key = f"score:{user_id}"
        await redis_client.delete(key)
        logger.info(f"🗑️ Cache Redis invalidado para usuário {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao invalidar cache Redis: {e}")


async def get_cached_score_mongodb(user_id: str, db) -> Optional[Dict]:
    """
    Busca score do cache MongoDB.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    cached = await db.score_history.find_one({
        "user_id": user_id,
        "created_at": {"$gte": today_start, "$lt": today_end}
    })
    
    if cached:
        return {
            "score": cached.get("score", 0),
            "details": cached.get("details"),
            "created_at": cached.get("created_at", now),
            "from_cache": True
        }
    return None


async def set_cached_score_mongodb(user_id: str, score_data: Dict, db):
    """
    Armazena score no cache MongoDB.
    🔧 SEM TTL: Dados históricos são mantidos para análise.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    score_entry = {
        "user_id": user_id,
        "score": score_data.get("score", 0),
        "details": score_data.get("details"),
        "created_at": now,
        "updated_at": now
    }
    
    await db.score_history.update_one(
        {
            "user_id": user_id,
            "created_at": {"$gte": today_start, "$lt": today_end}
        },
        {"$set": score_entry},
        upsert=True
    )
    logger.debug(f"💾 Score armazenado no MongoDB para usuário {user_id}")


async def get_score_with_cache(user_id: str, db) -> Dict:
    """
    Busca score com cache (Redis primeiro, fallback MongoDB).
    """
    # 1. Tenta Redis
    cached = await get_cached_score_redis(user_id)
    if cached:
        cached["from_cache"] = True
        return cached
    
    # 2. Tenta MongoDB
    cached = await get_cached_score_mongodb(user_id, db)
    if cached:
        await set_cached_score_redis(user_id, cached)
        return cached
    
    # 3. Cache miss - recalcula
    logger.info(f"🔄 Cache miss para usuário {user_id} - recalculando score...")
    
    start_time = time.time()
    result = await calculate_score(user_id, db)
    elapsed = time.time() - start_time
    
    # 🆕 Métricas de performance
    if elapsed > SLOW_THRESHOLD:
        logger.warning(f"⚠️ Cálculo de score LENTO para {user_id}: {elapsed:.2f}s")
    elif elapsed > 1.0:
        logger.debug(f"🐢 Cálculo de score médio para {user_id}: {elapsed:.2f}s")
    else:
        logger.debug(f"⚡ Cálculo de score rápido para {user_id}: {elapsed:.2f}s")
    
    score_data = {
        "score": result.get("score", 0),
        "details": result.get("details"),
        "created_at": datetime.now(timezone.utc),
        "from_cache": False
    }
    
    await set_cached_score_redis(user_id, score_data)
    await set_cached_score_mongodb(user_id, score_data, db)
    
    return score_data


# ========== WORKER DIÁRIO (03:00) ==========

async def run_daily_score_worker(db):
    """
    Worker diário que recalcula scores para todos os usuários ativos.
    Deve ser chamado pelo scheduler às 03:00.
    
    🆕 v5: Métricas de performance e retry com backoff exponencial.
    🔧 SEM TTL: Dados históricos mantidos para análise.
    """
    logger.info("🚀 Iniciando worker diário de score (03:00)")
    
    # Busca usuários com transações nos últimos 30 dias
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    active_users = await db.transactions.distinct("user_id", {
        "created_at": {"$gte": thirty_days_ago}
    })
    
    logger.info(f"📊 {len(active_users)} usuários ativos encontrados")
    
    if not active_users:
        logger.info("ℹ️ Nenhum usuário ativo encontrado")
        return {"updated": 0, "failed": 0}
    
    updated_count = 0
    failed_count = 0
    
    for user_id in active_users:
        user_id_str = str(user_id)
        success = False
        
        # 🆕 Retry com backoff exponencial
        for attempt in range(MAX_RETRIES):
            try:
                start_time = time.time()
                result = await calculate_score(user_id_str, db)
                elapsed = time.time() - start_time
                
                # 🆕 Métricas de performance
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
                    # Última tentativa falhou
                    logger.error(f"❌ Falha após {MAX_RETRIES} tentativas para {user_id_str}: {e}")
                    failed_count += 1
                else:
                    # 🆕 Backoff exponencial: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ Tentativa {attempt + 1} falhou para {user_id_str}, tentando novamente em {wait_time}s")
                    await asyncio.sleep(wait_time)
    
    logger.info(f"✅ Worker finalizado: {updated_count} atualizados, {failed_count} falhas")
    return {"updated": updated_count, "failed": failed_count}


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
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        user_id = str(current_user.id)
        result = await get_score_with_cache(user_id, db)
        
        logger.debug(f"✅ Score para usuário {user_id}: {result.get('score', 0)} (cache: {result.get('from_cache', False)})")
        
        return ScoreResponse(
            score=result.get("score", 0),
            details=result.get("details"),
            created_at=result.get("created_at", datetime.now(timezone.utc)),
            from_cache=result.get("from_cache", False)
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter score para usuário {current_user.id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro no score: {traceback.format_exc()}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SCORE_CALCULATION_FAILED",
            request=request
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
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        params = PaginationParams(page=page, limit=limit)
        query = {"user_id": str(current_user.id)}
        
        sort_field_mapping = {
            "created_at": "created_at",
            "score": "score"
        }
        sort_field = sort_field_mapping.get(sort_by, "created_at")
        sort_direction = -1 if sort_order == "desc" else 1

        items, total = await paginate_query(
            db.score_history, query, params, sort=[(sort_field, sort_direction)]
        )
        
        formatted_items = [convert_objectid_to_str(item) for item in items]
        
        logger.debug(f"📊 Histórico de score listado para usuário {current_user.id}: {len(formatted_items)} registros")
        return paginate(formatted_items, total, params).model_dump()
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar histórico de score para usuário {current_user.id}: {e}")
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
    🆕 Webhook para invalidar cache do score.
    Útil quando dados do usuário mudam e o score precisa ser recalculado.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        user_id = str(current_user.id)
        
        # Invalida Redis
        await invalidate_cache_redis(user_id)
        
        # Remove MongoDB cache (score do dia)
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
        logger.error(f"❌ Erro ao invalidar cache para usuário {current_user.id}: {e}")
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
    🆕 Endpoint para acionar o worker diário de score manualmente.
    Deve ser chamado por um cron job externo às 03:00.
    Requer chave secreta de admin.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
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
    
    logger.info(f"🔔 Trigger manual do worker diário solicitado por {current_user.id}")
    
    background_tasks.add_task(run_daily_score_worker, db)
    
    return {
        "message": get_message("SUCCESS_WORKER_TRIGGERED", language),
        "success": True
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Usa Depends(get_database) (consistência)
# ✅ Valida limit (máximo 100)
# ✅ Adicionado response_model para /current
# ✅ Removida conversão manual de date para string no histórico
# ✅ Adicionado try/except com logging
# ✅ Endpoint /current com cache (Redis + MongoDB fallback)
# ✅ Cache hit → retorna imediatamente (sem recalcular)
# ✅ Cache miss → recalcula (primeiro acesso do dia)
# ✅ Campo from_cache indica se veio do cache (para debug)
# ✅ Worker diário (03:00) mantém cache atualizado
# ✅ Webhook /invalidate-cache para invalidar cache
# ✅ Endpoint /trigger-daily-worker para acionar worker manualmente
# ✅ Redis opcional (fallback para MongoDB)
# ✅ created_at em vez de date (campo correto)
# ✅ Upsert no MongoDB (evita duplicatas)
# ✅ Busca de usuários ativos via transações
# ✅ Métricas de performance (tempo de cálculo)
# ✅ Retry no worker (3 tentativas com backoff exponencial)
# ❌ SEM TTL: Dados históricos de score são mantidos para análise
#
# 📌 CHAVES I18N UTILIZADAS:
#   - ERROR_SCORE_CALCULATION_FAILED → "Erro ao calcular score financeiro..."
#   - ERROR_SCORE_HISTORY_FAILED → "Erro ao buscar histórico de score..."
#   - SUCCESS_CACHE_INVALIDATED → "Cache invalidado com sucesso"
#   - SUCCESS_WORKER_TRIGGERED → "Worker diário acionado"
#   - ERROR_UNAUTHORIZED → "Não autorizado"
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO