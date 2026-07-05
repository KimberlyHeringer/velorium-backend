"""
Funções de Auditoria para todas as rotas
Arquivo: backend/app/utils/audit.py

Funcionalidade: Centraliza a lógica de auditoria para reutilização
em todas as rotas do sistema.

🔧 USO:
    from app.utils.audit import add_audit_history, add_limit_history, add_audit_log
    
    await add_audit_history(
        db.bills,
        bill_id,
        "update",
        str(current_user.id),
        {"changes": update_data}
    )
    
    await add_limit_history(
        db,
        card_id,
        str(current_user.id),
        old_limit,
        new_limit,
        "Atualização manual"
    )
    
    audit_id = await add_audit_log(
        db,
        str(current_user.id),
        "chat",
        {"question": chat_request.pergunta}
    )

📋 ESTRUTURA:
    - add_audit_history(): Função genérica para adicionar histórico (qualquer coleção)
    - add_limit_history(): Função específica para histórico de limites (cartões)
    - add_audit_log(): Função para logs de auditoria da IA (ia_audit_logs)

🔧 CARACTERÍSTICAS:
    - Suporte a qualquer coleção
    - Campo de histórico customizável (history_field)
    - TTL automático
    - Limite de entradas (MAX_HISTORY_ENTRIES)
    - Validações robustas
    - 🔧 CORRIGIDO: Suporte a collection como string
    - 🔧 CORRIGIDO: Verificação db.credit_cards
    - 🔧 CORRIGIDO: Validação de user_id
    - 🔧 CORRIGIDO: Verificação db is None
    - 🔧 CORRIGIDO: i18n nos logs
"""

from datetime import datetime, timezone, timedelta
from bson import ObjectId
from typing import Optional, Dict, Any, Union

from app.core.constants import MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS
from app.utils.logger import setup_logger
from app.utils.i18n import get_message

logger = setup_logger(__name__)


async def add_audit_history(
    collection: Union[str, Any],
    doc_id: str,
    action: str,
    user_id: str,
    details: Dict[str, Any],
    history_field: str = "history"
) -> None:
    """
    Adiciona entrada no histórico de auditoria de qualquer documento.
    
    Args:
        collection: Coleção do MongoDB (objeto ou nome da coleção como string)
        doc_id: ID do documento
        action: Ação realizada (create, update, delete, pay, unpay, etc.)
        user_id: ID do usuário que realizou a ação
        details: Detalhes adicionais da ação
        history_field: Nome do campo de histórico (padrão: "history")
    
    Raises:
        Exception: Se ocorrer erro ao salvar no banco (apenas loga)
    
    Exemplo:
        await add_audit_history(
            db.bills,
            bill_id,
            "update",
            str(current_user.id),
            {"changes": update_data}
        )
        
        await add_audit_history(
            "credit_cards",  # ← Suporte a string
            card_id,
            "create",
            str(current_user.id),
            {"name": "Nubank"},
            history_field="history"
        )
    """
    # ========== Validações ==========
    
    # 🔧 CORRIGIDO: Se collection for string, busca a coleção
    if isinstance(collection, str):
        from app.database import get_database
        db = get_database()
        collection = db[collection]
    
    if collection is None:
        logger.error(f"❌ {get_message('AUDIT_COLLECTION_NONE', 'pt')}")
        return
    
    if not doc_id:
        logger.error(f"❌ {get_message('AUDIT_DOC_ID_EMPTY', 'pt')}")
        return
    
    try:
        ObjectId(doc_id)
    except Exception as e:
        logger.error(f"❌ {get_message('AUDIT_DOC_ID_INVALID', 'pt')}: {doc_id} - {e}")
        return
    
    if not user_id:
        logger.error(f"❌ {get_message('AUDIT_USER_ID_EMPTY', 'pt')}")
        return
    
    try:
        ObjectId(user_id)
    except Exception as e:
        logger.error(f"❌ {get_message('AUDIT_USER_ID_INVALID', 'pt')}: {user_id} - {e}")
        return
    
    if not details:
        details = {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    # ========== Cria entrada ==========
    try:
        expires_at = datetime.now(timezone.utc) + timedelta(days=HISTORY_TTL_DAYS)
        
        history_entry = {
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "details": details
        }
        
        # ========== Atualiza documento ==========
        await collection.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$push": {
                    history_field: {
                        "$each": [history_entry],
                        "$slice": -MAX_HISTORY_ENTRIES
                    }
                }
            }
        )
    except Exception as e:
        logger.error(f"❌ {get_message('AUDIT_ERROR_SAVING', 'pt')}: {e}")


async def add_limit_history(
    db,
    card_id: str,
    user_id: str,
    old_limit: int,
    new_limit: int,
    reason: str = None
) -> None:
    """
    Adiciona entrada específica no histórico de alterações de limite de cartão.
    
    Args:
        db: Conexão com o banco de dados
        card_id: ID do cartão
        user_id: ID do usuário
        old_limit: Limite antigo (em centavos)
        new_limit: Limite novo (em centavos)
        reason: Motivo da alteração
    
    Exemplo:
        await add_limit_history(
            db,
            card_id,
            str(current_user.id),
            old_limit,
            new_limit,
            "Atualização manual"
        )
    """
    # 🔧 CORRIGIDO: Verifica se db é None
    if db is None:
        logger.error(f"❌ {get_message('AUDIT_DB_NONE', 'pt')}")
        return
    
    # 🔧 CORRIGIDO: Verifica se a coleção credit_cards existe
    if not hasattr(db, "credit_cards"):
        logger.error(f"❌ Coleção credit_cards não encontrada")
        return
    
    details = {
        "old_limit": old_limit,
        "new_limit": new_limit,
        "reason": reason or "Atualização manual"
    }
    
    await add_audit_history(
        db.credit_cards,
        card_id,
        "limit_change",
        user_id,
        details,
        history_field="history"
    )
    
    logger.info(f"📊 Histórico de limite: {card_id} - {old_limit} → {new_limit}")


async def add_audit_log(
    db,
    user_id: str,
    action: str,
    details: dict
) -> str:
    """
    Adiciona entrada no log de auditoria da IA.
    Retorna o ID do log para referência.
    
    Args:
        db: Conexão com o banco de dados
        user_id: ID do usuário
        action: Ação realizada (chat, extract_text, etc.)
        details: Detalhes adicionais da ação
    
    Returns:
        str: ID do log de auditoria
    
    Exemplo:
        audit_id = await add_audit_log(
            db,
            str(current_user.id),
            "chat",
            {"question": chat_request.pergunta}
        )
    """
    # 🔧 CORRIGIDO: Verificação db is None
    if db is None:
        logger.error(f"❌ {get_message('AUDIT_DB_NONE', 'pt')}")
        return ""
    
    # 🔧 CORRIGIDO: Validação de user_id
    if not user_id:
        logger.error(f"❌ {get_message('AUDIT_USER_ID_EMPTY', 'pt')}")
        return ""
    
    try:
        ObjectId(user_id)
    except Exception as e:
        logger.error(f"❌ {get_message('AUDIT_USER_ID_INVALID', 'pt')}: {user_id} - {e}")
        return ""
    
    if not details:
        details = {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    try:
        log_entry = {
            "user_id": user_id,
            "action": action,
            "details": details,
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await db.ia_audit_logs.insert_one(log_entry)
        logger.debug(f"📝 Log de auditoria adicionado: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"❌ {get_message('AUDIT_ERROR_SAVING', 'pt')}: {e}")
        return ""


# ========== FUNÇÕES AUXILIARES (PÓS-MVP) ==========

async def get_audit_history(
    db,
    doc_id: str,
    collection_name: str,
    page: int = 1,
    limit: int = 20
) -> list:
    """
    🔧 Pós-MVP: Busca histórico com paginação.
    
    Args:
        db: Conexão com o banco de dados
        doc_id: ID do documento
        collection_name: Nome da coleção
        page: Número da página
        limit: Itens por página
    
    Returns:
        list: Histórico paginado
    """
    collection = db[collection_name]
    doc = await collection.find_one({"_id": ObjectId(doc_id)})
    if not doc:
        return []
    
    history = doc.get("history", [])
    start = (page - 1) * limit
    end = start + limit
    return history[start:end]


async def get_audit_history_by_action(
    db,
    doc_id: str,
    collection_name: str,
    action: str
) -> list:
    """
    🔧 Pós-MVP: Busca histórico filtrado por ação.
    
    Args:
        db: Conexão com o banco de dados
        doc_id: ID do documento
        collection_name: Nome da coleção
        action: Ação a filtrar
    
    Returns:
        list: Histórico filtrado
    """
    collection = db[collection_name]
    doc = await collection.find_one({"_id": ObjectId(doc_id)})
    if not doc:
        return []
    
    history = doc.get("history", [])
    return [h for h in history if h.get("action") == action]


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Função genérica para qualquer coleção
# ✅ Campo de histórico customizável (history_field)
# ✅ TTL automático (expiração)
# ✅ Limite de entradas (evita 16MB)
# ✅ Validações robustas (collection, doc_id, details)
# ✅ Logs estruturados
# ✅ Função específica para limite de cartões (add_limit_history)
# ✅ Função específica para IA (add_audit_log)
# ✅ 🔧 CORRIGIDO: Suporte a collection como string
# ✅ 🔧 CORRIGIDO: Verificação db.credit_cards
# ✅ 🔧 CORRIGIDO: Validação de user_id
# ✅ 🔧 CORRIGIDO: Verificação db is None
# ✅ 🔧 CORRIGIDO: i18n nos logs
# ✅ 🔧 CORRIGIDO: add_audit_log com validações
# ✅ 🆕 Função get_audit_history (pós-MVP)
# ✅ 🆕 Função get_audit_history_by_action (pós-MVP)
#
# ❌ Não implementado (Pós-MVP):
#   - Buscar histórico paginado
#   - Buscar histórico por ação
#   - Filtrar histórico por data
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração com validações, i18n, db None (04/07/2026)
#   - v3: Correções - collection como string, db.credit_cards (04/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO