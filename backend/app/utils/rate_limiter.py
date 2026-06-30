"""
Configuração de Rate Limiting para FastAPI
Arquivo: backend/app/utils/rate_limiter.py

🔧 CORRIGIDO:
- Suporte a rate limiting por user_id (prioriza usuário autenticado)
- fallback para IP se usuário não estiver autenticado
- Suporte a i18n na mensagem de erro
- Limites configurados por endpoint
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.utils.logger import setup_logger
from app.utils.i18n import get_message

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)


def get_user_or_ip_key(request: Request) -> str:
    """
    Obtém a chave de rate limiting: user_id se autenticado, senão IP.
    🔧 CORRIGIDO: Prioriza user_id para usuários autenticados.
    """
    # Tenta obter o user_id do estado da requisição
    user_id = getattr(request.state, "user_id", None)
    
    if user_id:
        return f"user:{user_id}"
    
    # Fallback para IP
    return get_remote_address(request)


# 🔧 CORRIGIDO: Criar o limiter com a função de chave personalizada
limiter = Limiter(key_func=get_user_or_ip_key)


def init_rate_limiter(app: FastAPI):
    """Inicializa o rate limiter no app FastAPI"""
    app.state.limiter = limiter
    
    logger.info("✅ Rate limiter inicializado com suporte a user_id")
    
    # Handler personalizado para erro 429 (com i18n)
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        client_ip = get_remote_address(request)
        user_id = getattr(request.state, "user_id", None)
        
        if user_id:
            logger.warning(f"Rate limit excedido para usuário: {user_id} - URL: {request.url.path}")
        else:
            logger.warning(f"Rate limit excedido para IP: {client_ip} - URL: {request.url.path}")
        
        # 🔧 NOVO: Mensagem de erro com i18n
        language = getattr(request.state, "language", "pt")
        detail = get_message("RATE_LIMIT_EXCEEDED", language)
        
        return JSONResponse(
            status_code=429,
            content={"detail": detail}
        )
    
    logger.debug("Rate limit handler configurado")


# Limites por endpoint (requisições por minuto)
LIMITS = {
    "login": "5/minute",      # Máximo 5 tentativas de login por minuto
    "register": "3/minute",   # Máximo 3 registros por minuto
    "ia_chat": "10/minute",   # Máximo 10 mensagens de IA por minuto
    "ia_insight": "5/minute", # Máximo 5 insights por minuto
    "default": "30/minute",   # Padrão para outras rotas
}


def get_limit(endpoint: str) -> str:
    """Retorna o limite configurado para um endpoint específico"""
    limit = LIMITS.get(endpoint, LIMITS["default"])
    logger.debug(f"Limite retornado para endpoint {endpoint}: {limit}")
    return limit


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. 🔧 NOVO: get_user_or_ip_key() - prioriza user_id sobre IP
2. 🔧 NOVO: limiter usa get_user_or_ip_key em vez de get_remote_address
3. 🔧 NOVO: i18n na mensagem de erro (RATE_LIMIT_EXCEEDED)
4. 🔧 NOVO: Logs com user_id quando disponível

📌 CHAVES I18N REFERENCIADAS:
   - RATE_LIMIT_EXCEEDED → "Muitas requisições. Tente novamente mais tarde."

✅ STATUS: PRONTO PARA PRODUÇÃO
================================================================================
"""