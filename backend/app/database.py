"""
Configuração da conexão com MongoDB
Arquivo: backend/app/database.py
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Any
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException
import certifi

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
        print(f"✅ Conectado ao MongoDB: {DATABASE_NAME}")
        
    except Exception as e:
        print(f"❌ Erro ao conectar ao MongoDB: {e}")
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
        print("✅ Conexão com MongoDB fechada")


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
    """
    db = get_database()
    
    # Lista de índices para criar (ignora erros de índice já existente)
    indexes = [
        ("transactions", [("user_id", 1)]),
        ("transactions", [("user_id", 1), ("date", -1)]),
        ("transactions", [("user_id", 1), ("context", 1), ("date", -1)]),
        ("bills", [("user_id", 1)]),
        ("bills", [("user_id", 1), ("installments.start_date", 1)]),
        ("goals", [("user_id", 1)]),
        ("user_profiles", [("user_id", 1)], {"unique": True}),
        ("score_history", [("user_id", 1), ("date", -1)]),
        ("credit_cards", [("user_id", 1)]),
        ("credit_card_purchases", [("card_id", 1)]),
        ("refresh_token_blacklist", [("expires_at", 1)], {"expireAfterSeconds": 0}),
        ("refresh_token_blacklist", [("token", 1)], {"unique": True}),
    ]
    
    for collection_name, keys, *extra in indexes:
        try:
            collection = db[collection_name]
            options = extra[0] if extra else {}
            await collection.create_index(keys, **options)
        except Exception as e:
            print(f"⚠️ Índice em {collection_name} já existe ou erro: {e}")
    
    print("✅ Índices criados/verificados com sucesso")