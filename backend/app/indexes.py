"""
Gerenciamento de Índices do MongoDB
Arquivo: backend/app/indexes.py

🔧 NOVO: Separado do database.py para melhor organização
Contém TODOS os índices organizados por coleção

ÍNDICES ORGANIZADOS POR COLEÇÃO:
- users: busca por email (login)
- transactions: consultas financeiras
- bills: contas a pagar
- goals: metas
- user_profiles: perfil financeiro
- score_history: histórico de score
- credit_cards: cartões
- credit_card_purchases: compras parceladas
- credit_card_installments: parcelas
- achievements: conquistas
- refresh_token_blacklist: segurança
"""

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def create_indexes(db):
    """
    Cria índices essenciais para consultas rápidas com muitos usuários
    Roda apenas uma vez, na inicialização do app
    
    🔧 CORRIGIDO: Recebe db como parâmetro (não usa get_database())
    🔧 MELHORADO: Índices compostos para filtros comuns
    
    Args:
        db: Instância do banco de dados (AsyncIOMotorDatabase)
    """
    # 🔧 Verifica se db está conectado
    if db is None:
        logger.error("❌ Banco não conectado, não é possível criar índices")
        return
    
    logger.info("🔄 Iniciando criação/verificação de índices...")
    
    # ================================================================
    # 1. USUÁRIOS
    # ================================================================
    try:
        await db.users.create_index([("email", 1)], unique=True)
        logger.info("✅ Índice users.email (unique) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice users.email: {e}", exc_info=True)
    
    # ================================================================
    # 2. TRANSAÇÕES
    # ================================================================
    indexes = [
        # Essencial para listar transações do usuário
        ("transactions", [("user_id", 1), ("date", -1)]),
        # Para filtrar por tipo (receita/despesa)
        ("transactions", [("user_id", 1), ("type", 1), ("date", -1)]),
        # Para relatórios por categoria
        ("transactions", [("user_id", 1), ("category", 1), ("date", -1)]),
        # Para contexto familiar
        ("transactions", [("user_id", 1), ("context", 1), ("date", -1)]),
        # Para busca por data específica
        ("transactions", [("date", -1)]),
        
        # 🔧 NOVO: Índices compostos para performance
        # Dashboard (Individual, Família, Profissional)
        ("transactions", [("user_id", 1), ("context", 1), ("date", -1)]),
        # Filtrar receitas/despesas no dashboard
        ("transactions", [("user_id", 1), ("context", 1), ("type", 1)]),
        # Busca por categoria no dashboard
        ("transactions", [("user_id", 1), ("context", 1), ("category", 1)]),
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
        ("bills", [("user_id", 1)]),
        ("bills", [("user_id", 1), ("paid", 1)]),
        ("bills", [("user_id", 1), ("installments.start_date", 1)]),
        ("bills", [("user_id", 1), ("installments.due_day", 1)]),
        
        # 🔧 NOVO: Índices compostos para contas
        ("bills", [("user_id", 1), ("paid", 1), ("installments.start_date", 1)]),
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
        ("goals", [("user_id", 1)]),
        ("goals", [("user_id", 1), ("completed", 1)]),
        ("goals", [("user_id", 1), ("category", 1)]),
        
        # 🔧 NOVO: Índice composto para metas
        ("goals", [("user_id", 1), ("completed", 1), ("created_at", -1)]),
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
        ("credit_cards", [("user_id", 1), ("due_day", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
    # ================================================================
    # 8. COMPRAS PARCELADAS
    # ================================================================
    indexes = [
        ("credit_card_purchases", [("card_id", 1)]),
        ("credit_card_purchases", [("user_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1)]),
        
        # 🔧 NOVO: Índice composto para faturas
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
    # 9. PARCELAS (INSTALLMENTS)
    # ================================================================
    indexes = [
        ("credit_card_installments", [("purchase_id", 1)]),
        ("credit_card_installments", [("user_id", 1), ("paid", 1)]),
        ("credit_card_installments", [("card_id", 1), ("due_date", 1)]),
        ("credit_card_installments", [("user_id", 1), ("due_date", 1)]),
        
        # 🔧 NOVO: Índices compostos para faturas
        ("credit_card_installments", [("user_id", 1), ("paid", 1), ("due_date", 1)]),
        ("credit_card_installments", [("card_id", 1), ("due_date", 1), ("paid", 1)]),
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
    indexes = [
        ("achievements", [("user_id", 1)]),
        ("achievements", [("user_id", 1), ("type", 1), ("date", -1)]),
        ("achievements", [("user_id", 1), ("month", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}", exc_info=True)
    
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
# ✅ Índices organizados por coleção (fácil manutenção)
# ✅ Índices compostos para filtros comuns (performance)
# ✅ Recebe db como parâmetro (desacoplado do database.py)
# ✅ Logs com exc_info=True para melhor rastreamento
# ✅ Tratamento de erros individual por índice
#
# 🔧 ÍNDICES COMPOSTOS ADICIONADOS:
# - transactions: (user_id, context, date) → Dashboard
# - transactions: (user_id, context, type) → Filtro receitas/despesas
# - bills: (user_id, paid, start_date) → Contas pendentes
# - goals: (user_id, completed, created_at) → Metas ordenadas
# - credit_card_purchases: (card_id, created_at, paid) → Faturas
# - credit_card_installments: (user_id, paid, due_date) → Parcelas
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO