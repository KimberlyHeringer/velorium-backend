"""
Configuração de Rate Limiting para FastAPI
Arquivo: backend/app/utils/rate_limiter.py

🔧 MODIFICADO: Regra 2.8 - Adicionado logger para rastrear limites excedidos
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# Criar o limiter baseado no IP do cliente
limiter = Limiter(key_func=get_remote_address)


def init_rate_limiter(app: FastAPI):
    """Inicializa o rate limiter no app FastAPI"""
    app.state.limiter = limiter
    
    logger.info("Rate limiter inicializado com sucesso")
    
    # Handler personalizado para erro 429 (evita importar método privado)
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        client_ip = get_remote_address(request)
        logger.warning(f"Rate limit excedido para IP: {client_ip} - URL: {request.url.path}")
        
        return JSONResponse(
            status_code=429,
            content={"detail": "Muitas requisições. Tente novamente mais tarde."}
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