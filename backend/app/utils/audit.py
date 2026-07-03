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
"""

from datetime import datetime, timezone, timedelta
from bson import ObjectId
from typing import Optional, Dict, Any

from app.core.constants import MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def add_audit_history(
    collection,
    doc_id: str,
    action: str,
    user_id: str,
    details: Dict[str, Any],
    history_field: str = "history"
) -> None:
    """
    Adiciona entrada no histórico de auditoria de qualquer documento.
    
    Args:
        collection: Coleção do MongoDB
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
            db.credit_cards,
            card_id,
            "create",
            str(current_user.id),
            {"name": "Nubank"},
            history_field="history"
        )
    """
    # ========== Validações ==========
    if collection is None:
        logger.error("❌ Collection não pode ser None em add_audit_history")
        return
    
    if not doc_id:
        logger.error("❌ doc_id não pode ser vazio em add_audit_history")
        return
    
    try:
        ObjectId(doc_id)
    except Exception as e:
        logger.error(f"❌ doc_id inválido em add_audit_history: {doc_id} - {e}")
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
        logger.error(f"❌ Erro ao adicionar histórico de auditoria: {e}")


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
    🆕 Adiciona entrada no log de auditoria da IA.
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
    log_entry = {
        "user_id": user_id,
        "action": action,
        "details": details,
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.ia_audit_logs.insert_one(log_entry)
    return str(result.inserted_id)


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
# ✅ 🔧 CORRIGIDO: history_field agora é usado corretamente
# ✅ 🔧 CORRIGIDO: add_limit_history agora existe no módulo
# ✅ 🆕 add_audit_log adicionado para IA
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO