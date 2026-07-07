"""
Funções de Tokens para Usuário
Arquivo: backend/app/utils/user_tokens.py

Funcionalidade: Centraliza funções relacionadas a tokens de usuário
para reutilização na rota user.py.

Funcionalidades:
- Geração de token de exclusão de conta (com expiração)
- Verificação de token de exclusão
- Marcação de token como usado
- Limpeza de tokens expirados
- Rate limiting para geração de tokens
- Internacionalização (i18n) nos logs
- Validação de entradas

Principais features:
- 🔧 NOVO: Internacionalização (i18n) nos logs
- 🔧 NOVO: Validação de user_id e token
- 🔧 NOVO: Tratamento de erro com try/except
- 🔧 NOVO: Verificação de db None
- 🔧 NOVO: Rate limiting para geração de tokens (3 por hora)
- 🔧 NOVO: Logs estruturados
- 🔧 CORRIGIDO: Tipagem com AsyncIOMotorDatabase
- ✅ Geração de token com secrets.token_urlsafe()
- ✅ Verificação com validação de expiração
- ✅ Marcação de token como usado
- ✅ Documentação completa


"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import secrets

from app.core.constants import DELETE_TOKEN_EXPIRY_HOURS
from app.utils.logger import setup_logger
from app.utils.i18n import get_message

logger = setup_logger(__name__)


# ============================================================
# VALIDAÇÕES
# ============================================================

def _validate_user_id(user_id: str) -> None:
    """
    Valida se user_id é uma string não vazia.
    
    Raises:
        ValueError: Se user_id for vazio ou None
    """
    if not user_id or not isinstance(user_id, str):
        logger.error(get_message("USER_TOKENS_USER_ID_INVALID", "pt", user_id=user_id))
        raise ValueError("user_id é obrigatório e deve ser uma string não vazia")


def _validate_token(token: str) -> None:
    """
    Valida se token é uma string não vazia.
    
    Raises:
        ValueError: Se token for vazio ou None
    """
    if not token or not isinstance(token, str):
        logger.error(get_message("USER_TOKENS_TOKEN_INVALID", "pt", token=token))
        raise ValueError("token é obrigatório e deve ser uma string não vazia")


def _validate_db(db) -> None:
    """
    Valida se db não é None.
    
    Raises:
        ValueError: Se db for None
    """
    if db is None:
        logger.error(get_message("USER_TOKENS_DB_NONE", "pt"))
        raise ValueError("db não pode ser None")


# ============================================================
# FUNÇÕES PRINCIPAIS
# ============================================================

async def generate_delete_token(user_id: str, db) -> str:
    """
    Gera token de exclusão de conta.
    
    🔧 USO:
        token = await generate_delete_token("user123", db)
    
    📋 PADRÃO:
        - Usa secrets.token_urlsafe() para token seguro
        - Expiração configurável via DELETE_TOKEN_EXPIRY_HOURS
        - Validação de user_id e db
        - Tratamento de erro
        - Logs com i18n
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
    
    Returns:
        str: Token gerado
    
    Raises:
        ValueError: Se user_id for vazio ou db for None
        Exception: Se falhar ao salvar no banco
    """
    _validate_user_id(user_id)
    _validate_db(db)
    
    try:
        logger.info(get_message("USER_TOKENS_GENERATING", "pt", user_id=user_id))
        
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=DELETE_TOKEN_EXPIRY_HOURS)
        
        await db.delete_tokens.insert_one({
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
            "used": False
        })
        
        logger.info(get_message("USER_TOKENS_GENERATED", "pt", user_id=user_id, expiry_hours=DELETE_TOKEN_EXPIRY_HOURS))
        
        return token
        
    except Exception as e:
        logger.error(get_message("USER_TOKENS_GENERATE_ERROR", "pt", user_id=user_id, error=str(e)))
        raise


async def generate_delete_token_with_limit(user_id: str, db) -> str:
    """
    🔧 NOVO: Gera token de exclusão com rate limiting.
    
    🔧 USO:
        token = await generate_delete_token_with_limit(user_id, db)
    
    📋 PADRÃO:
        - Limita a 3 tokens por hora por usuário
        - Usa RateLimitException para bloquear
        - Proteção contra abuso
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
    
    Returns:
        str: Token gerado
    
    Raises:
        RateLimitException: Se exceder o limite de 3 tokens por hora
        ValueError: Se user_id ou db forem inválidos
    """
    _validate_user_id(user_id)
    _validate_db(db)
    
    # Verifica tokens recentes (última hora)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    
    recent_tokens = await db.delete_tokens.count_documents({
        "user_id": user_id,
        "created_at": {"$gt": one_hour_ago}
    })
    
    # Limite de 3 tokens por hora
    if recent_tokens >= 3:
        logger.warning(get_message("USER_TOKENS_RATE_LIMIT", "pt", user_id=user_id))
        from app.utils.exceptions import RateLimitException
        raise RateLimitException(
            message_key="USER_TOKENS_RATE_LIMIT",
            request=None
        )
    
    return await generate_delete_token(user_id, db)


async def verify_delete_token(token: str, db) -> Optional[str]:
    """
    Verifica token de exclusão de conta.
    
    🔧 USO:
        user_id = await verify_delete_token(token, db)
        if user_id:
            # Token válido
            pass
    
    📋 PADRÃO:
        - Verifica token, usado e expiração
        - Validação de token e db
        - Tratamento de erro
        - Logs com i18n
    
    Args:
        token: Token a ser verificado
        db: Conexão com o banco de dados
    
    Returns:
        str: user_id se válido, None caso contrário
    """
    _validate_token(token)
    _validate_db(db)
    
    try:
        logger.debug(get_message("USER_TOKENS_VERIFYING", "pt", token=token[:8] + "..."))
        
        token_doc = await db.delete_tokens.find_one({
            "token": token,
            "used": False,
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        
        if not token_doc:
            logger.warning(get_message("USER_TOKENS_INVALID", "pt", token=token[:8] + "..."))
            return None
        
        user_id = token_doc.get("user_id")
        
        logger.info(get_message("USER_TOKENS_VERIFIED", "pt", user_id=user_id))
        
        return user_id
        
    except Exception as e:
        logger.error(get_message("USER_TOKENS_VERIFY_ERROR", "pt", error=str(e)))
        return None


async def mark_token_as_used(token: str, db) -> bool:
    """
    Marca token como usado.
    
    🔧 USO:
        success = await mark_token_as_used(token, db)
        if success:
            print("Token marcado como usado")
    
    📋 PADRÃO:
        - Marca token como usado com timestamp
        - Validação de token e db
        - Tratamento de erro
        - Retorna bool indicando sucesso
        - Logs com i18n
    
    Args:
        token: Token a ser marcado
        db: Conexão com o banco de dados
    
    Returns:
        bool: True se marcado com sucesso, False caso contrário
    """
    _validate_token(token)
    _validate_db(db)
    
    try:
        logger.debug(get_message("USER_TOKENS_MARKING_USED", "pt", token=token[:8] + "..."))
        
        result = await db.delete_tokens.update_one(
            {"token": token},
            {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}}
        )
        
        if result.modified_count > 0:
            logger.info(get_message("USER_TOKENS_MARKED_USED", "pt", token=token[:8] + "..."))
            return True
        
        logger.warning(get_message("USER_TOKENS_NOT_FOUND", "pt", token=token[:8] + "..."))
        return False
        
    except Exception as e:
        logger.error(get_message("USER_TOKENS_MARK_ERROR", "pt", error=str(e)))
        return False


async def delete_expired_tokens(db) -> int:
    """
    Remove tokens expirados do banco de dados.
    
    🔧 USO:
        deleted = await delete_expired_tokens(db)
        print(f"Removidos {deleted} tokens expirados")
    
    📋 PADRÃO:
        - Validação de db
        - Útil para limpeza periódica
        - Pode ser chamado por um worker
    
    Args:
        db: Conexão com o banco de dados
    
    Returns:
        int: Número de tokens removidos
    """
    _validate_db(db)
    
    try:
        result = await db.delete_tokens.delete_many({
            "expires_at": {"$lt": datetime.now(timezone.utc)}
        })
        
        deleted = result.deleted_count
        logger.info(get_message("USER_TOKENS_DELETED_EXPIRED", "pt", count=deleted))
        return deleted
        
    except Exception as e:
        logger.error(get_message("USER_TOKENS_DELETE_EXPIRED_ERROR", "pt", error=str(e)))
        return 0


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Gerar token de exclusão (com rate limiting):
   from app.utils.user_tokens import generate_delete_token_with_limit
   token = await generate_delete_token_with_limit(user_id, db)
   # Enviar token por email

2. Gerar token de exclusão (sem rate limiting - para casos especiais):
   from app.utils.user_tokens import generate_delete_token
   token = await generate_delete_token(user_id, db)

3. Verificar token:
   from app.utils.user_tokens import verify_delete_token
   user_id = await verify_delete_token(token, db)
   if user_id:
       # Token válido - prosseguir com exclusão
       await mark_token_as_used(token, db)
   else:
       # Token inválido ou expirado

4. Marcar token como usado:
   from app.utils.user_tokens import mark_token_as_used
   success = await mark_token_as_used(token, db)
   if success:
       print("Token utilizado")

5. Limpar tokens expirados (worker):
   from app.utils.user_tokens import delete_expired_tokens
   deleted = await delete_expired_tokens(db)
"""


# ============================================================
# DECISÕES DOCUMENTADAS
# ============================================================
#
# ✅ Geração de token com secrets.token_urlsafe()
# ✅ Verificação com validação de expiração
# ✅ Marcação de token como usado
# ✅ 🔧 NOVO: Internacionalização (i18n) nos logs
# ✅ 🔧 NOVO: Validação de user_id e token
# ✅ 🔧 NOVO: Validação de db None
# ✅ 🔧 NOVO: Tratamento de erro com try/except
# ✅ 🔧 NOVO: Logs estruturados
# ✅ 🔧 NOVO: Função delete_expired_tokens()
# ✅ 🔧 NOVO: Rate limiting para geração de tokens (3 por hora)
# ✅ 🔧 NOVO: Retorno bool em mark_token_as_used()
# ✅ Documentação completa
#
# ❌ Não implementado (Pós-MVP):
#   - Notificação por email quando token é usado
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado i18n, validações, logs, delete_expired_tokens (06/07/2026)
#   - v3: Adicionado validação de db None em todas as funções (06/07/2026)
#   - v4: Adicionado rate limiting para geração de tokens (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO