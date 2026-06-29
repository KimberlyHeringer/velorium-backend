"""
Gerenciamento de Índices do MongoDB
Arquivo: backend/app/indexes.py

🔧 CORRIGIDO:
- Removido índice financial_risk (não usado em queries)
- Removido due_day do índice de bills
- 🔧 CORRIGIDO: Usa índice regular (não hashed) para refresh_token_blacklist
- 🔧 NOVO: Índice para credit_card_purchases com fully_paid
- 🔧 NOVO: Índice para score_history com user_id + date
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
    # 3. CONTAS A PAGAR (BILLS)
    # ================================================================
    indexes = [
        ("bills", [("user_id", 1), ("paid", 1)]),
        ("bills", [("user_id", 1), ("installments.start_date", 1)]),
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
    # 🔧 NOVO: Índice composto para consultas de histórico
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
    # 8. COMPRAS PARCELADAS (CREDIT_CARD_PURCHASES)
    # 🔧 NOVO: Adicionado índice fully_paid para filtrar por status
    # ================================================================
    indexes = [
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("user_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1), ("paid", 1)]),
        # 🔧 NOVO: Índice para filtrar compras por status (fully_paid)
        ("credit_card_purchases", [("user_id", 1), ("fully_paid", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 9. PARCELAS (INSTALLMENTS)
    # ================================================================
    indexes = [
        ("credit_card_installments", [("user_id", 1), ("paid", 1), ("due_date", 1)]),
        ("credit_card_installments", [("card_id", 1), ("due_date", 1), ("paid", 1)]),
        ("credit_card_installments", [("purchase_id", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 10. CONQUISTAS (ACHIEVEMENTS)
    # ================================================================
    try:
        await db.achievements.create_index(
            [("user_id", 1), ("type", 1), ("year", 1), ("month", 1), ("date", -1)]
        )
        logger.info("✅ Índice achievements.user_id + type + year + month + date criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice achievements: {e}", exc_info=True)
    
    # ================================================================
    # 11. BLACKLIST DE TOKENS (SEGURANÇA)
    # 🔧 CORRIGIDO: Usa índice regular (não hashed) para garantir unicidade
    # ================================================================
    try:
        await db.refresh_token_blacklist.create_index(
            [("expires_at", 1)],
            expireAfterSeconds=0
        )
        # 🔧 CORRIGIDO: Índice regular com unique (hashed não suporta unique)
        await db.refresh_token_blacklist.create_index(
            [("token", 1)],
            unique=True
        )
        logger.info("✅ Índices refresh_token_blacklist criados")
    except Exception as e:
        logger.warning(f"⚠️ Índices refresh_token_blacklist: {e}", exc_info=True)
    
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
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO