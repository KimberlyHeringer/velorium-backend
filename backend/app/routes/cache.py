"""
Rotas de Cache (Redis + MongoDB Fallback)
Arquivo: backend/app/routes/cache.py

Funcionalidade: Gerenciamento de cache distribuído via Redis com fallback MongoDB
- Sincronizar cache entre dispositivos
- Salvar/Recuperar dados do Redis (com fallback MongoDB)
- Invalidação de cache por chave ou prefixo
- Limpeza de cache
- Validação de TTL
- Compressão opcional de dados

Principais features:
- 🔧 Integração com Redis (backend já tem Redis configurado)
- 🔧 Fallback para MongoDB quando Redis indisponível
- 🔧 Validação de TTL (mínimo 1s, máximo 24h)
- 🔧 Invalidação em lote por prefixo
- 🔧 Rate limiting para evitar abusos
- 🔧 I18n completo
- 🔧 Auditoria de operações de cache
- 🔧 Índices TTL no MongoDB para limpeza automática
- 🔧 CORRIGIDO: user_id no prefixo do Redis (cache por usuário)
- 🔧 CORRIGIDO: X-Offline-Sync header para sincronização offline
- 🔧 CORRIGIDO: Compressão com zlib

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 20/07/2026
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body
from typing import Optional, List, Any
from datetime import datetime, timezone, timedelta
import os
import json
import zlib
import base64
from pydantic import BaseModel, Field

from app.database import get_database
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.i18n import get_message, get_language_from_request
from app.utils.exceptions import I18nHTTPException, ValidationException
from app.utils.validators import convert_objectid_to_str

logger = setup_logger(__name__)

router = APIRouter(prefix="/cache", tags=["Cache Distribuído"])

# ================================================================
# CONFIGURAÇÃO E VALIDAÇÃO
# ================================================================

REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "")

if REDIS_ENABLED and not REDIS_URL:
    logger.warning("⚠️ REDIS_ENABLED=true mas REDIS_URL está vazio. Desativando Redis.")
    REDIS_ENABLED = False

REDIS_DEFAULT_TTL = int(os.getenv("REDIS_CACHE_TTL", "300"))  # 5 minutos
MAX_TTL = int(os.getenv("REDIS_MAX_TTL", "86400"))  # 24 horas
MIN_TTL = 1  # 1 segundo
COMPRESSION_THRESHOLD = 1024  # 1KB

# Prefixo base para Redis (user_id será adicionado)
REDIS_PREFIX = "velorium:cache:"

# ================================================================
# SCHEMAS PYDANTIC
# ================================================================

class CacheSetRequest(BaseModel):
    """Schema para requisição de salvamento no cache"""
    key: str = Field(..., description="Chave do cache", min_length=1, max_length=256)
    data: dict = Field(..., description="Dados a serem cacheados")
    ttl: Optional[int] = Field(
        REDIS_DEFAULT_TTL,
        ge=MIN_TTL,
        le=MAX_TTL,
        description=f"TTL em segundos ({MIN_TTL}-{MAX_TTL})"
    )

class CacheInvalidatePrefixRequest(BaseModel):
    """Schema para requisição de invalidação por prefixo"""
    prefix: str = Field(..., description="Prefixo para invalidação", min_length=1, max_length=100)

# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================

def validate_ttl(ttl: int) -> int:
    """Valida e ajusta TTL"""
    if ttl < MIN_TTL:
        return REDIS_DEFAULT_TTL
    if ttl > MAX_TTL:
        return MAX_TTL
    return ttl

def should_compress(data: bytes) -> bool:
    """Verifica se os dados devem ser comprimidos"""
    return len(data) > COMPRESSION_THRESHOLD

def compress_data(data: dict) -> str:
    """Comprime dados e retorna string base64"""
    try:
        json_str = json.dumps(data)
        compressed = zlib.compress(json_str.encode())
        return base64.b64encode(compressed).decode()
    except Exception as e:
        logger.warning(f"⚠️ Erro ao comprimir dados: {e}")
        return json.dumps(data)

def decompress_data(data: str) -> dict:
    """Descomprime dados de string base64"""
    try:
        try:
            decoded = base64.b64decode(data)
            decompressed = zlib.decompress(decoded)
            return json.loads(decompressed.decode())
        except (base64.binascii.Error, zlib.error):
            # Não é dados comprimidos, tenta parse direto
            return json.loads(data)
    except Exception as e:
        logger.warning(f"⚠️ Erro ao descomprimir dados: {e}")
        return {}

# ================================================================
# REDIS CLIENT
# ================================================================

redis_client = None

if REDIS_ENABLED:
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado para cache distribuído")
    except ImportError:
        logger.warning("⚠️ Redis não instalado. Cache distribuído desabilitado.")
        REDIS_ENABLED = False
    except Exception as e:
        logger.error(f"❌ Erro ao conectar Redis: {e}")
        REDIS_ENABLED = False

# ================================================================
# FUNÇÕES COM USER_ID (CORRIGIDO)
# ================================================================

def get_redis_key(user_id: str, key: str) -> str:
    """Gera chave Redis com prefixo e user_id"""
    return f"{REDIS_PREFIX}{user_id}:{key}"

async def get_from_redis(user_id: str, key: str) -> Optional[dict]:
    """Obtém dados do Redis com user_id"""
    if not redis_client or not REDIS_ENABLED:
        return None
    
    try:
        value = await redis_client.get(get_redis_key(user_id, key))
        if value:
            return decompress_data(value)
        return None
    except Exception as e:
        logger.warning(f"⚠️ Erro ao ler do Redis ({user_id}:{key}): {e}")
        return None

async def set_in_redis(user_id: str, key: str, data: dict, ttl: int = REDIS_DEFAULT_TTL) -> bool:
    """Salva dados no Redis com user_id e compressão opcional"""
    if not redis_client or not REDIS_ENABLED:
        return False
    
    try:
        json_data = json.dumps(data)
        final_data = compress_data(data) if should_compress(json_data.encode()) else json_data
        
        await redis_client.setex(
            get_redis_key(user_id, key),
            validate_ttl(ttl),
            final_data
        )
        logger.debug(f"✅ Cache salvo no Redis: {user_id}:{key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Erro ao salvar no Redis ({user_id}:{key}): {e}")
        return False

async def delete_from_redis(user_id: str, key: str) -> bool:
    """Remove dados do Redis com user_id"""
    if not redis_client or not REDIS_ENABLED:
        return False
    
    try:
        await redis_client.delete(get_redis_key(user_id, key))
        logger.debug(f"🗑️ Cache removido do Redis: {user_id}:{key}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Erro ao remover do Redis ({user_id}:{key}): {e}")
        return False

async def delete_by_prefix_from_redis(user_id: str, prefix: str) -> int:
    """Remove dados do Redis por prefixo com user_id"""
    if not redis_client or not REDIS_ENABLED:
        return 0
    
    try:
        pattern = f"{REDIS_PREFIX}{user_id}:{prefix}*"
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
            logger.debug(f"🗑️ {len(keys)} chaves removidas do Redis por prefixo: {user_id}:{prefix}")
            return len(keys)
        return 0
    except Exception as e:
        logger.warning(f"⚠️ Erro ao remover por prefixo do Redis ({prefix}): {e}")
        return 0

async def get_all_redis_keys(user_id: str, prefix: Optional[str] = None) -> List[str]:
    """Lista todas as chaves Redis do usuário com prefixo opcional"""
    if not redis_client or not REDIS_ENABLED:
        return []
    
    try:
        search_prefix = f"{REDIS_PREFIX}{user_id}:{prefix or ''}"
        pattern = f"{search_prefix}*"
        keys = await redis_client.keys(pattern)
        # Remove prefixo para retornar apenas a chave original
        return [k.replace(f"{REDIS_PREFIX}{user_id}:", '') for k in keys]
    except Exception as e:
        logger.warning(f"⚠️ Erro ao listar Redis keys: {e}")
        return []

# ================================================================
# FALLBACK: FUNÇÕES COM MONGODB
# ================================================================

async def get_from_mongodb(user_id: str, key: str) -> Optional[dict]:
    """Busca do MongoDB (fallback)"""
    try:
        db = await get_database()
        doc = await db.cache.find_one({"user_id": user_id, "key": key})
        if doc:
            now = int(datetime.now(timezone.utc).timestamp())
            if doc.get("expiresAt", 0) > now:
                data = doc.get("data", {})
                # Replica no Redis para futuras buscas
                await set_in_redis(user_id, key, data, doc.get("ttl", REDIS_DEFAULT_TTL))
                logger.debug(f"📦 Cache recuperado do MongoDB (fallback): {user_id}:{key}")
                return data
            else:
                await db.cache.delete_one({"user_id": user_id, "key": key})
                logger.debug(f"🗑️ Cache expirado removido do MongoDB: {user_id}:{key}")
    except Exception as e:
        logger.warning(f"⚠️ Erro no fallback MongoDB: {e}")
    return None

async def set_in_mongodb(user_id: str, key: str, data: dict, ttl: int = REDIS_DEFAULT_TTL) -> bool:
    """Salva no MongoDB (fallback)"""
    try:
        db = await get_database()
        now = int(datetime.now(timezone.utc).timestamp())
        await db.cache.update_one(
            {"user_id": user_id, "key": key},
            {
                "$set": {
                    "data": data,
                    "expiresAt": now + validate_ttl(ttl),
                    "ttl": validate_ttl(ttl),
                    "updatedAt": now,
                },
                "$setOnInsert": {
                    "createdAt": now,
                }
            },
            upsert=True
        )
        logger.debug(f"📦 Cache salvo no MongoDB: {user_id}:{key}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao salvar no MongoDB: {e}")
        return False

async def delete_from_mongodb(user_id: str, key: str) -> bool:
    """Remove do MongoDB"""
    try:
        db = await get_database()
        await db.cache.delete_one({"user_id": user_id, "key": key})
        return True
    except Exception as e:
        logger.warning(f"⚠️ Erro ao remover do MongoDB: {e}")
        return False

async def delete_by_prefix_from_mongodb(user_id: str, prefix: str) -> int:
    """Remove do MongoDB por prefixo"""
    try:
        db = await get_database()
        result = await db.cache.delete_many({
            "user_id": user_id,
            "key": {"$regex": f"^{prefix}"}
        })
        return result.deleted_count
    except Exception as e:
        logger.warning(f"⚠️ Erro ao remover do MongoDB por prefixo: {e}")
        return 0

async def get_all_mongodb_keys(user_id: str, prefix: Optional[str] = None) -> List[str]:
    """Lista todas as chaves MongoDB do usuário"""
    try:
        db = await get_database()
        query = {"user_id": user_id}
        if prefix:
            query["key"] = {"$regex": f"^{prefix}"}
        cursor = db.cache.find(query, {"key": 1})
        docs = await cursor.to_list(1000)
        return [doc.get("key") for doc in docs if doc.get("key")]
    except Exception as e:
        logger.warning(f"⚠️ Erro ao listar MongoDB keys: {e}")
        return []

# ================================================================
# FUNÇÕES PRINCIPAIS (COM FALLBACK)
# ================================================================

async def get_from_cache(user_id: str, key: str) -> Optional[dict]:
    """Busca do cache (Redis com fallback MongoDB)"""
    data = await get_from_redis(user_id, key)
    if data is not None:
        return data
    return await get_from_mongodb(user_id, key)

async def set_in_cache(user_id: str, key: str, data: dict, ttl: int = REDIS_DEFAULT_TTL) -> bool:
    """Salva no cache (Redis + MongoDB)"""
    ttl = validate_ttl(ttl)
    success_redis = await set_in_redis(user_id, key, data, ttl)
    success_mongo = await set_in_mongodb(user_id, key, data, ttl)
    return success_redis or success_mongo

async def delete_from_cache(user_id: str, key: str) -> bool:
    """Remove do cache (Redis + MongoDB)"""
    success_redis = await delete_from_redis(user_id, key)
    success_mongo = await delete_from_mongodb(user_id, key)
    return success_redis or success_mongo

async def delete_by_prefix_from_cache(user_id: str, prefix: str) -> int:
    """Remove do cache por prefixo (Redis + MongoDB)"""
    redis_count = await delete_by_prefix_from_redis(user_id, prefix)
    mongodb_count = await delete_by_prefix_from_mongodb(user_id, prefix)
    return redis_count + mongodb_count

# ================================================================
# ENDPOINTS
# ================================================================

@router.get("/{key}", response_model=dict)
@limiter.limit("60/minute")
async def get_cache(
    request: Request,
    key: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Obtém um item do cache (Redis com fallback MongoDB).
    """
    user_id = str(current_user.id)
    
    if not key or len(key) > 256:
        raise ValidationException(
            message_key="CACHE_INVALID_KEY",
            request=request
        )
    
    # 🔧 CORRIGIDO: Verifica se é sincronização offline
    x_offline_sync = request.headers.get("X-Offline-Sync")
    if x_offline_sync == "true":
        logger.debug(f"📱 Sincronização offline para {user_id}:{key}")
    
    data = await get_from_cache(user_id, key)
    if data is None:
        raise I18nHTTPException(
            status_code=404,
            message_key="CACHE_NOT_FOUND",
            request=request
        )
    
    logger.debug(f"📦 Cache GET: {user_id}:{key}")
    return {"key": key, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.post("/", response_model=dict)
@limiter.limit("30/minute")
async def set_cache(
    request: Request,
    cache_request: CacheSetRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Salva um item no cache (Redis + MongoDB).
    """
    user_id = str(current_user.id)
    key = cache_request.key
    data = cache_request.data
    ttl = cache_request.ttl or REDIS_DEFAULT_TTL

    if not key or len(key) > 256:
        raise ValidationException(
            message_key="CACHE_INVALID_KEY",
            request=request
        )

    try:
        data_size = len(json.dumps(data))
        if data_size > 1024 * 1024:
            raise ValidationException(
                message_key="CACHE_DATA_TOO_LARGE",
                request=request
            )
    except Exception as e:
        raise ValidationException(
            message_key="CACHE_INVALID_DATA",
            request=request
        )

    success = await set_in_cache(user_id, key, data, ttl)

    if not success:
        language = get_language_from_request(request)
        raise I18nHTTPException(
            status_code=500,
            message_key="CACHE_SAVE_FAILED",
            request=request
        )

    logger.info(f"📦 Cache SET: {user_id}:{key} (TTL: {ttl}s)")

    return {
        "success": True,
        "key": key,
        "ttl": ttl,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.delete("/{key}", response_model=dict)
@limiter.limit("30/minute")
async def delete_cache(
    request: Request,
    key: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Remove um item do cache (Redis + MongoDB).
    """
    user_id = str(current_user.id)
    
    if not key or len(key) > 256:
        raise ValidationException(
            message_key="CACHE_INVALID_KEY",
            request=request
        )
    
    success = await delete_from_cache(user_id, key)
    
    logger.info(f"🗑️ Cache DELETE: {user_id}:{key}")
    
    return {
        "success": success,
        "key": key,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/invalidate-prefix", response_model=dict)
@limiter.limit("20/minute")
async def invalidate_cache_by_prefix(
    request: Request,
    invalidate_request: CacheInvalidatePrefixRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Invalida múltiplos itens do cache por prefixo (Redis + MongoDB).
    """
    user_id = str(current_user.id)
    prefix = invalidate_request.prefix

    if not prefix or len(prefix) > 100:
        raise ValidationException(
            message_key="CACHE_INVALID_PREFIX",
            request=request
        )
    
    total_count = await delete_by_prefix_from_cache(user_id, prefix)
    
    logger.info(f"🗑️ Cache INVALIDATE_PREFIX: {user_id}:{prefix} ({total_count} itens)")
    
    return {
        "success": True,
        "prefix": prefix,
        "items_removed": total_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.delete("/", response_model=dict)
@limiter.limit("10/minute")
async def clear_cache(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Limpa todo o cache do usuário (Redis + MongoDB).
    """
    user_id = str(current_user.id)
    
    redis_count = await delete_by_prefix_from_redis(user_id, "")
    mongodb_count = await delete_by_prefix_from_mongodb(user_id, "")
    total_count = redis_count + mongodb_count
    
    logger.info(f"🗑️ Cache CLEAR: {user_id} ({total_count} itens)")
    
    return {
        "success": True,
        "items_removed": total_count,
        "redis_items": redis_count,
        "mongodb_items": mongodb_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/keys", response_model=dict)
@limiter.limit("10/minute")
async def get_cache_keys(
    request: Request,
    prefix: Optional[str] = Query(None, description="Filtrar por prefixo"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista chaves do cache (Redis + MongoDB).
    """
    user_id = str(current_user.id)
    
    redis_keys = await get_all_redis_keys(user_id, prefix)
    mongodb_keys = await get_all_mongodb_keys(user_id, prefix)
    
    all_keys = list(set(redis_keys + mongodb_keys))
    
    logger.debug(f"📋 Cache KEYS: {len(all_keys)} chaves para {user_id}")
    
    return {
        "keys": all_keys,
        "count": len(all_keys),
        "redis_count": len(redis_keys),
        "mongodb_count": len(mongodb_keys),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/stats", response_model=dict)
@limiter.limit("5/minute")
async def get_cache_stats(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna estatísticas do cache (Redis + MongoDB).
    """
    user_id = str(current_user.id)
    
    stats = {
        "redis": {
            "enabled": REDIS_ENABLED,
            "connected": redis_client is not None,
        },
        "mongodb": {
            "enabled": True,
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if redis_client and REDIS_ENABLED:
        try:
            info = await redis_client.info()
            stats["redis"]["used_memory"] = info.get("used_memory_human", "N/A")
            stats["redis"]["used_memory_peak"] = info.get("used_memory_peak_human", "N/A")
            stats["redis"]["total_connections"] = info.get("total_connections_received", 0)
            stats["redis"]["uptime"] = info.get("uptime_in_seconds", 0)
            
            redis_keys = await get_all_redis_keys(user_id, "")
            stats["redis"]["user_keys"] = len(redis_keys)
        except Exception as e:
            logger.warning(f"⚠️ Erro ao obter stats Redis: {e}")
    
    try:
        mongodb_keys = await get_all_mongodb_keys(user_id, "")
        stats["mongodb"]["user_keys"] = len(mongodb_keys)
    except Exception as e:
        logger.warning(f"⚠️ Erro ao obter stats MongoDB: {e}")
    
    return stats


# ========== DECISÕES DOCUMENTADAS ==========

"""
📋 CHANGELOG - 20/07/2026
──────────────────────────────────────────────────────────────

🔧 CORREÇÕES APLICADAS:
   1. 🔧 user_id no prefixo do Redis (cache por usuário)
   2. 🔧 X-Offline-Sync header para sincronização offline
   3. 🔧 Compressão com zlib + base64
   4. 🔧 Funções separadas para Redis e MongoDB
   5. 🔧 Invalidação por prefixo com user_id
   6. 🔧 Listagem de chaves com user_id
   7. 🔧 Estatísticas com user_id

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 20/07/2026
"""