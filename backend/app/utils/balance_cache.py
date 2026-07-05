"""
Funções de Cache para Saldo Financeiro
Arquivo: backend/app/utils/balance_cache.py

Funcionalidades:
- Cache de saldo financeiro com Redis (fallback para MongoDB)
- Cálculo de saldo do mês atual
- Invalidação de cache por usuário
- Suporte a contextos (individual, familia, profissional)

Principais features:
- 🔧 CORRIGIDO: Suporte a Redis com fallback MongoDB
- 🔧 CORRIGIDO: TTL configurável via constants
- 🔧 CORRIGIDO: Scan_iter em vez de keys() (performance)
- 🔧 CORRIGIDO: setup_logger em vez de logging
- 🔧 CORRIGIDO: Verificação db is None
- 🔧 CORRIGIDO: Verificação user_id vazio
- 🔧 CORRIGIDO: Cache MongoDB como fallback quando Redis indisponível
- 🔧 CORRIGIDO: i18n nas mensagens de log
- 🔧 CORRIGIDO: Documentação completa

🔧 USO:
    from app.utils.balance_cache import (
        get_cached_balance,
        set_cached_balance,
        invalidate_balance_cache,
        calculate_balance
    )
    
    # Busca saldo com cache (Redis ou MongoDB)
    balance = await get_cached_balance(user_id, db, context="individual")
    
    # Invalida cache
    await invalidate_balance_cache(user_id, db)
    
    # Calcula saldo diretamente
    result = await calculate_balance(user_id, db, context="individual")
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
import os
import json

from app.core.constants import PAYMENT_METHOD_CREDIT_CARD, BALANCE_CACHE_TTL_SECONDS
from app.utils.date_utils import get_month_range
from app.utils.logger import setup_logger
from app.utils.i18n import get_message

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# ========== CONFIGURAÇÃO REDIS (OPCIONAL) ==========
try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para cache de saldo")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - usando MongoDB para cache de saldo")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - usando MongoDB para cache de saldo")
except Exception as e:
    redis_client = None
    logger.error(f"❌ {get_message('REDIS_CONNECTION_ERROR', 'pt')}: {e}")


# ========== CACHE NO MONGODB (FALLBACK) ==========

async def get_cached_balance_db(user_id: str, db, context: str = None) -> Optional[dict]:
    """
    🔧 CORRIGIDO: Busca saldo do cache MongoDB.
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
        context: Contexto (individual, familia, profissional)
    
    Returns:
        dict: Dados do saldo ou None se não encontrado
    """
    if db is None:
        logger.warning(f"⚠️ {get_message('DB_NONE', 'pt')}")
        return None
    
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return None
    
    try:
        doc = await db.balance_cache.find_one({
            "user_id": user_id,
            "context": context or "all",
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        if doc:
            logger.debug(f"✅ {get_message('BALANCE_CACHE_HIT', 'pt')} - {user_id}")
            return doc.get("balance_data")
        return None
    except Exception as e:
        logger.warning(f"⚠️ {get_message('BALANCE_CACHE_ERROR', 'pt')}: {e}")
        return None


async def set_cached_balance_db(user_id: str, balance_data: dict, db, context: str = None) -> None:
    """
    🔧 CORRIGIDO: Armazena saldo no cache MongoDB.
    
    Args:
        user_id: ID do usuário
        balance_data: Dados do saldo
        db: Conexão com o banco de dados
        context: Contexto (individual, familia, profissional)
    """
    if db is None:
        logger.warning(f"⚠️ {get_message('DB_NONE', 'pt')}")
        return
    
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return
    
    try:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=BALANCE_CACHE_TTL_SECONDS)
        
        await db.balance_cache.update_one(
            {"user_id": user_id, "context": context or "all"},
            {"$set": {
                "balance_data": balance_data,
                "expires_at": expires_at,
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        logger.debug(f"💾 {get_message('BALANCE_CACHE_SAVED', 'pt')} - {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ {get_message('BALANCE_CACHE_ERROR', 'pt')}: {e}")


# ========== CACHE NO REDIS ==========

async def get_cached_balance_redis(user_id: str, context: str = None) -> Optional[dict]:
    """
    Busca saldo do cache Redis.
    
    Args:
        user_id: ID do usuário
        context: Contexto (individual, familia, profissional)
    
    Returns:
        dict: Dados do saldo ou None se não encontrado
    """
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return None
    
    if not redis_client:
        return None
    
    try:
        key = f"balance:{user_id}:{context or 'all'}"
        data = await redis_client.get(key)
        if data:
            logger.debug(f"✅ {get_message('BALANCE_CACHE_HIT', 'pt')} - {user_id}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"⚠️ {get_message('BALANCE_CACHE_ERROR', 'pt')}: {e}")
        return None


async def set_cached_balance_redis(user_id: str, balance_data: dict, context: str = None) -> None:
    """
    Armazena saldo no cache Redis.
    
    Args:
        user_id: ID do usuário
        balance_data: Dados do saldo
        context: Contexto (individual, familia, profissional)
    """
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return
    
    if not redis_client:
        return
    
    try:
        key = f"balance:{user_id}:{context or 'all'}"
        await redis_client.setex(
            key,
            BALANCE_CACHE_TTL_SECONDS,
            json.dumps(balance_data, default=str)
        )
        logger.debug(f"💾 {get_message('BALANCE_CACHE_SAVED', 'pt')} - {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ {get_message('BALANCE_CACHE_ERROR', 'pt')}: {e}")


# ========== FUNÇÕES PRINCIPAIS ==========

async def get_cached_balance(user_id: str, db, context: str = None) -> Optional[dict]:
    """
    🔧 CORRIGIDO: Busca saldo do cache (Redis primeiro, fallback MongoDB).
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
        context: Contexto (individual, familia, profissional)
    
    Returns:
        dict: Dados do saldo ou None se não encontrado
    """
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return None
    
    # 1. Tenta Redis
    if redis_client:
        cached = await get_cached_balance_redis(user_id, context)
        if cached:
            return cached
    
    # 2. Fallback MongoDB
    return await get_cached_balance_db(user_id, db, context)


async def set_cached_balance(user_id: str, balance_data: dict, db, context: str = None) -> None:
    """
    🔧 CORRIGIDO: Armazena saldo no cache (Redis e MongoDB).
    
    Args:
        user_id: ID do usuário
        balance_data: Dados do saldo
        db: Conexão com o banco de dados
        context: Contexto (individual, familia, profissional)
    """
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return
    
    # 1. Salva no Redis
    if redis_client:
        await set_cached_balance_redis(user_id, balance_data, context)
    
    # 2. Salva no MongoDB (fallback)
    await set_cached_balance_db(user_id, balance_data, db, context)


async def invalidate_balance_cache(user_id: str, db) -> None:
    """
    Invalida cache de saldo para um usuário (Redis e MongoDB).
    Usa scan_iter em vez de keys() para performance.
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
    """
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return
    
    # 1. Invalida Redis
    if redis_client:
        try:
            keys = []
            async for key in redis_client.scan_iter(match=f"balance:{user_id}:*"):
                keys.append(key)
                if len(keys) >= 100:
                    await redis_client.delete(*keys)
                    keys = []
            
            if keys:
                await redis_client.delete(*keys)
            
            logger.info(f"🗑️ {get_message('BALANCE_CACHE_INVALIDATED', 'pt')} - {user_id} (Redis)")
        except Exception as e:
            logger.warning(f"⚠️ {get_message('BALANCE_CACHE_ERROR', 'pt')}: {e}")
    
    # 2. Invalida MongoDB
    if db is not None:
        try:
            await db.balance_cache.delete_many({"user_id": user_id})
            logger.info(f"🗑️ {get_message('BALANCE_CACHE_INVALIDATED', 'pt')} - {user_id} (MongoDB)")
        except Exception as e:
            logger.warning(f"⚠️ {get_message('BALANCE_CACHE_ERROR', 'pt')}: {e}")


async def calculate_balance(user_id: str, db, context: str = None) -> dict:
    """
    Calcula o saldo do usuário (usado pelo cache).
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
        context: Contexto (individual, familia, profissional)
    
    Returns:
        dict: Dados do saldo (income, expense, balance)
    """
    # 🔧 CORRIGIDO: Verifica se db é None
    if db is None:
        logger.error(f"❌ {get_message('DB_NONE', 'pt')}")
        return {"income": 0, "expense": 0, "balance": 0}
    
    if not user_id:
        logger.warning(f"⚠️ {get_message('USER_ID_EMPTY', 'pt')}")
        return {"income": 0, "expense": 0, "balance": 0}
    
    start_of_month, end_of_month = get_month_range()
    
    match = {
        "user_id": user_id,
        "date": {"$gte": start_of_month, "$lt": end_of_month},
        "$or": [
            {"type": "income"},
            {"type": "expense", "payment_method": {"$ne": PAYMENT_METHOD_CREDIT_CARD}},
            {"type": "expense", "payment_method": {"$exists": False}}
        ]
    }
    if context:
        match["context"] = context

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "total_income": {"$sum": {"$cond": [{"$eq": ["$type", "income"]}, "$amount", 0]}},
            "total_expense": {"$sum": {"$cond": [{"$eq": ["$type", "expense"]}, "$amount", 0]}}
        }}
    ]

    try:
        result = await db.transactions.aggregate(pipeline).to_list(1)
        
        if result:
            income = result[0]["total_income"]
            expense = result[0]["total_expense"]
            return {
                "income": income,
                "expense": expense,
                "balance": income - expense
            }
    except Exception as e:
        logger.error(f"❌ {get_message('BALANCE_CALCULATION_ERROR', 'pt')}: {e}")
    
    return {"income": 0, "expense": 0, "balance": 0}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Funções reutilizáveis para cache de saldo
#   - Suporte a Redis com scan_iter (performance)
#   - Cache MongoDB como fallback
#   - TTL configurável via constants
#   - Validações robustas (db None, user_id vazio)
#   - Logs estruturados com i18n
#   - Documentação completa
#   - 🔧 CORRIGIDO: setup_logger em vez de logging
#   - 🔧 CORRIGIDO: Verificação db is None
#   - 🔧 CORRIGIDO: Verificação user_id vazio
#   - 🔧 CORRIGIDO: Cache MongoDB como fallback
#   - 🔧 CORRIGIDO: i18n nos logs
#   - 🔧 CORRIGIDO: get_cached_balance() e set_cached_balance() unificados
#
# ❌ Não implementado (Pós-MVP):
#   - Compressão de dados no cache
#   - Cache por período (semana, mês, ano)
#   - Cache em lote para múltiplos usuários
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração com i18n, validações, fallback MongoDB (05/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO