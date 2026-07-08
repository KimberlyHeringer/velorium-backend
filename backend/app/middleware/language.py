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

📋 ESTRUTURA:
    - LanguageMiddleware: Middleware que captura e armazena o idioma
    - get_language_from_state(): Função auxiliar para obter o idioma

Regra: 7.1 (Internacionalização)

🔧 USO:
    from app.middleware.language import LanguageMiddleware, get_language_from_state
    
    # Registrar middleware
    app.add_middleware(LanguageMiddleware)
    
    # Usar em rotas
    @router.get("/")
    async def get_data(request: Request):
        language = get_language_from_state(request)
        mensagem = get_message("SUCCESS_CREATED", language)
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import os

from app.utils.i18n import get_language_from_request
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# ========== CONFIGURAÇÃO ==========
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


class LanguageMiddleware(BaseHTTPMiddleware):
    """
    Middleware que captura o idioma do usuário e armazena no request.state.
    
    🔧 CARACTERÍSTICAS:
    - Lê o header Accept-Language
    - Armazena o idioma em request.state.language
    - Fallback para "pt" se o idioma não for suportado
    - 🔧 CORRIGIDO: Usa ENVIRONMENT para logs
    
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
        
        # 🔧 CORRIGIDO: Log em desenvolvimento (usando ENVIRONMENT)
        if ENVIRONMENT == "development":
            logger.debug(f"🌐 Idioma detectado: {language} (Accept-Language: {request.headers.get('Accept-Language', 'N/A')})")
        
        # Continua o processamento da requisição
        response = await call_next(request)
        
        return response


# ================================================================
# FUNÇÃO AUXILIAR
# ================================================================

def get_language_from_state(request: Request) -> str:
    """
    Função auxiliar para obter o idioma do request.state.
    
    🔧 USO:
        language = get_language_from_state(request)
        if language == "pt":
            print("Português")
    
    Args:
        request (Request): Objeto da requisição
    
    Returns:
        str: Código do idioma (pt, en, es, zh)
    
    Exemplo:
        >>> language = get_language_from_state(request)
        >>> print(language)  # "pt"
    """
    return getattr(request.state, "language", "pt")


# ================================================================
# NOTAS DE IMPLEMENTAÇÃO
# ================================================================

"""
📌 COMO USAR:

1. Registrar o middleware no main.py:
   from app.middleware.language import LanguageMiddleware
   app.add_middleware(LanguageMiddleware)

2. Usar o idioma em uma rota:
   from app.middleware.language import get_language_from_state
   
   @router.get("/")
   async def get_data(request: Request):
       language = get_language_from_state(request)
       print(f"Idioma do usuário: {language}")

3. Usar com i18n:
   from app.middleware.language import get_language_from_state
   from app.utils.i18n import get_message
   
   @router.get("/")
   async def get_data(request: Request):
       language = get_language_from_state(request)
       message = get_message("SUCCESS_CREATED", language)

4. Testar com diferentes headers:
   curl -H "Accept-Language: en" http://localhost:8000/
   curl -H "Accept-Language: es" http://localhost:8000/
   curl -H "Accept-Language: zh" http://localhost:8000/
"""


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ Middleware que captura Accept-Language
# ✅ Armazena idioma em request.state.language
# ✅ Fallback para "pt" se o idioma não for suportado
# ✅ 🔧 CORRIGIDO: Log em desenvolvimento usando ENVIRONMENT
# ✅ Função auxiliar get_language_from_state()
# ✅ Compatível com FastAPI e Starlette
# ✅ Documentação completa
#
# ❌ Não implementado (Pós-MVP):
#   - Cache de idioma por usuário (via banco ou Redis)
#   - Suporte a detecção de idioma via navegador (para web)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Corrigido log com ENVIRONMENT (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO