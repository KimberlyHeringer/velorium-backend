"""
Middleware de Captura de Idioma
Arquivo: backend/app/middleware/language.py

Funcionalidade: Captura o idioma do usuário via header Accept-Language
e armazena no request.state para uso em toda a aplicação.

🔧 USO:
    # Registrar no main.py
    from app.middleware.language import LanguageMiddleware
    app.add_middleware(LanguageMiddleware)
    
    # Usar em rotas
    @router.get("/")
    async def get_data(request: Request):
        language = request.state.language  # "pt", "en", "es", "zh"
        # ... usar o idioma
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.i18n import get_language_from_request
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)


class LanguageMiddleware(BaseHTTPMiddleware):
    """
    Middleware que captura o idioma do usuário e armazena no request.state.
    
    🔧 CARACTERÍSTICAS:
    - Lê o header Accept-Language
    - Armazena o idioma em request.state.language
    - Fallback para "pt" se o idioma não for suportado
    
    🔧 USO:
        app.add_middleware(LanguageMiddleware)
    
    🔧 ACESSO:
        language = request.state.language  # "pt", "en", "es", "zh"
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Processa a requisição e adiciona o idioma ao estado.
        
        Args:
            request (Request): Objeto da requisição
            call_next: Próximo middleware ou handler
        
        Returns:
            Response: Resposta da requisição
        """
        # Captura o idioma do header
        language = get_language_from_request(request)
        
        # Armazena no estado da requisição
        request.state.language = language
        
        # Log em desenvolvimento (opcional)
        if __debug__:
            logger.debug(f"🌐 Idioma detectado: {language} (Accept-Language: {request.headers.get('Accept-Language', 'N/A')})")
        
        # Continua o processamento da requisição
        response = await call_next(request)
        
        return response


# ========== FUNÇÃO AUXILIAR ==========

def get_language_from_state(request: Request) -> str:
    """
    Função auxiliar para obter o idioma do request.state.
    
    Args:
        request (Request): Objeto da requisição
    
    Returns:
        str: Código do idioma (pt, en, es, zh)
    
    Exemplo:
        >>> language = get_language_from_state(request)
        >>> print(language)  # "pt"
    """
    return getattr(request.state, "language", "pt")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Middleware que captura Accept-Language
# ✅ Armazena idioma em request.state.language
# ✅ Fallback para "pt" se o idioma não for suportado
# ✅ Log em desenvolvimento para debug
# ✅ Função auxiliar get_language_from_state()
# ✅ Compatível com FastAPI e Starlette
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO