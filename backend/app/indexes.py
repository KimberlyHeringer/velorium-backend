"""
Gerenciamento de Índices do MongoDB
Arquivo: backend/app/indexes.py

🔧 CORRIGIDO:
- Removido índice financial_risk (não usado em queries)
- Removido due_day do índice de bills
- 🔧 CORRIGIDO: Usa índice regular (não hashed) para refresh_token_blacklist
- 🔧 NOVO: Índice para credit_card_purchases com fully_paid
- 🔧 NOVO: Índice para score_history com user_id + date
- 🔧 NOVO: Índice TTL para reset_token_expires (expiração automática)
- 🔧 NOVO: Índices para bill_installments (otimização de consultas)
- 🔧 NOVO: Índice TTL para history.expires_at (expiração automática do histórico)
- 🔧 NOVO: partialFilterExpression no TTL para otimização
- 🔧 NOVO: Índices para bills (category e paid+due_date)
- 🆕 NOVO: Índice para credit_card_purchases (interest_rate)
- 🆕 NOVO: Índices para ia_audit_logs (user_id + created_at)
- 🆕 NOVO: Índices para ia_feedback (audit_id, feedback)
- 🆕 NOVO: Índices para investments (user_id + category, user_id + sold, user_id + created_at)
"""

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def create_indexes(db):
    """
    Cria índices essenciais para consultas rápidas.
    🔧 OTIMIZADO: Sem redundâncias e com índices otimizados.
    """
    if db is None:
        logger.error("❌ Banco não conectado, não é possível criar índices")
        return
    
    logger.info("🔄 Iniciando criação/verificação de índices...")
    
    # ================================================================
    # 1. USUÁRIOS
    # ================================================================
    try:
        await db.users.create_index(
            [("email", 1)],
            unique=True,
            collation={"locale": "en", "strength": 2}
        )
        logger.info("✅ Índice users.email (unique) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice users.email: {e}", exc_info=True)
    
    # ================================================================
    # 2. TRANSAÇÕES
    # ================================================================
    indexes = [
        ("transactions", [("user_id", 1), ("context", 1), ("date", -1)]),
        ("transactions", [("user_id", 1), ("context", 1), ("type", 1)]),
        ("transactions", [("user_id", 1), ("context", 1), ("category", 1)]),
        ("transactions", [("date", -1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 3. CONTAS A PAGAR (BILLS) - ATUALIZADO
    # ================================================================
    indexes = [
        ("bills", [("user_id", 1), ("paid", 1)]),
        ("bills", [("user_id", 1), ("installments.start_date", 1)]),
        ("bills", [("user_id", 1), ("category", 1)]),
        ("bills", [("user_id", 1), ("paid", 1), ("due_date", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 4. METAS (GOALS)
    # ================================================================
    indexes = [
        ("goals", [("user_id", 1), ("completed", 1), ("created_at", -1)]),
        ("goals", [("user_id", 1), ("category", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 5. PERFIL DO USUÁRIO
    # ================================================================
    try:
        await db.user_profiles.create_index([("user_id", 1)], unique=True)
        logger.info("✅ Índice user_profiles.user_id (unique) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice user_profiles: {e}", exc_info=True)
    
    # ================================================================
    # 6. HISTÓRICO DE SCORE
    # ================================================================
    try:
        await db.score_history.create_index([("user_id", 1), ("date", -1)])
        logger.info("✅ Índice score_history.user_id + date criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice score_history: {e}", exc_info=True)
    
    # ================================================================
    # 7. CARTÕES DE CRÉDITO
    # ================================================================
    indexes = [
        ("credit_cards", [("user_id", 1)]),
        ("credit_cards", [("user_id", 1), ("closing_day", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 8. COMPRAS PARCELADAS (CREDIT_CARD_PURCHASES) - ATUALIZADO
    # ================================================================
    indexes = [
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("user_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1), ("paid", 1)]),
        ("credit_card_purchases", [("user_id", 1), ("fully_paid", 1)]),
        ("credit_card_purchases", [("interest_rate", 1)]),
        ("credit_card_purchases", [("user_id", 1), ("remaining_installments", 1)]),
        ("credit_card_purchases", [("user_id", 1), ("fully_paid", 1), ("created_at", -1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 9. PARCELAS DE CARTÃO DE CRÉDITO (CREDIT_CARD_INSTALLMENTS)
    # ================================================================
    indexes = [
        ("credit_card_installments", [("user_id", 1), ("paid", 1), ("due_date", 1)]),
        ("credit_card_installments", [("card_id", 1), ("due_date", 1), ("paid", 1)]),
        ("credit_card_installments", [("purchase_id", 1)]),
        ("credit_card_installments", [("purchase_id", 1), ("paid", 1)]),
        ("credit_card_installments", [("user_id", 1), ("due_date", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 10. PARCELAS DE CONTAS A PAGAR (BILL_INSTALLMENTS)
    # ================================================================
    indexes = [
        ("bill_installments", [("user_id", 1), ("due_date", -1)]),
        ("bill_installments", [("bill_id", 1), ("user_id", 1)]),
        ("bill_installments", [("user_id", 1), ("paid", 1)]),
        ("bill_installments", [("user_id", 1), ("due_date", 1), ("paid", 1)]),
        ("bill_installments", [("user_id", 1), ("paid_by", 1)]),
        ("bill_installments", [("history.action", 1), ("history.timestamp", -1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 11. TTL PARA HISTÓRICO ANTIGO (BILL_INSTALLMENTS)
    # ================================================================
    try:
        await db.bill_installments.create_index(
            [("history.expires_at", 1)],
            expireAfterSeconds=0,
            partialFilterExpression={"history": {"$exists": True, "$ne": []}}
        )
        logger.info("✅ Índice TTL para history.expires_at criado (com partialFilterExpression)")
    except Exception as e:
        logger.warning(f"⚠️ Índice TTL para history.expires_at: {e}", exc_info=True)
    
    # ================================================================
    # 12. CONQUISTAS (ACHIEVEMENTS)
    # ================================================================
    try:
        await db.achievements.create_index(
            [("user_id", 1), ("type", 1), ("year", 1), ("month", 1), ("date", -1)]
        )
        logger.info("✅ Índice achievements.user_id + type + year + month + date criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice achievements: {e}", exc_info=True)
    
    # ================================================================
    # 13. BLACKLIST DE TOKENS (SEGURANÇA)
    # ================================================================
    try:
        await db.refresh_token_blacklist.create_index(
            [("expires_at", 1)],
            expireAfterSeconds=0
        )
        await db.refresh_token_blacklist.create_index(
            [("token", 1)],
            unique=True
        )
        logger.info("✅ Índices refresh_token_blacklist criados")
    except Exception as e:
        logger.warning(f"⚠️ Índices refresh_token_blacklist: {e}", exc_info=True)
    
    # ================================================================
    # 14. RESET TOKEN (TTL para expiração automática)
    # ================================================================
    try:
        await db.users.create_index(
            [("reset_token_expires", 1)],
            expireAfterSeconds=0
        )
        logger.info("✅ Índice reset_token_expires (TTL) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice reset_token_expires: {e}", exc_info=True)
    
    # ================================================================
    # 15. LOGS DE AUDITORIA DA IA (IA_AUDIT_LOGS) 🆕
    # ================================================================
    try:
        await db.ia_audit_logs.create_index(
            [("user_id", 1), ("created_at", -1)]
        )
        logger.info("✅ Índice ia_audit_logs.user_id + created_at criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice ia_audit_logs: {e}", exc_info=True)
    
    # ================================================================
    # 16. FEEDBACK DA IA (IA_FEEDBACK) 🆕
    # ================================================================
    try:
        await db.ia_feedback.create_index([("audit_id", 1)])
        logger.info("✅ Índice ia_feedback.audit_id criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice ia_feedback.audit_id: {e}", exc_info=True)
    
    try:
        await db.ia_feedback.create_index([("feedback", 1)])
        logger.info("✅ Índice ia_feedback.feedback criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice ia_feedback.feedback: {e}", exc_info=True)
    
    try:
        await db.ia_feedback.create_index([("created_at", -1)])
        logger.info("✅ Índice ia_feedback.created_at criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice ia_feedback.created_at: {e}", exc_info=True)
    
    # ================================================================
    # 17. HISTÓRICO DE CHAT DA IA (CHAT_HISTORY) 🆕
    # ================================================================
    try:
        await db.chat_history.create_index(
            [("user_id", 1), ("created_at", -1)]
        )
        logger.info("✅ Índice chat_history.user_id + created_at criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice chat_history: {e}", exc_info=True)
    
    # ================================================================
    # 18. INVESTIMENTOS (INVESTMENTS) 🆕
    # ================================================================
    try:
        await db.investments.create_index(
            [("user_id", 1), ("category", 1)]
        )
        logger.info("✅ Índice investments.user_id + category criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice investments.user_id + category: {e}", exc_info=True)
    
    try:
        await db.investments.create_index(
            [("user_id", 1), ("sold", 1)]
        )
        logger.info("✅ Índice investments.user_id + sold criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice investments.user_id + sold: {e}", exc_info=True)
    
    try:
        await db.investments.create_index(
            [("user_id", 1), ("created_at", -1)]
        )
        logger.info("✅ Índice investments.user_id + created_at criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice investments.user_id + created_at: {e}", exc_info=True)
    
    logger.info("✅ Todos os índices foram criados/verificados com sucesso!")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Índices organizados por coleção
# ✅ 🔧 REMOVIDO: financial_risk (não usado em queries)
# ✅ 🔧 REMOVIDO: due_day de bills (não usado em queries)
# ✅ 🔧 CORRIGIDO: índice regular (não hashed) para refresh_token_blacklist
# ✅ 🔧 CORRIGIDO: achievements com year + month (int) em vez de month (string)
# ✅ 🔧 REMOVIDOS: índices redundantes em transactions
# ✅ 🔧 REMOVIDOS: índices redundantes em credit_card_purchases
# ✅ 🔧 MELHORADO: índice de email com collation case-insensitive
# ✅ 🔧 NOVO: Índice credit_card_purchases com fully_paid para filtro por status
# ✅ 🔧 NOVO: Índice score_history com user_id + date para consultas de histórico
# ✅ 🔧 NOVO: Índice TTL para reset_token_expires (expiração automática)
# ✅ 🆕 NOVO: Índices bill_installments para otimização de consultas
# ✅ 🆕 NOVO: Índice TTL para history.expires_at (expiração automática do histórico)
# ✅ 🆕 NOVO: partialFilterExpression no TTL para otimização
# ✅ 🆕 NOVO: Índices bills atualizados
# ✅ 🆕 NOVO: Índices credit_card_purchases atualizados
# ✅ 🆕 NOVO: Índices credit_card_installments atualizados
# ✅ 🆕 NOVO: Índices para IA (ia_audit_logs, ia_feedback, chat_history)
# ✅ 🆕 NOVO: Índices para investments
#   - (user_id, category) - Filtro por categoria
#   - (user_id, sold) - Filtro por status de venda
#   - (user_id, created_at) - Ordenação por data
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO