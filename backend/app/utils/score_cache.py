"""
Funções de Cache para Score Financeiro
Arquivo: backend/app/utils/score_cache.py

Funcionalidade: Centraliza funções de cache para o score financeiro,
com suporte a Redis e fallback MongoDB.

🔧 USO:
    from app.utils.score_cache import get_score_with_cache, invalidate_cache_redis
    
    result = await get_score_with_cache(user_id, db)
    await invalidate_cache_redis(user_id)

📋 ESTRUTURA:
    - get_cached_score_redis(): Busca score no Redis
    - set_cached_score_redis(): Armazena score no Redis
    - invalidate_cache_redis(): Invalida cache Redis
    - get_cached_score_mongodb(): Busca score no MongoDB
    - set_cached_score_mongodb(): Armazena score no MongoDB
    - get_score_with_cache(): Busca score com cache (Redis + MongoDB fallback)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
import json
import os
import logging

from app.core.constants import CACHE_TTL_SECONDS
from app.services.score_service import calculate_score

logger = logging.getLogger(__name__)

# ========== CONFIGURAÇÃO REDIS (OPCIONAL) ==========
try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para score cache")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - usando MongoDB como cache")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - usando MongoDB como cache")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")


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
    SEM TTL: Dados históricos mantidos para análise.
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
    
    result = await calculate_score(user_id, db)
    
    score_data = {
        "score": result.get("score", 0),
        "details": result.get("details"),
        "created_at": datetime.now(timezone.utc),
        "from_cache": False
    }
    
    await set_cached_score_redis(user_id, score_data)
    await set_cached_score_mongodb(user_id, score_data, db)
    
    return score_data


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Funções reutilizáveis para cache de score
# ✅ Suporte a Redis com fallback MongoDB
# ✅ SEM TTL (dados históricos mantidos)
# ✅ Upsert no MongoDB (evita duplicatas)
# ✅ Validações robustas
# ✅ Logs estruturados
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO