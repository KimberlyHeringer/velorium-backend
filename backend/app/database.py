"""
Configuração da conexão com MongoDB
Arquivo: backend/app/database.py

🔧 CORRIGIDO:
- db tipado corretamente como AsyncIOMotorDatabase | None
- create_indexes() removido (movido para indexes.py)
- connect_to_mongo() levanta RuntimeError (não HTTPException)
- get_database() levanta RuntimeError (não HTTPException)
- Logs com exc_info=True para melhor rastreamento
- Validação de MONGO_URI mais clara
- Agora focado APENAS em conexão e health check
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv
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

# 🔧 CORRIGIDO: Validação de MONGO_URI mais clara
if not MONGO_URI:
    raise ValueError(
        "❌ MONGO_URI não encontrada no .env!\n"
        "   Certifique-se de que o arquivo .env existe e contém:\n"
        "   MONGO_URI=mongodb+srv://<usuario>:<senha>@<cluster>.mongodb.net/"
    )

# 🔧 CORRIGIDO: Verifica se a URI começa com o formato correto
if not MONGO_URI.startswith(("mongodb://", "mongodb+srv://")):
    logger.warning(f"⚠️ MONGO_URI não começa com 'mongodb://' ou 'mongodb+srv://': {MONGO_URI[:20]}...")

# 🔧 CORRIGIDO: Tipagem correta
client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None


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
        # 🔧 CORRIGIDO: RuntimeError em vez de HTTPException (startup)
        logger.error(f"❌ Erro ao conectar ao MongoDB: {e}", exc_info=True)
        raise RuntimeError(f"Banco de dados indisponível: {e}")


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
    # 🔧 CORRIGIDO: RuntimeError em vez de HTTPException
    if db is None:
        raise RuntimeError("Banco de dados não conectado")
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
        logger.error(f"❌ Health check falhou: {e}", exc_info=True)
        return {"status": "unhealthy", "error": str(e)}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Tipagem correta com Optional[AsyncIOMotorDatabase]
# ✅ RuntimeError em vez de HTTPException para funções internas
# ✅ Logs com exc_info=True para melhor rastreamento
# ✅ Validação clara de MONGO_URI
# ✅ Índices movidos para indexes.py (organização)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO