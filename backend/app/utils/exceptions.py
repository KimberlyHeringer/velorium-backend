"""
Exceções Internacionalizadas (i18n)
Arquivo: backend/app/utils/exceptions.py

Funcionalidades:
- I18nHTTPException: Classe base com tradução automática
- ValidationException: 400 Bad Request
- BadRequestException: Alias para ValidationException
- NotFoundException: 404 Not Found
- UnauthorizedException: 401 Unauthorized
- ForbiddenException: 403 Forbidden
- ConflictException: 409 Conflict
- RateLimitException: 429 Too Many Requests
- TooManyRequestsException: Alias para RateLimitException
- InternalServerException: 500 Internal Server Error
- ServiceUnavailableException: 503 Service Unavailable

Principais features:
- 🔧 CORRIGIDO: Documentação completa
- 🔧 CORRIGIDO: Suporte a variáveis nas mensagens (formatação com **kwargs)
- 🔧 CORRIGIDO: Headers explícitos
- 🔧 CORRIGIDO: RateLimitException (429)
- 🔧 CORRIGIDO: ServiceUnavailableException (503)
- 🔧 CORRIGIDO: InternalServerException (500)
- 🔧 CORRIGIDO: Aliases para compatibilidade semântica
- 🔧 CORRIGIDO: Fallback para detail se get_message retornar None
- 🔧 CORRIGIDO: Logger com setup_logger (não importado dentro da função)
- ✅ Internacionalização via get_message() e get_language_from_request()

🔧 USO:
    from app.utils.exceptions import (
        I18nHTTPException,
        ValidationException,
        BadRequestException,
        NotFoundException,
        UnauthorizedException,
        ForbiddenException,
        ConflictException,
        RateLimitException,
        TooManyRequestsException,
        InternalServerException,
        ServiceUnavailableException
    )
    
    # Exceção genérica com mensagem traduzida
    raise I18nHTTPException(
        status_code=404,
        message_key="ACHIEVEMENT_NOT_FOUND",
        request=request
    )
    
    # Exceção com variáveis
    raise NotFoundException(
        message_key="ERROR_USER_NOT_FOUND",
        request=request,
        name="João"  # Será substituído na mensagem
    )
    
    # Exceções específicas
    raise ValidationException(message_key="ERROR_VALIDATION", request=request)
    raise RateLimitException(message_key="RATE_LIMIT_EXCEEDED", request=request)
    raise InternalServerException(message_key="ERROR_SERVER", request=request)
"""

from fastapi import HTTPException, Request
from typing import Optional

from app.utils.i18n import get_message, get_language_from_request
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)


class I18nHTTPException(HTTPException):
    """
    Exceção HTTP com mensagem traduzível baseada no idioma do usuário.
    
    🔧 CARACTERÍSTICAS:
    - Detecta automaticamente o idioma do usuário via header Accept-Language
    - Traduz a mensagem usando o dicionário i18n
    - 🔧 Suporte a variáveis na mensagem (ex: "Usuário {name} não encontrado")
    - 🔧 Fallback para a própria chave se a mensagem não for encontrada
    - Mantém compatibilidade com HTTPException do FastAPI
    
    Args:
        status_code (int): Código HTTP (404, 400, 401, etc.)
        message_key (str): Chave da mensagem no dicionário i18n
        request (Request, optional): Objeto da requisição para detectar idioma
        language (str, optional): Idioma específico (sobrescreve o header)
        headers (dict, optional): Headers HTTP adicionais
        **kwargs: Argumentos para formatação da mensagem (ex: name="João")
    
    Exemplo:
        >>> raise I18nHTTPException(
        ...     status_code=404,
        ...     message_key="ACHIEVEMENT_NOT_FOUND",
        ...     request=request
        ... )
        
        >>> raise I18nHTTPException(
        ...     status_code=404,
        ...     message_key="ERROR_USER_NOT_FOUND",
        ...     request=request,
        ...     name="João"  # Substitui {name} na mensagem
        ... )
    """
    
    def __init__(
        self,
        status_code: int,
        message_key: str,
        request: Optional[Request] = None,
        language: Optional[str] = None,
        headers: Optional[dict] = None,
        **kwargs
    ):
        # Determina o idioma
        if language:
            lang = language
        elif request:
            lang = get_language_from_request(request)
        else:
            lang = "pt"
        
        # 🔧 CORRIGIDO: Fallback para detail se get_message retornar None
        detail = get_message(message_key, lang)
        if not detail:
            logger.warning(f"⚠️ Mensagem não encontrada para chave: {message_key} (idioma: {lang})")
            detail = message_key  # Fallback para a própria chave
        
        # 🔧 CORRIGIDO: Suporte a variáveis
        if kwargs:
            try:
                detail = detail.format(**kwargs)
            except KeyError as e:
                # Se houver erro na formatação, mantém a mensagem original
                # e registra um aviso
                logger.warning(f"⚠️ Erro ao formatar mensagem '{message_key}': chave {e} não encontrada")
        
        # Armazena metadados adicionais
        self.message_key = message_key
        self.language = lang
        self.kwargs = kwargs
        
        # Chama o construtor da classe pai com headers
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers
        )


# ================================================================
# EXCEÇÕES ESPECÍFICAS
# ================================================================

class ValidationException(I18nHTTPException):
    """
    Exceção para erros de validação (400 Bad Request).
    
    Exemplo:
        >>> raise ValidationException(
        ...     message_key="ERROR_VALIDATION",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "ERROR_VALIDATION",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=400,
            message_key=message_key,
            request=request,
            **kwargs
        )


class BadRequestException(ValidationException):
    """
    🆕 NOVO: Alias para ValidationException (400 Bad Request).
    Mantido para compatibilidade semântica.
    
    Exemplo:
        >>> raise BadRequestException(
        ...     message_key="ERROR_VALIDATION",
        ...     request=request
        ... )
    """
    pass


class NotFoundException(I18nHTTPException):
    """
    Exceção para recursos não encontrados (404 Not Found).
    
    Exemplo:
        >>> raise NotFoundException(
        ...     message_key="ACHIEVEMENT_NOT_FOUND",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "ERROR_NOT_FOUND",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=404,
            message_key=message_key,
            request=request,
            **kwargs
        )


class UnauthorizedException(I18nHTTPException):
    """
    Exceção para não autorizado (401 Unauthorized).
    
    Exemplo:
        >>> raise UnauthorizedException(
        ...     message_key="AUTH_INVALID_CREDENTIALS",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "ERROR_UNAUTHORIZED",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=401,
            message_key=message_key,
            request=request,
            **kwargs
        )


class ForbiddenException(I18nHTTPException):
    """
    Exceção para acesso negado (403 Forbidden).
    
    Exemplo:
        >>> raise ForbiddenException(
        ...     message_key="ERROR_FORBIDDEN",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "ERROR_FORBIDDEN",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=403,
            message_key=message_key,
            request=request,
            **kwargs
        )


class ConflictException(I18nHTTPException):
    """
    Exceção para conflito (409 Conflict).
    
    Exemplo:
        >>> raise ConflictException(
        ...     message_key="ACHIEVEMENT_ALREADY_EXISTS",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "ERROR_CONFLICT",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=409,
            message_key=message_key,
            request=request,
            **kwargs
        )


class RateLimitException(I18nHTTPException):
    """
    Exceção para limite de requisições (429 Too Many Requests).
    
    Exemplo:
        >>> raise RateLimitException(
        ...     message_key="RATE_LIMIT_EXCEEDED",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "RATE_LIMIT_EXCEEDED",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=429,
            message_key=message_key,
            request=request,
            **kwargs
        )


class TooManyRequestsException(RateLimitException):
    """
    🆕 NOVO: Alias para RateLimitException (429 Too Many Requests).
    Mantido para compatibilidade semântica.
    
    Exemplo:
        >>> raise TooManyRequestsException(
        ...     message_key="RATE_LIMIT_EXCEEDED",
        ...     request=request
        ... )
    """
    pass


class InternalServerException(I18nHTTPException):
    """
    🆕 NOVO: Exceção para erro interno do servidor (500 Internal Server Error).
    
    Exemplo:
        >>> raise InternalServerException(
        ...     message_key="ERROR_SERVER",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "ERROR_SERVER",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=500,
            message_key=message_key,
            request=request,
            **kwargs
        )


class ServiceUnavailableException(I18nHTTPException):
    """
    Exceção para serviço indisponível (503 Service Unavailable).
    
    Exemplo:
        >>> raise ServiceUnavailableException(
        ...     message_key="ERROR_SERVICE_UNAVAILABLE",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        message_key: str = "ERROR_SERVICE_UNAVAILABLE",
        request: Optional[Request] = None,
        **kwargs
    ):
        super().__init__(
            status_code=503,
            message_key=message_key,
            request=request,
            **kwargs
        )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ I18nHTTPException: classe base com tradução automática
# ✅ ValidationException: 400 Bad Request
# ✅ 🆕 BadRequestException: Alias para ValidationException
# ✅ NotFoundException: 404 Not Found
# ✅ UnauthorizedException: 401 Unauthorized
# ✅ ForbiddenException: 403 Forbidden
# ✅ ConflictException: 409 Conflict
# ✅ RateLimitException: 429 Too Many Requests
# ✅ 🆕 TooManyRequestsException: Alias para RateLimitException
# ✅ 🆕 InternalServerException: 500 Internal Server Error
# ✅ ServiceUnavailableException: 503 Service Unavailable
# ✅ Suporte a detecção automática de idioma via Request
# ✅ Suporte a idioma específico via parâmetro language
# ✅ 🔧 CORRIGIDO: Suporte a variáveis nas mensagens (**kwargs)
# ✅ 🔧 CORRIGIDO: Headers explícitos
# ✅ 🔧 CORRIGIDO: Documentação completa
# ✅ 🔧 CORRIGIDO: Fallback para detail se get_message retornar None
# ✅ 🔧 CORRIGIDO: Logger com setup_logger (não importado dentro da função)
# ✅ Compatível com HTTPException do FastAPI
#
# ❌ Não implementado (Pós-MVP):
#   - Nenhum (completo para MVP)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Suporte a variáveis, RateLimitException, ServiceUnavailableException (05/07/2026)
#   - v3: Correções - Fallback detail, logger setup (05/07/2026)
#   - v4: Novas classes - BadRequestException, TooManyRequestsException, InternalServerException (05/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO