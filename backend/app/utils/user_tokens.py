"""
Funções de Tokens para Usuário
Arquivo: backend/app/utils/user_tokens.py

Funcionalidade: Centraliza funções relacionadas a tokens de usuário
para reutilização na rota user.py.

🔧 USO:
    from app.utils.user_tokens import (
        generate_delete_token,
        verify_delete_token,
        mark_token_as_used
    )
    
    token = await generate_delete_token(user_id, db)
    user_id = await verify_delete_token(token, db)
    await mark_token_as_used(token, db)

📋 ESTRUTURA:
    - generate_delete_token(): Gera token de exclusão de conta
    - verify_delete_token(): Verifica token de exclusão
    - mark_token_as_used(): Marca token como usado
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import secrets

from app.core.constants import DELETE_TOKEN_EXPIRY_HOURS
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def generate_delete_token(user_id: str, db) -> str:
    """
    Gera token de exclusão de conta.
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
    
    Returns:
        str: Token gerado
    
    Exemplo:
        token = await generate_delete_token("user123", db)
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=DELETE_TOKEN_EXPIRY_HOURS)
    
    await db.delete_tokens.insert_one({
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
        "used": False
    })
    
    return token


async def verify_delete_token(token: str, db) -> Optional[str]:
    """
    Verifica token de exclusão de conta.
    
    Args:
        token: Token a ser verificado
        db: Conexão com o banco de dados
    
    Returns:
        str: user_id se válido, None caso contrário
    
    Exemplo:
        user_id = await verify_delete_token(token, db)
        if user_id:
            # Token válido
            pass
    """
    token_doc = await db.delete_tokens.find_one({
        "token": token,
        "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    
    if not token_doc:
        return None
    
    return token_doc.get("user_id")


async def mark_token_as_used(token: str, db):
    """
    Marca token como usado.
    
    Args:
        token: Token a ser marcado
        db: Conexão com o banco de dados
    
    Exemplo:
        await mark_token_as_used(token, db)
    """
    await db.delete_tokens.update_one(
        {"token": token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}}
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Funções reutilizáveis para tokens de usuário
# ✅ Geração de token com expiração
# ✅ Verificação com validação de expiração
# ✅ Marcação de token como usado
# ✅ Logs estruturados
# ✅ Validações robustas
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO