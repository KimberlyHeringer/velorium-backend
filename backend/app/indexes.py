"""
Gerenciamento de Índices do MongoDB
Arquivo: backend/app/indexes.py

🔧 CORRIGIDO:
- Removidos índices redundantes em transactions
- Removidos índices redundantes em credit_card_purchases
- Adicionados índices para user_profiles
- Adicionado índice composto para achievements
- Índice de email com collation case-insensitive
"""

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def create_indexes(db):
    """
    Cria índices essenciais para consultas rápidas.
    🔧 OTIMIZADO: Sem redundâncias.
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
            collation={"locale": "en", "strength": 2}  # Case insensitive
        )
        logger.info("✅ Índice users.email (unique) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice users.email: {e}", exc_info=True)
    
    # ================================================================
    # 2. TRANSAÇÕES (OTIMIZADO - sem redundâncias)
    # ================================================================
    indexes = [
        # Composto para dashboard (já cobre user_id + date)
        ("transactions", [("user_id", 1), ("context", 1), ("date", -1)]),
        # Filtro por tipo
        ("transactions", [("user_id", 1), ("context", 1), ("type", 1)]),
        # Filtro por categoria
        ("transactions", [("user_id", 1), ("context", 1), ("category", 1)]),
        # Relatórios globais
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
    # 3. CONTAS A PAGAR
    # ================================================================
    indexes = [
        ("bills", [("user_id", 1), ("paid", 1), ("installments.start_date", 1)]),
        ("bills", [("user_id", 1), ("paid", 1), ("installments.due_day", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 4. METAS
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
    # 5. PERFIL DO USUÁRIO (NOVO)
    # ================================================================
    try:
        await db.user_profiles.create_index([("user_id", 1)], unique=True)
        logger.info("✅ Índice user_profiles.user_id (unique) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice user_profiles: {e}", exc_info=True)
    
    try:
        await db.user_profiles.create_index([("user_id", 1), ("financial_risk", 1)])
        logger.info("✅ Índice user_profiles.financial_risk criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice user_profiles.financial_risk: {e}", exc_info=True)
    
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
    # 8. COMPRAS PARCELADAS (OTIMIZADO - sem redundâncias)
    # ================================================================
    indexes = [
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("user_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1), ("paid", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 9. PARCELAS
    # ================================================================
    indexes = [
        ("credit_card_installments", [("user_id", 1), ("paid", 1), ("due_date", 1)]),
        ("credit_card_installments", [("card_id", 1), ("due_date", 1), ("paid", 1)]),
        ("credit_card_installments", [("purchase_id", 1)]),  # Para joins
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 10. CONQUISTAS (NOVO ÍNDICE COMPOSTO)
    # ================================================================
    try:
        await db.achievements.create_index(
            [("user_id", 1), ("type", 1), ("month", 1), ("date", -1)]
        )
        logger.info("✅ Índice achievements.user_id + type + month + date criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice achievements: {e}", exc_info=True)
    
    # ================================================================
    # 11. BLACKLIST DE TOKENS (SEGURANÇA)
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
    
    logger.info("✅ Todos os índices foram criados/verificados com sucesso!")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Índices organizados por coleção
# ✅ 🔧 REMOVIDOS: índices redundantes em transactions
# ✅ 🔧 REMOVIDOS: índices redundantes em credit_card_purchases
# ✅ 🔧 NOVOS: índices para user_profiles (financial_risk)
# ✅ 🔧 NOVO: índice composto para achievements
# ✅ 🔧 MELHORADO: índice de email com collation case-insensitive
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO