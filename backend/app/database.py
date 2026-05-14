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

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "velorium_db")

if not MONGO_URI:
    raise ValueError("MONGO_URI nao encontrada no .env!")

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
            tlsCAFile=certifi.where()
        )
        await client.admin.command('ping')
        db = client[DATABASE_NAME]
        print(f"Conectado ao MongoDB: {DATABASE_NAME}")
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
        raise HTTPException(status_code=503, detail="Banco de dados indisponivel")


async def close_mongo_connection():
    global client, db
    if client:
        client.close()
        db = None
        print("Conexao com MongoDB fechada")


def get_database():
    if db is None:
        raise HTTPException(status_code=503, detail="Banco de dados nao conectado")
    return db


async def health_check() -> dict:
    try:
        if client is None:
            return {"status": "disconnected"}
        await client.admin.command('ping')
        return {"status": "healthy", "database": DATABASE_NAME}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def create_indexes():
    db = get_database()
    
    await db.transactions.create_index([("user_id", 1)])
    await db.transactions.create_index([("user_id", 1), ("date", -1)])
    await db.transactions.create_index([("user_id", 1), ("context", 1), ("date", -1)])
    
    await db.bills.create_index([("user_id", 1)])
    await db.bills.create_index([("user_id", 1), ("installments.start_date", 1)])
    
    await db.goals.create_index([("user_id", 1)])
    await db.user_profiles.create_index([("user_id", 1)], unique=True)
    await db.score_history.create_index([("user_id", 1), ("date", -1)])
    await db.credit_cards.create_index([("user_id", 1)])
    await db.credit_card_purchases.create_index([("card_id", 1)])
    
    await db.refresh_token_blacklist.create_index([("expires_at", 1)], expireAfterSeconds=0)
    await db.refresh_token_blacklist.create_index([("token", 1)], unique=True)
    
    print("Indices criados/verificados com sucesso")
    )
    # Índice único para garantir que o mesmo token não seja inserido duas vezes
    await db.refresh_token_blacklist.create_index([("token", 1)], unique=True)
    
    print("✅ Índices criados/verificados com sucesso")
