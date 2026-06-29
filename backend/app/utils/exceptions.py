"""
Exceções Internacionalizadas (i18n)
Arquivo: backend/app/utils/exceptions.py

Funcionalidade: Fornece exceções com mensagens traduzidas baseadas no idioma do usuário.

🔧 USO:
    from app.utils.exceptions import I18nHTTPException, NotFoundException
    
    # Lançar exceção com mensagem traduzida
    raise I18nHTTPException(
        status_code=404,
        message_key="ACHIEVEMENT_NOT_FOUND",
        request=request
    )
    
    # Ou usar exceções específicas
    raise NotFoundException(
        message_key="ACHIEVEMENT_NOT_FOUND",
        request=request
    )
"""

from fastapi import HTTPException, Request
from typing import Optional

from app.utils.i18n import get_message, get_language_from_request


class I18nHTTPException(HTTPException):
    """
    Exceção HTTP com mensagem traduzível baseada no idioma do usuário.
    
    🔧 CARACTERÍSTICAS:
    - Detecta automaticamente o idioma do usuário via header Accept-Language
    - Traduz a mensagem usando o dicionário i18n
    - Mantém compatibilidade com HTTPException do FastAPI
    
    Args:
        status_code (int): Código HTTP (404, 400, 401, etc.)
        message_key (str): Chave da mensagem no dicionário i18n
        request (Request, optional): Objeto da requisição para detectar idioma
        language (str, optional): Idioma específico (sobrescreve o header)
        **kwargs: Argumentos adicionais para formatação (futuro)
    
    Exemplo:
        >>> raise I18nHTTPException(
        ...     status_code=404,
        ...     message_key="ACHIEVEMENT_NOT_FOUND",
        ...     request=request
        ... )
    """
    
    def __init__(
        self,
        status_code: int,
        message_key: str,
        request: Optional[Request] = None,
        language: Optional[str] = None,
        **kwargs
    ):
        # Determina o idioma
        if language:
            lang = language
        elif request:
            lang = get_language_from_request(request)
        else:
            lang = "pt"
        
        # Traduz a mensagem
        detail = get_message(message_key, lang)
        
        # Armazena metadados adicionais
        self.message_key = message_key
        self.language = lang
        
        # Chama o construtor da classe pai
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=kwargs.get("headers")
        )


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


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ I18nHTTPException: classe base com tradução automática
# ✅ ValidationException: 400 Bad Request
# ✅ NotFoundException: 404 Not Found
# ✅ UnauthorizedException: 401 Unauthorized
# ✅ ForbiddenException: 403 Forbidden
# ✅ ConflictException: 409 Conflict
# ✅ Suporte a detecção automática de idioma via Request
# ✅ Suporte a idioma específico via parâmetro language
# ✅ Compatível com HTTPException do FastAPI
#
# ⏳ PENDÊNCIAS PÓS-MVP:
# - Adicionar suporte a variáveis nas mensagens (ex: "Usuário {name} não encont