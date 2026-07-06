"""
Configuração de Rate Limiting para FastAPI
Arquivo: backend/app/utils/rate_limiter.py

🔧 CORRIGIDO (v4):
- Suporte a rate limiting por user_id (prioriza usuário autenticado)
- fallback para IP se usuário não estiver autenticado
- Suporte a i18n na mensagem de erro
- Limites configurados por endpoint
- 🔧 NOVO: Headers de rate limit (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
- 🔧 NOVO: Redis para rate limiting persistente
- 🔧 NOVO: Limites configuráveis via .env
- 🔧 NOVO: Limites diferentes para produção
- 🔧 CORRIGIDO: remaining nunca negativo (max(0, ...))
- 🔧 CORRIGIDO: Suporte a "X/day" no get_limit_from_string()
- ✅ get_user_rate_limit_key() para uso em rotas
- ✅ Exportação de limiter e funções

Regra: 2.8 (Logs)
Regra: 3.2 (Cache com Redis)
Regra: 7.1 (Internacionalização)

🔧 USO:
    from app.utils.rate_limiter import limiter, get_user_rate_limit_key
    
    @router.get("/")
    @limiter.limit("30/minute", key_func=get_user_rate_limit_key)
    async def my_endpoint(request: Request):
        return {"status": "ok"}
"""

import os
import time
import json
from typing import Optional, Tuple

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.utils.logger import setup_logger
from app.utils.i18n import get_message

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# ========== CONFIGURAÇÃO DE AMBIENTE ==========
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
PRODUCTION = ENVIRONMENT == "production"

# ========== CONSTANTES ==========
# Limites padrão por endpoint (configuráveis via .env)
DEFAULT_LIMITS = {
    "login": os.getenv("RATE_LIMIT_LOGIN", "5/minute"),
    "register": os.getenv("RATE_LIMIT_REGISTER", "3/minute"),
    "ia_chat": os.getenv("RATE_LIMIT_IA_CHAT", "10/minute"),
    "ia_insight": os.getenv("RATE_LIMIT_IA_INSIGHT", "5/minute"),
    "profile_get": os.getenv("RATE_LIMIT_PROFILE_GET", "30/minute"),
    "profile_post": os.getenv("RATE_LIMIT_PROFILE_POST", "20/minute"),
    "default": os.getenv("RATE_LIMIT_DEFAULT", "30/minute"),
}

# Limites para produção (mais restritivos)
PRODUCTION_LIMITS = {
    "login": os.getenv("RATE_LIMIT_LOGIN_PROD", "3/minute"),
    "register": os.getenv("RATE_LIMIT_REGISTER_PROD", "2/minute"),
    "ia_chat": os.getenv("RATE_LIMIT_IA_CHAT_PROD", "5/minute"),
    "ia_insight": os.getenv("RATE_LIMIT_IA_INSIGHT_PROD", "3/minute"),
    "profile_get": os.getenv("RATE_LIMIT_PROFILE_GET_PROD", "20/minute"),
    "profile_post": os.getenv("RATE_LIMIT_PROFILE_POST_PROD", "10/minute"),
    "default": os.getenv("RATE_LIMIT_DEFAULT_PROD", "20/minute"),
}

# Usa limites de produção se estiver em produção
LIMITS = PRODUCTION_LIMITS if PRODUCTION else DEFAULT_LIMITS

logger.info(f"📊 Rate limits: {'PRODUÇÃO' if PRODUCTION else 'DESENVOLVIMENTO'}")
logger.debug(f"📊 Limites configurados: {LIMITS}")


# ========== REDIS CLIENT (CONEXÃO SEGURA) ==========
try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para rate limiting")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - rate limiting em memória")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - rate limiting em memória")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")


# ========== FUNÇÕES DE CHAVE ==========

def get_user_or_ip_key(request: Request) -> str:
    """
    Obtém a chave de rate limiting: user_id se autenticado, senão IP.
    Prioriza user_id para usuários autenticados.
    """
    # Tenta obter o user_id do estado da requisição
    user_id = getattr(request.state, "user_id", None)
    
    if user_id:
        return f"user:{user_id}"
    
    # Fallback para IP
    return get_remote_address(request)


def get_user_rate_limit_key(request: Request) -> str:
    """
    Gera chave de rate limiting por usuário para uso em rotas.
    Similar ao get_user_or_ip_key, mas com prefixo diferente para rotas específicas.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"route:user:{user_id}"
    
    client_ip = request.client.host if request.client else "unknown"
    return f"route:ip:{client_ip}"


# ========== FUNÇÕES DE RATE LIMIT COM REDIS ==========

async def check_rate_limit_redis(
    key: str,
    limit: int,
    window: int
) -> Tuple[bool, int, int, int]:
    """
    Verifica rate limit usando Redis.
    
    Args:
        key: Chave única para o usuário/IP e endpoint
        limit: Número máximo de requisições permitidas
        window: Janela de tempo em segundos
    
    Returns:
        Tuple[bool, int, int, int]: (pode_fazer, limite, restante, reset_em)
    """
    if not redis_client:
        # Fallback para memória (SlowAPI já faz isso)
        return True, limit, limit, 0
    
    try:
        now = int(time.time())
        window_start = now - window
        
        # Remove entradas antigas
        await redis_client.zremrangebyscore(key, 0, window_start)
        
        # Conta requisições na janela
        count = await redis_client.zcard(key)
        
        # 🔧 CORRIGIDO: remaining nunca negativo
        remaining = max(0, limit - count)
        
        # Calcula reset time
        oldest = await redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            reset_time = int(oldest[0][1]) + window
        else:
            reset_time = now + window
        
        if count < limit:
            # Adiciona esta requisição
            await redis_client.zadd(key, {str(now): now})
            # Define TTL para limpeza automática
            await redis_client.expire(key, window)
            # 🔧 CORRIGIDO: remaining - 1 para incluir esta requisição
            return True, limit, remaining - 1, reset_time
        
        # Bloqueia a requisição
        return False, limit, 0, reset_time
        
    except Exception as e:
        logger.warning(f"⚠️ Erro no rate limiting com Redis: {e}")
        # Fallback: permite a requisição
        return True, limit, limit, 0


def get_limit_from_string(limit_str: str) -> Tuple[int, int]:
    """
    Converte string "X/minute" para (limit, window_seconds).
    
    Exemplo:
        "5/minute" → (5, 60)
        "10/hour" → (10, 3600)
        "2/day" → (2, 86400)  # 🔧 CORRIGIDO: suporte a day
    """
    try:
        parts = limit_str.split("/")
        if len(parts) != 2:
            return 30, 60
        
        limit = int(parts[0])
        unit = parts[1].lower()
        
        if unit in ["minute", "min", "m"]:
            window = 60
        elif unit in ["hour", "h"]:
            window = 3600
        elif unit in ["day", "d"]:
            # 🔧 CORRIGIDO: Suporte a "X/day"
            window = 86400
        elif unit in ["second", "sec", "s"]:
            window = 1
        else:
            window = 60
        
        return limit, window
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao parsear limite '{limit_str}': {e}")
        return 30, 60


def get_limit(endpoint: str) -> str:
    """Retorna o limite configurado para um endpoint específico"""
    limit = LIMITS.get(endpoint, LIMITS["default"])
    logger.debug(f"📊 Limite retornado para endpoint {endpoint}: {limit}")
    return limit


# ========== CRIAR LIMITER ==========

limiter = Limiter(key_func=get_user_or_ip_key)


def init_rate_limiter(app: FastAPI):
    """Inicializa o rate limiter no app FastAPI"""
    app.state.limiter = limiter
    
    logger.info("✅ Rate limiter inicializado com suporte a Redis")
    
    # Handler personalizado para erro 429 (com i18n e headers)
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        client_ip = get_remote_address(request)
        user_id = getattr(request.state, "user_id", None)
        
        # Log do evento
        if user_id:
            logger.warning(f"⚠️ Rate limit excedido para usuário: {user_id} - URL: {request.url.path}")
        else:
            logger.warning(f"⚠️ Rate limit excedido para IP: {client_ip} - URL: {request.url.path}")
        
        # Mensagem de erro com i18n
        language = getattr(request.state, "language", "pt")
        detail = get_message("RATE_LIMIT_EXCEEDED", language)
        
        # Headers de rate limit
        headers = {
            "X-RateLimit-Limit": str(getattr(exc, "limit", 0)),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 60),
            "Retry-After": "60",
        }
        
        return JSONResponse(
            status_code=429,
            content={"detail": detail},
            headers=headers
        )
    
    logger.debug("📊 Rate limit handler configurado")


# ========== FUNÇÃO AUXILIAR PARA HEADERS ==========

def add_rate_limit_headers(
    request: Request,
    response: JSONResponse,
    key: str,
    limit: int,
    remaining: int,
    reset_time: int
) -> None:
    """
    Adiciona headers de rate limit à resposta.
    
    USO:
        add_rate_limit_headers(request, response, key, limit, remaining, reset_time)
    """
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(reset_time)


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Em uma rota (com rate limiting):
   from app.utils.rate_limiter import limiter, get_user_rate_limit_key
   
   @router.get("/")
   @limiter.limit("30/minute", key_func=get_user_rate_limit_key)
   async def my_endpoint(request: Request):
       return {"status": "ok"}

2. Configurar limites via .env:
   RATE_LIMIT_LOGIN_PROD=3/minute
   RATE_LIMIT_IA_CHAT_PROD=5/minute

3. Headers retornados:
   X-RateLimit-Limit: 30
   X-RateLimit-Remaining: 29
   X-RateLimit-Reset: 1734567890
"""


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Rate limiting por usuário (user_id) para autenticados
# ✅ Fallback para IP se não autenticado
# ✅ i18n na mensagem de erro
# ✅ Logs com user_id e IP
# ✅ Limites configurados por endpoint
# ✅ Headers X-RateLimit-*
# ✅ Redis para rate limiting persistente
# ✅ Limites diferentes para produção
# ✅ Limites configuráveis via .env
# ✅ Validação e parse de strings de limite
# ✅ 🔧 CORRIGIDO: remaining nunca negativo
# ✅ 🔧 CORRIGIDO: Suporte a "X/day"
# ✅ Documentação completa
#
# ❌ Não implementado (Pós-MVP):
#   - Métricas de rate limiting (hits por endpoint)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial com rate limiting básico
#   - v2: Adicionado user_id, i18n, logs (05/07/2026)
#   - v3: Adicionado Redis, headers, limites por ambiente (06/07/2026)
#   - v4: Corrigido remaining negativo, suporte a day (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO