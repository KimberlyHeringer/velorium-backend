"""
Configuração da conexão com MongoDB
Arquivo: backend/app/database.py

🔧 MODIFICADO: Regra 2.8 - Logs
- Substituído print por logger.info/error/warning
- Adicionado logger configurado
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Any
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException
import certifi

from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# Carrega variáveis de ambiente do arquivo .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Obtém as credenciais do ambiente
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "velorium_db")

# Validação: se não tiver URI, o app nem sobe (segurança)
if not MONGO_URI:
    raise ValueError("MONGO_URI nao encontrada no .env!")

# Variáveis globais para armazenar o cliente e o banco
client: Optional[AsyncIOMotorClient] = None
db: Any = None


async def connect_to_mongo():
    """
    Estabelece conexão com o MongoDB Atlas
    Executada na inicialização do app (startup event)
    """
    global client, db
    try:
        client = AsyncIOMotorClient(
            MONGO_URI,
            maxPoolSize=50,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            retryWrites=True,
            w="majority",
            tls=True,
            tlsCAFile=certifi.where()
        )
        
        # Verifica se a conexão está funcionando
        await client.admin.command('ping')
        db = client[DATABASE_NAME]
        logger.info(f"✅ Conectado ao MongoDB: {DATABASE_NAME}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao MongoDB: {e}")
        raise HTTPException(status_code=503, detail="Banco de dados indisponível")


async def close_mongo_connection():
    """
    Fecha a conexão com o MongoDB
    Executada no desligamento do app (shutdown event)
    """
    global client, db
    if client:
        client.close()
        db = None
        logger.info("✅ Conexão com MongoDB fechada")


def get_database():
    """
    Retorna a instância do banco de dados
    Usada pelos routers que precisam acessar o MongoDB
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Banco de dados não conectado")
    return db


async def health_check() -> dict:
    """
    Verifica se o banco está saudável
    Usado pelo endpoint /health para monitoramento
    """
    try:
        if client is None:
            return {"status": "disconnected"}
        await client.admin.command('ping')
        return {"status": "healthy", "database": DATABASE_NAME}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# ========== ÍNDICES PARA PERFORMANCE ==========
async def create_indexes():
    """
    Cria índices essenciais para consultas rápidas com muitos usuários
    Roda apenas uma vez, na inicialização do app
    
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
    db = get_database()
    
    # ========== USUÁRIOS ==========
    # 🔴 CRÍTICO: garantir que emails são únicos
    try:
        await db.users.create_index([("email", 1)], unique=True)
        logger.info("✅ Índice users.email (unique) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice users.email: {e}")
    
    # ========== TRANSAÇÕES ==========
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
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}")
    
    # ========== CONTAS A PAGAR (BILLS) ==========
    indexes = [
        ("bills", [("user_id", 1)]),
        ("bills", [("user_id", 1), ("paid", 1)]),
        ("bills", [("user_id", 1), ("installments.start_date", 1)]),
        ("bills", [("user_id", 1), ("installments.due_day", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}")
    
    # ========== METAS (GOALS) ==========
    indexes = [
        ("goals", [("user_id", 1)]),
        ("goals", [("user_id", 1), ("completed", 1)]),
        ("goals", [("user_id", 1), ("category", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}")
    
    # ========== PERFIL DO USUÁRIO ==========
    try:
        await db.user_profiles.create_index([("user_id", 1)], unique=True)
        logger.info("✅ Índice user_profiles.user_id (unique) criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice user_profiles: {e}")
    
    # ========== HISTÓRICO DE SCORE ==========
    try:
        await db.score_history.create_index([("user_id", 1), ("date", -1)])
        logger.info("✅ Índice score_history.user_id + date criado")
    except Exception as e:
        logger.warning(f"⚠️ Índice score_history: {e}")
    
    # ========== CARTÕES DE CRÉDITO ==========
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
            logger.warning(f"⚠️ Índice em {collection_name}: {e}")
    
    # ========== COMPRAS PARCELADAS ==========
    indexes = [
        ("credit_card_purchases", [("card_id", 1)]),
        ("credit_card_purchases", [("user_id", 1), ("created_at", -1)]),
        ("credit_card_purchases", [("card_id", 1), ("created_at", -1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}")
    
    # ========== PARCELAS (INSTALLMENTS) ==========
    indexes = [
        ("credit_card_installments", [("purchase_id", 1)]),  # ESSENCIAL!
        ("credit_card_installments", [("user_id", 1), ("paid", 1)]),
        ("credit_card_installments", [("card_id", 1), ("due_date", 1)]),
        ("credit_card_installments", [("user_id", 1), ("due_date", 1)]),
    ]
    
    for collection_name, keys in indexes:
        try:
            collection = db[collection_name]
            await collection.create_index(keys)
            logger.info(f"✅ Índice {collection_name}.{keys} criado")
        except Exception as e:
            logger.warning(f"⚠️ Índice em {collection_name}: {e}")
    
    # ========== CONQUISTAS (ACHIEVEMENTS) ==========
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
            logger.warning(f"⚠️ Índice em {collection_name}: {e}")
    
    # ========== BLACKLIST DE TOKENS (SEGURANÇA) ==========
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
        logger.warning(f"⚠️ Índices refresh_token_blacklist: {e}")
    
    logger.info("✅ Todos os índices foram criados/verificados com sucesso!")