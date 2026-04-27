from __future__ import annotations
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Any
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException
import certifi

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "velorium_db")

if not MONGO_URI:
    raise ValueError("MONGO_URI não encontrada no .env!")

client: Optional[AsyncIOMotorClient] = None
db: Any = None

async def connect_to_mongo():
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
            tlsAllowInvalidCertificates=True,
            tlsCAFile=certifi.where()
        )
        await client.admin.command('ping')
        db = client[DATABASE_NAME]
        print(f"✅ Conectado ao MongoDB: {DATABASE_NAME}")
    except Exception as e:
        print(f"❌ Erro ao conectar ao MongoDB: {e}")
        raise HTTPException(status_code=503, detail="Banco de dados indisponível")

async def close_mongo_connection():
    global client, db
    if client:
        client.close()
        db = None
        print("✅ Conexão com MongoDB fechada")

def get_database():
    if db is None:
        raise HTTPException(status_code=503, detail="Banco de dados não conectado")
    return db

async def health_check() -> dict:
    try:
        if client is None:
            return {"status": "disconnected"}
        await client.admin.command('ping')
        return {"status": "healthy", "database": DATABASE_NAME}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ========== ÍNDICES PARA PERFORMANCE ==========
async def create_indexes():
    """Cria índices essenciais para consultas rápidas com muitos usuários"""
    db = get_database()
    
    # Transações
    await db.transactions.create_index([("user_id", 1)])
    await db.transactions.create_index([("user_id", 1), ("date", -1)])
    
    # Contas a pagar
    await db.bills.create_index([("user_id", 1)])
    await db.bills.create_index([("user_id", 1), ("installments.start_date", 1)])
    
    # Metas
    await db.goals.create_index([("user_id", 1)])
    
    # Perfil financeiro
    await db.user_profiles.create_index([("user_id", 1)], unique=True)
    
    # Histórico de score
    await db.score_history.create_index([("user_id", 1), ("date", -1)])
    
    # Cartões de crédito
    await db.credit_cards.create_index([("user_id", 1)])
    
    print("✅ Índices criados/verificados com sucesso")