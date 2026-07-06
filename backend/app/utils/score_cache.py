"""
Funções de Cache para Score Financeiro
Arquivo: backend/app/utils/score_cache.py

Funcionalidade: Centraliza funções de cache para o score financeiro,
com suporte a Redis e fallback MongoDB.

Funcionalidades:
- Cache Redis para score (TTL: 1 hora, variável por score)
- Fallback MongoDB para score
- Invalidação de cache (individual e em lote)
- Métricas de hit/miss do cache
- Busca de score com cache (Redis → MongoDB → recalculo)
- Internacionalização (i18n) nos logs
- SEM TTL no MongoDB (dados históricos mantidos)

Principais features:
- 🔧 NOVO: Internacionalização (i18n) nos logs
- 🔧 NOVO: Métricas de hit/miss do cache
- 🔧 NOVO: TTL variável por score (score alto = cache mais longo)
- 🔧 NOVO: Invalidação em lote (batch)
- 🔧 CORRIGIDO: Logger padronizado com setup_logger()
- 🔧 CORRIGIDO: Validação de user_id
- 🔧 CORRIGIDO: Campo 'date' em vez de 'created_at' no retorno do MongoDB
- 🔧 CORRIGIDO: Verificação de db None
- ✅ Redis com fallback MongoDB
- ✅ SEM TTL no MongoDB
- ✅ Upsert no MongoDB (evita duplicatas)
- ✅ Documentação completa

Regra: 2.8 (Logs)
Regra: 3.2 (Cache com Redis)
Regra: 7.1 (Internacionalização)

🔧 USO:
    from app.utils.score_cache import (
        get_score_with_cache,
        invalidate_cache_redis,
        invalidate_cache_batch,
        get_score_metrics,
        reset_score_metrics
    )
    
    # Buscar score com cache
    result = await get_score_with_cache(user_id, db)
    
    # Invalidar cache individual
    await invalidate_cache_redis(user_id)
    
    # Invalidar cache em lote
    await invalidate_cache_batch(["user1", "user2", "user3"])
    
    # Ver métricas do cache
    metrics = get_score_metrics()
    print(metrics["hit_rate"])  # 85.0%
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import json
import os

from app.utils.logger import setup_logger
from app.utils.i18n import get_message
from app.core.constants import CACHE_TTL_SECONDS
from app.services.score_service import calculate_score

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# ========== CONFIGURAÇÃO REDIS (OPCIONAL) ==========
try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info(get_message("SCORE_CACHE_REDIS_CONNECTED", "pt"))
    else:
        redis_client = None
        logger.info(get_message("SCORE_CACHE_REDIS_NOT_CONFIGURED", "pt"))
except ImportError:
    redis_client = None
    logger.info(get_message("SCORE_CACHE_REDIS_NOT_INSTALLED", "pt"))
except Exception as e:
    redis_client = None
    logger.error(get_message("SCORE_CACHE_REDIS_ERROR", "pt", error=str(e)))


# ============================================================
# MÉTRICAS DE CACHE
# ============================================================

class ScoreCacheMetrics:
    """
    🔧 NOVO: Métricas para monitorar a eficácia do cache de score.
    
    🔧 USO:
        metrics = ScoreCacheMetrics()
        metrics.record_redis_hit()
        metrics.record_mongo_hit()
        metrics.record_miss()
        print(metrics.get_hit_rate())  # 85.0%
    """
    
    def __init__(self):
        self._redis_hits = 0
        self._mongo_hits = 0
        self._misses = 0
    
    def record_redis_hit(self) -> None:
        """Registra um acerto no Redis."""
        self._redis_hits += 1
    
    def record_mongo_hit(self) -> None:
        """Registra um acerto no MongoDB (fallback)."""
        self._mongo_hits += 1
    
    def record_miss(self) -> None:
        """Registra um erro de cache (recalculo necessário)."""
        self._misses += 1
    
    def get_total_hits(self) -> int:
        """Retorna o total de acertos."""
        return self._redis_hits + self._mongo_hits
    
    def get_total(self) -> int:
        """Retorna o total de tentativas."""
        return self.get_total_hits() + self._misses
    
    def get_hit_rate(self) -> float:
        """Retorna o percentual de acertos (considerando todos os hits)."""
        total = self.get_total()
        return round((self.get_total_hits() / total * 100), 2) if total > 0 else 0.0
    
    def get_redis_hit_rate(self) -> float:
        """Retorna o percentual de acertos no Redis."""
        total = self.get_total()
        return round((self._redis_hits / total * 100), 2) if total > 0 else 0.0
    
    def get_summary(self) -> dict:
        """Retorna um resumo das métricas."""
        return {
            "redis_hits": self._redis_hits,
            "mongo_hits": self._mongo_hits,
            "misses": self._misses,
            "total_hits": self.get_total_hits(),
            "total": self.get_total(),
            "hit_rate": self.get_hit_rate(),
            "redis_hit_rate": self.get_redis_hit_rate()
        }
    
    def reset(self) -> None:
        """Reseta todas as métricas."""
        self._redis_hits = 0
        self._mongo_hits = 0
        self._misses = 0


# 🔧 NOVO: Instância global de métricas
_score_metrics = ScoreCacheMetrics()


# ============================================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================================

def _validate_user_id(user_id: str) -> None:
    """
    Valida se user_id é uma string não vazia.
    
    Raises:
        ValueError: Se user_id for vazio ou None
    """
    if not user_id or not isinstance(user_id, str):
        logger.error(get_message("SCORE_CACHE_USER_ID_INVALID", "pt", user_id=user_id))
        raise ValueError("user_id é obrigatório e deve ser uma string não vazia")


# ============================================================
# FUNÇÕES DE MÉTRICAS
# ============================================================

def get_score_metrics() -> dict:
    """
    🔧 NOVO: Retorna as métricas atuais do cache de score.
    
    🔧 USO:
        metrics = get_score_metrics()
        print(metrics["hit_rate"])  # 85.0
    """
    return _score_metrics.get_summary()


def reset_score_metrics() -> None:
    """
    🔧 NOVO: Reseta as métricas do cache de score.
    """
    _score_metrics.reset()
    logger.info("🔄 Métricas de score resetadas")


# ============================================================
# FUNÇÕES DE CACHE REDIS
# ============================================================

def _get_ttl_for_score(score: int) -> int:
    """
    🔧 NOVO: Retorna TTL baseado no score.
    
    - Score alto (>80): cache mais longo (2 horas)
    - Score médio (50-80): cache padrão (1 hora)
    - Score baixo (<50): cache mais curto (30 minutos)
    """
    if score > 80:
        return CACHE_TTL_SECONDS * 2  # 2 horas
    elif score < 50:
        return CACHE_TTL_SECONDS // 2  # 30 minutos
    else:
        return CACHE_TTL_SECONDS  # 1 hora


async def get_cached_score_redis(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca score do cache Redis.

    🔧 USO:
        cached = await get_cached_score_redis(user_id)
        if cached:
            print(cached["score"])

    📋 PADRÃO:
        - Tenta Redis primeiro
        - Se falhar, retorna None
        - Log com i18n
    """
    if not redis_client:
        return None
    
    _validate_user_id(user_id)
    
    try:
        key = f"score:{user_id}"
        data = await redis_client.get(key)
        if data:
            # 🔧 NOVO: Registra hit nas métricas
            _score_metrics.record_redis_hit()
            logger.debug(get_message("SCORE_CACHE_REDIS_HIT", "pt", user_id=user_id))
            return json.loads(data)
        
        logger.debug(get_message("SCORE_CACHE_REDIS_MISS", "pt", user_id=user_id))
        return None
        
    except Exception as e:
        logger.warning(get_message("SCORE_CACHE_REDIS_GET_ERROR", "pt", user_id=user_id, error=str(e)))
        return None


async def set_cached_score_redis(user_id: str, score_data: Dict[str, Any]) -> None:
    """
    Armazena score no cache Redis.

    🔧 USO:
        await set_cached_score_redis(user_id, score_data)

    📋 PADRÃO:
        - 🔧 NOVO: TTL variável baseado no score
        - Se Redis falhar, apenas loga (não quebra a requisição)
        - Log com i18n
    """
    if not redis_client:
        return
    
    _validate_user_id(user_id)
    
    try:
        key = f"score:{user_id}"
        # 🔧 NOVO: TTL variável baseado no score
        score = score_data.get("score", 0)
        ttl = _get_ttl_for_score(score)
        
        await redis_client.setex(
            key,
            ttl,
            json.dumps(score_data, default=str)
        )
        logger.debug(get_message("SCORE_CACHE_REDIS_SET", "pt", user_id=user_id, ttl=ttl))
    except Exception as e:
        logger.warning(get_message("SCORE_CACHE_REDIS_SET_ERROR", "pt", user_id=user_id, error=str(e)))


async def invalidate_cache_redis(user_id: str) -> None:
    """
    Invalida cache Redis para um usuário.

    🔧 USO:
        await invalidate_cache_redis(user_id)

    📋 PADRÃO:
        - Segue o mesmo padrão de outras funções de cache
        - Log com i18n
    """
    if not redis_client:
        return
    
    _validate_user_id(user_id)
    
    try:
        key = f"score:{user_id}"
        await redis_client.delete(key)
        logger.info(get_message("SCORE_CACHE_REDIS_INVALIDATED", "pt", user_id=user_id))
    except Exception as e:
        logger.warning(get_message("SCORE_CACHE_REDIS_INVALIDATE_ERROR", "pt", user_id=user_id, error=str(e)))


# ============================================================
# 🔧 NOVO: INVALIDAÇÃO EM LOTE
# ============================================================

async def invalidate_cache_batch(user_ids: List[str]) -> None:
    """
    🔧 NOVO: Invalida cache Redis para múltiplos usuários.
    
    🔧 USO:
        await invalidate_cache_batch(["user1", "user2", "user3"])
    
    📋 PADRÃO:
        - Útil para workers que processam múltiplos usuários
        - Registra quantos foram invalidados
    """
    if not redis_client or not user_ids:
        return
    
    invalidated = 0
    errors = 0
    
    for user_id in user_ids:
        try:
            _validate_user_id(user_id)
            key = f"score:{user_id}"
            await redis_client.delete(key)
            invalidated += 1
        except Exception as e:
            errors += 1
            logger.warning(get_message("SCORE_CACHE_REDIS_INVALIDATE_ERROR", "pt", user_id=user_id, error=str(e)))
    
    logger.info(get_message("SCORE_CACHE_REDIS_BATCH_INVALIDATED", "pt", count=invalidated, errors=errors))


# ============================================================
# FUNÇÕES DE CACHE MONGODB
# ============================================================

async def get_cached_score_mongodb(user_id: str, db) -> Optional[Dict[str, Any]]:
    """
    Busca score do cache MongoDB.

    🔧 USO:
        cached = await get_cached_score_mongodb(user_id, db)

    📋 PADRÃO:
        - Busca score do dia atual
        - Retorna 'date' em vez de 'created_at'
        - Log com i18n
    """
    _validate_user_id(user_id)
    
    if db is None:
        logger.error(get_message("SCORE_CACHE_DB_NONE", "pt", user_id=user_id))
        return None
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    try:
        cached = await db.score_history.find_one({
            "user_id": user_id,
            "created_at": {"$gte": today_start, "$lt": today_end}
        })
        
        if cached:
            # 🔧 NOVO: Registra hit no MongoDB (fallback)
            _score_metrics.record_mongo_hit()
            logger.debug(get_message("SCORE_CACHE_MONGODB_HIT", "pt", user_id=user_id))
            return {
                "score": cached.get("score", 0),
                "details": cached.get("details"),
                "date": cached.get("date", now),
                "created_at": cached.get("created_at", now),
                "from_cache": True
            }
        
        logger.debug(get_message("SCORE_CACHE_MONGODB_MISS", "pt", user_id=user_id))
        return None
        
    except Exception as e:
        logger.warning(get_message("SCORE_CACHE_MONGODB_GET_ERROR", "pt", user_id=user_id, error=str(e)))
        return None


async def set_cached_score_mongodb(user_id: str, score_data: Dict[str, Any], db) -> None:
    """
    Armazena score no cache MongoDB.
    SEM TTL: Dados históricos mantidos para análise.

    🔧 USO:
        await set_cached_score_mongodb(user_id, score_data, db)

    📋 PADRÃO:
        - Upsert no MongoDB (evita duplicatas)
        - SEM TTL (dados mantidos para sempre)
        - Verifica se db é None
        - Log com i18n
    """
    _validate_user_id(user_id)
    
    if db is None:
        logger.warning(get_message("SCORE_CACHE_DB_NONE", "pt", user_id=user_id))
        return
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    score_entry = {
        "user_id": user_id,
        "score": score_data.get("score", 0),
        "details": score_data.get("details"),
        "date": score_data.get("date", now),
        "created_at": now,
        "updated_at": now
    }
    
    try:
        await db.score_history.update_one(
            {
                "user_id": user_id,
                "created_at": {"$gte": today_start, "$lt": today_end}
            },
            {"$set": score_entry},
            upsert=True
        )
        logger.debug(get_message("SCORE_CACHE_MONGODB_SET", "pt", user_id=user_id))
    except Exception as e:
        logger.warning(get_message("SCORE_CACHE_MONGODB_SET_ERROR", "pt", user_id=user_id, error=str(e)))


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

async def get_score_with_cache(user_id: str, db) -> Dict[str, Any]:
    """
    Busca score com cache (Redis primeiro, fallback MongoDB).

    🔧 USO:
        result = await get_score_with_cache(user_id, db)
        print(result["score"])  # 68
        print(result["from_cache"])  # True/False

    📋 PADRÃO:
        - 1. Tenta Redis
        - 2. Tenta MongoDB (fallback)
        - 3. Recalcula se cache miss
        - 🔧 NOVO: Registra métricas de hit/miss
        - Verifica se db é None
        - Log com i18n
    """
    _validate_user_id(user_id)
    
    if db is None:
        logger.error(get_message("SCORE_CACHE_DB_NONE", "pt", user_id=user_id))
        _score_metrics.record_miss()
        result = await calculate_score(user_id, db)
        return {
            "score": result.get("score", 0),
            "details": result.get("details"),
            "date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "from_cache": False
        }
    
    # 1. Tenta Redis
    cached = await get_cached_score_redis(user_id)
    if cached:
        cached["from_cache"] = True
        logger.debug(get_message("SCORE_CACHE_FINAL_HIT", "pt", user_id=user_id))
        return cached
    
    # 2. Tenta MongoDB
    cached = await get_cached_score_mongodb(user_id, db)
    if cached:
        # Armazena no Redis para próximas requisições
        await set_cached_score_redis(user_id, cached)
        logger.debug(get_message("SCORE_CACHE_FINAL_HIT_MONGODB", "pt", user_id=user_id))
        return cached
    
    # 3. Cache miss - recalcula
    # 🔧 NOVO: Registra miss nas métricas
    _score_metrics.record_miss()
    logger.info(get_message("SCORE_CACHE_MISS_RECALCULATING", "pt", user_id=user_id))
    
    result = await calculate_score(user_id, db)
    
    now = datetime.now(timezone.utc)
    score_data = {
        "score": result.get("score", 0),
        "details": result.get("details"),
        "date": now,
        "created_at": now,
        "from_cache": False
    }
    
    # Armazena em ambos os caches
    await set_cached_score_redis(user_id, score_data)
    await set_cached_score_mongodb(user_id, score_data, db)
    
    logger.info(get_message("SCORE_CACHE_RECALCULATED", "pt", user_id=user_id))
    
    return score_data


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Buscar score com cache:
   from app.utils.score_cache import get_score_with_cache
   result = await get_score_with_cache(user_id, db)
   print(result["score"])  # 68

2. Invalidar cache individual:
   from app.utils.score_cache import invalidate_cache_redis
   await invalidate_cache_redis(user_id)

3. Invalidar cache em lote:
   from app.utils.score_cache import invalidate_cache_batch
   await invalidate_cache_batch(["user1", "user2", "user3"])

4. Ver métricas:
   from app.utils.score_cache import get_score_metrics
   metrics = get_score_metrics()
   print(metrics["hit_rate"])  # 85.0%

5. Resetar métricas:
   from app.utils.score_cache import reset_score_metrics
   reset_score_metrics()
"""


# ============================================================
# DECISÕES DOCUMENTADAS
# ============================================================
#
# ✅ Funções reutilizáveis para cache de score
# ✅ Suporte a Redis com fallback MongoDB
# ✅ SEM TTL no MongoDB (dados históricos mantidos)
# ✅ Upsert no MongoDB (evita duplicatas)
# ✅ Validações robustas
# ✅ Logs estruturados
# ✅ Internacionalização (i18n) nos logs
# ✅ Logger padronizado com setup_logger()
# ✅ Validação de user_id
# ✅ Campo 'date' em vez de 'created_at' no retorno
# ✅ Verificação de db None
# ✅ 🔧 NOVO: Métricas de hit/miss do cache
# ✅ 🔧 NOVO: TTL variável por score
# ✅ 🔧 NOVO: Invalidação em lote (batch)
# ✅ Documentação completa
#
# ❌ Não implementado (Pós-MVP):
#   - Cache distribuído (cluster Redis)
#   - Métricas persistentes (em Redis/PostgreSQL)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado i18n, validação de user_id, logger padronizado (06/07/2026)
#   - v3: Corrigido campo 'date', verificação de db None (06/07/2026)
#   - v4: Adicionado métricas, TTL variável, invalidação batch (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO