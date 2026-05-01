"""
Configuração da conexão com MongoDB
Arquivo: backend/app/utils/database.py
"""

from __future__ import annotations
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
    raise ValueError("MONGO_URI não encontrada no .env!")

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
        # ⚠️ ATENÇÃO: NÃO adicione tlsAllowInvalidCertificates=True aqui
        # Isso desabilita a verificação do certificado SSL e é uma falha de segurança
        # O MongoDB Atlas já tem certificado válido, não precisa dessa flag
        
        client = AsyncIOMotorClient(
            MONGO_URI,
            maxPoolSize=50,          # Máximo de conexões simultâneas
            minPoolSize=10,          # Mínimo mantido aberto
            serverSelectionTimeoutMS=5000,   # 5 segundos para escolher servidor
            connectTimeoutMS=10000,          # 10 segundos para conectar
            socketTimeoutMS=20000,           # 20 segundos para operações
            retryWrites=True,                # Re-tenta escritas em caso de falha
            w="majority",                    # Garante consistência
            tls=True,                        # SSL ativado (obrigatório)
            tlsCAFile=certifi.where()        # Certificado CA confiável
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
    
    # Índice para transações (mais comum)
    await db.transactions.create_index([("user_id", 1)])
    await db.transactions.create_index([("user_id", 1), ("date", -1)])
    
    # Índice composto para buscas por contexto + data (usado no dashboard)
    await db.transactions.create_index([("user_id", 1), ("context", 1), ("date", -1)])
    
    # Índices para contas a pagar
    await db.bills.create_index([("user_id", 1)])
    await db.bills.create_index([("user_id", 1), ("installments.start_date", 1)])
    
    # Índice para metas
    await db.goals.create_index([("user_id", 1)])
    
    # Índice para perfil financeiro (único por usuário)
    await db.user_profiles.create_index([("user_id", 1)], unique=True)
    
    # Índice para histórico de score
    await db.score_history.create_index([("user_id", 1), ("date", -1)])
    
    # Índices para cartões de crédito
    await db.credit_cards.create_index([("user_id", 1)])
    
    # Índice para compras parceladas (busca por cartão)
    await db.credit_card_purchases.create_index([("card_id", 1)])
    
    print("✅ Índices criados/verificados com sucesso")