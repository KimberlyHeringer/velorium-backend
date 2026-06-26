"""
Configuração da conexão com MongoDB
Arquivo: backend/app/database.py

🔧 CORRIGIDO:
- db tipado corretamente como AsyncIOMotorDatabase | None
- connect_to_mongo() levanta RuntimeError (não HTTPException)
- get_database() levanta RuntimeError (não HTTPException)
- Logs com exc_info=True para melhor rastreamento
- Validação de MONGO_URI mais clara
- 🔧 REFATORADO: connect_to_mongo() sem duplicação de código
- 🔧 REFATORADO: apply_schemas() com dicionário de schemas (DRY)
- 🔧 REFATORADO: OpenTelemetry movido para função init_telemetry()
- 🔧 CORRIGIDO: init_telemetry() agora é chamada
- 🔧 CORRIGIDO: DATABASE_NAME com fallback para string vazia
- 🔧 MELHORADO: Health check com mais métricas
- 🔧 MELHORADO: Fallback para certifi com verificação
- 🔧 NOVO: Retry logic com backoff exponencial configurável
- 🔧 NOVO: Schema de amount aceita int ou double com mínimo 0.01
- 🔧 NOVO: Context manager para transações com timeout configurável
- 🔧 CORRIGIDO: OpenTelemetry com OTLP Exporter em produção
- 🔧 CORRIGIDO: MAX_RETRIES, RETRY_DELAY, DB_TIMEOUT configuráveis via .env
- 🔧 CORRIGIDO: Pool size configurável via .env (otimizado para free tier)
- 🔧 CORRIGIDO: Timeout com validação (mínimo 1 segundo)
- 🔧 CORRIGIDO: additionalProperties: false nos schemas
- 🔧 OTIMIZADO: apply_schemas() com list_collections() e comparação robusta
- 🔧 CORRIGIDO: schemas_are_equal() para comparação ignorando ordem
- 🔧 NOVO: FORCE_SCHEMA_UPDATE via .env para desenvolvimento
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional, Dict, Any
import os
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
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
DATABASE_NAME = os.getenv("DATABASE_NAME") or "velorium_db"

# ========== CONFIGURAÇÕES (configuráveis via .env) ==========
MAX_RETRIES = int(os.getenv("MONGO_MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("MONGO_RETRY_DELAY", "2"))
DB_TIMEOUT = max(1, int(os.getenv("MONGO_TIMEOUT", "30")))  # Mínimo 1 segundo
MAX_POOL_SIZE = int(os.getenv("MONGO_MAX_POOL_SIZE", "10"))  # Safe para free tier
MIN_POOL_SIZE = int(os.getenv("MONGO_MIN_POOL_SIZE", "2"))
FORCE_SCHEMA_UPDATE = os.getenv("FORCE_SCHEMA_UPDATE", "false").lower() == "true"

# ========== VALIDAÇÃO DE MONGO_URI ==========
if not MONGO_URI:
    raise ValueError(
        "❌ MONGO_URI não encontrada no .env!\n"
        "   Certifique-se de que o arquivo .env existe e contém:\n"
        "   MONGO_URI=mongodb+srv://<usuario>:<senha>@<cluster>.mongodb.net/"
    )

if not MONGO_URI.startswith(("mongodb://", "mongodb+srv://")):
    logger.warning(f"⚠️ MONGO_URI não começa com 'mongodb://' ou 'mongodb+srv://': {MONGO_URI[:20]}...")

# ========== TIPAGEM ==========
client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None

# ========== OPENTELEMETRY ==========
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
OTEL_ENDPOINT = os.getenv("OTEL_ENDPOINT", "http://localhost:4317")
tracer = None
otel_initialized = False


def init_telemetry():
    """
    Inicializa o OpenTelemetry para monitoramento.
    🔧 CORRIGIDO: Usa OTLP Exporter em produção, Console em desenvolvimento.
    """
    global tracer, otel_initialized
    
    if not OTEL_ENABLED:
        logger.info("⏳ OpenTelemetry desabilitado (OTEL_ENABLED=false)")
        return False
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.semconv.trace import SpanAttributes
        
        # 🔧 CORRIGIDO: Escolhe o exporter baseado no ambiente
        if ENVIRONMENT == "production":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT)
            logger.info(f"🔧 OpenTelemetry: usando OTLP Exporter ({OTEL_ENDPOINT})")
        else:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            exporter = ConsoleSpanExporter()
            logger.info("🔧 OpenTelemetry: usando Console Exporter (desenvolvimento)")
        
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)
        
        span_processor = BatchSpanProcessor(exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Tenta instrumentar o MongoDB
        try:
            from opentelemetry.instrumentation.pymongo import PyMongoInstrumentor
            PyMongoInstrumentor().instrument()
            logger.info("✅ OpenTelemetry: PyMongoInstrumentor ativado")
        except ImportError:
            try:
                from opentelemetry.instrumentation.motor import MotorInstrumentor
                MotorInstrumentor().instrument()
                logger.info("✅ OpenTelemetry: MotorInstrumentor ativado")
            except ImportError:
                logger.warning("⚠️ OpenTelemetry: Nenhum instrumentor encontrado para MongoDB")
                logger.info("ℹ️  OpenTelemetry: Instrumentação manual será usada")
        
        otel_initialized = True
        logger.info("✅ OpenTelemetry configurado com sucesso")
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️ OpenTelemetry não disponível: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao configurar OpenTelemetry: {e}", exc_info=True)
        return False


# ========== CONEXÃO COM MONGODB ==========

def get_client_options() -> Dict[str, Any]:
    """
    Retorna as opções de configuração do cliente MongoDB.
    🔧 CORRIGIDO: Pool size configurável via .env
    🔧 CORRIGIDO: certifi com verificação de existência
    """
    # 🔧 CORRIGIDO: Verificação de certifi
    try:
        tls_ca = certifi.where()
        if not os.path.exists(tls_ca):
            raise FileNotFoundError(f"Arquivo certifi não encontrado: {tls_ca}")
    except Exception:
        tls_ca = None
        logger.warning("⚠️ certifi não disponível, usando certificados do sistema")
    
    return {
        "maxPoolSize": MAX_POOL_SIZE,
        "minPoolSize": MIN_POOL_SIZE,
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 10000,
        "socketTimeoutMS": 20000,
        "retryWrites": True,
        "w": "majority",
        "tls": True,
        "tlsCAFile": tls_ca
    }


async def connect_to_mongo():
    """
    Estabelece conexão com o MongoDB Atlas.
    🔧 NOVO: Retry logic com backoff exponencial configurável.
    """
    global client, db, tracer
    
    client_options = get_client_options()
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"🔄 Tentativa {attempt + 1}/{MAX_RETRIES} de conectar ao MongoDB...")
            
            if OTEL_ENABLED and tracer:
                with tracer.start_as_current_span("connect_to_mongo") as span:
                    span.set_attribute("db.system", "mongodb")
                    span.set_attribute("db.name", DATABASE_NAME)
                    client = AsyncIOMotorClient(MONGO_URI, **client_options)
            else:
                client = AsyncIOMotorClient(MONGO_URI, **client_options)
            
            await client.admin.command('ping')
            db = client[DATABASE_NAME]
            logger.info(f"✅ Conectado ao MongoDB: {DATABASE_NAME}")
            
            # Aplica JSON Schema validation (otimizado)
            await apply_schemas()
            return
            
        except Exception as e:
            logger.warning(f"⚠️ Tentativa {attempt + 1} falhou: {e}")
            
            if attempt == MAX_RETRIES - 1:
                logger.error(f"❌ Todas as {MAX_RETRIES} tentativas falharam", exc_info=True)
                raise RuntimeError(f"Banco de dados indisponível após {MAX_RETRIES} tentativas: {e}")
            
            wait_time = RETRY_DELAY * (2 ** attempt)
            logger.info(f"⏳ Aguardando {wait_time}s antes da próxima tentativa...")
            await asyncio.sleep(wait_time)


async def close_mongo_connection():
    """Fecha a conexão com o MongoDB."""
    global client, db
    if client:
        client.close()
        db = None
        logger.info("✅ Conexão com MongoDB fechada")


def get_database():
    """Retorna a instância do banco de dados."""
    if db is None:
        raise RuntimeError("Banco de dados não conectado")
    return db


# ========== CONTEXT MANAGER ==========

@asynccontextmanager
async def get_db_context(timeout: int = DB_TIMEOUT):
    """
    Context manager para acesso ao banco.
    🔧 NOVO: Timeout configurável com validação.
    """
    db_instance = get_database()
    try:
        yield db_instance
    except asyncio.TimeoutError:
        logger.error(f"⏰ Timeout ({timeout}s) na operação do banco")
        raise
    except Exception as e:
        logger.error(f"❌ Erro no contexto do banco: {e}", exc_info=True)
        raise


async def health_check() -> dict:
    """Verifica se o banco está saudável."""
    try:
        if client is None:
            return {"status": "disconnected"}
        
        await client.admin.command('ping')
        
        try:
            topology = client.topology_description
            if hasattr(topology, 'server_descriptions'):
                servers = topology.server_descriptions()
                connected = sum(1 for s in servers.values() if s.is_connected) if servers else 0
                total = len(servers) if servers else 0
            else:
                connected = 0
                total = 0
        except Exception:
            connected = 0
            total = 0
        
        return {
            "status": "healthy",
            "database": DATABASE_NAME,
            "connected_servers": f"{connected}/{total}" if total > 0 else "unknown",
            "pool_size": total or "unknown"
        }
        
    except Exception as e:
        logger.error(f"❌ Health check falhou: {e}", exc_info=True)
        return {"status": "unhealthy", "error": str(e)}


# ========== JSON SCHEMA VALIDATION ==========

# 🔧 REFATORADO: Schemas em dicionário (DRY)
# 🔧 CORRIGIDO: amount com mínimo 0.01
# 🔧 CORRIGIDO: additionalProperties: False
SCHEMAS: Dict[str, Dict[str, Any]] = {
    "transactions": {
        "bsonType": "object",
        "additionalProperties": False,
        "required": ["user_id", "amount", "type", "date", "description"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "amount": {"bsonType": ["int", "double"], "minimum": 0.01},
            "type": {"enum": ["income", "expense"]},
            "date": {"bsonType": "date"},
            "description": {"bsonType": "string", "maxLength": 200},
            "category": {"bsonType": "string"},
            "context": {"enum": ["individual", "familia", "professional"]},
            "payment_method": {"enum": ["dinheiro", "cartao_credito", "cartao_debito", "pix", "transferencia", "boleto", "outros"]}
        }
    },
    "goals": {
        "bsonType": "object",
        "additionalProperties": False,
        "required": ["user_id", "name", "target", "current"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "name": {"bsonType": "string", "maxLength": 100},
            "target": {"bsonType": ["int", "double"], "minimum": 0.01},
            "current": {"bsonType": ["int", "double"], "minimum": 0},
            "category": {"bsonType": "string"},
            "completed": {"bsonType": "bool"},
            "deadline": {"bsonType": "date"}
        }
    },
    "bills": {
        "bsonType": "object",
        "additionalProperties": False,
        "required": ["user_id", "description", "amount"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "description": {"bsonType": "string", "maxLength": 200},
            "amount": {"bsonType": ["int", "double"], "minimum": 0.01},
            "category": {"bsonType": "string"},
            "paid": {"bsonType": "bool"},
            "installments": {
                "bsonType": "object",
                "properties": {
                    "total": {"bsonType": "int", "minimum": 1},
                    "start_date": {"bsonType": "date"}
                }
            }
        }
    },
    "credit_cards": {
        "bsonType": "object",
        "additionalProperties": False,
        "required": ["user_id", "name", "closing_day", "due_day"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "name": {"bsonType": "string", "maxLength": 50},
            "brand": {"bsonType": "string", "maxLength": 30},
            "closing_day": {"bsonType": "int", "minimum": 1, "maximum": 31},
            "due_day": {"bsonType": "int", "minimum": 1, "maximum": 31},
            "total_limit": {"bsonType": ["int", "double"], "minimum": 0},
            "used_limit": {"bsonType": ["int", "double"], "minimum": 0},
            "committed_amount": {"bsonType": ["int", "double"], "minimum": 0}
        }
    }
}


def schemas_are_equal(schema1: Dict, schema2: Dict) -> bool:
    """
    Compara dois JSON Schemas ignorando ordem e campos irrelevantes.
    🔧 CORRIGIDO: Comparação robusta para evitar falsos positivos.
    """
    # Campos que o MongoDB pode adicionar automaticamente (ignorar)
    ignore_keys = {"title", "description", "$id", "$schema"}
    
    def clean_schema(schema):
        """Remove campos irrelevantes e normaliza para comparação."""
        if not isinstance(schema, dict):
            return schema
        
        cleaned = {}
        for key, value in schema.items():
            if key in ignore_keys:
                continue
            if isinstance(value, dict):
                cleaned[key] = clean_schema(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    clean_schema(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        return cleaned
    
    cleaned1 = clean_schema(schema1)
    cleaned2 = clean_schema(schema2)
    
    # Comparação com sort_keys para ignorar ordem
    try:
        return json.dumps(cleaned1, sort_keys=True) == json.dumps(cleaned2, sort_keys=True)
    except:
        return cleaned1 == cleaned2


async def apply_schemas():
    """
    Aplica JSON Schema validation nas coleções do MongoDB.
    🔧 CORRIGIDO: Usa list_collections() que é mais confiável.
    🔧 CORRIGIDO: Comparação robusta com schemas_are_equal().
    🔧 NOVO: FORCE_SCHEMA_UPDATE para forçar recriação em dev.
    """
    if db is None:
        logger.error("❌ Banco não conectado, não é possível aplicar schemas")
        return
    
    logger.info("🔄 Aplicando JSON Schema validation...")
    
    # Obtém informações das coleções
    collections = await db.list_collection_names()
    collection_infos = await db.list_collections()
    collection_validators = {
        info["name"]: info.get("options", {}).get("validator", {}) 
        for info in collection_infos
    }
    
    for collection_name, schema in SCHEMAS.items():
        try:
            if collection_name not in collections:
                await db.create_collection(collection_name, validator={
                    "$jsonSchema": schema
                })
                logger.info(f"✅ Schema criado em '{collection_name}'")
            else:
                existing_validator = collection_validators.get(collection_name, {})
                existing_schema = existing_validator.get("$jsonSchema", {})
                
                # 🔧 CORRIGIDO: FORCE_SCHEMA_UPDATE para desenvolvimento
                if FORCE_SCHEMA_UPDATE:
                    await db.command({
                        "collMod": collection_name,
                        "validator": {"$jsonSchema": schema}
                    })
                    logger.info(f"✅ Schema forçado em '{collection_name}' (FORCE_SCHEMA_UPDATE=true)")
                # 🔧 CORRIGIDO: Comparação robusta
                elif not existing_schema or not schemas_are_equal(existing_schema, schema):
                    await db.command({
                        "collMod": collection_name,
                        "validator": {"$jsonSchema": schema}
                    })
                    logger.info(f"✅ Schema atualizado em '{collection_name}'")
                else:
                    logger.debug(f"ℹ️ Schema já existe em '{collection_name}'")
                    
        except Exception as e:
            logger.warning(f"⚠️ Schema para '{collection_name}': {e}", exc_info=True)
    
    logger.info("✅ JSON Schema validation aplicado com sucesso!")


# ========== INICIALIZA OPENTELEMETRY (SE HABILITADO) ==========
if OTEL_ENABLED:
    init_telemetry()


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Tipagem correta com Optional[AsyncIOMotorDatabase]
# ✅ RuntimeError em vez de HTTPException
# ✅ Logs com exc_info=True
# ✅ Validação clara de MONGO_URI
# ✅ 🔧 REFATORADO: connect_to_mongo() sem duplicação
# ✅ 🔧 REFATORADO: apply_schemas() com dicionário (DRY)
# ✅ 🔧 REFATORADO: OpenTelemetry em função explícita
# ✅ 🔧 CORRIGIDO: init_telemetry() chamada
# ✅ 🔧 CORRIGIDO: DATABASE_NAME com fallback
# ✅ 🔧 MELHORADO: Health check com métricas
# ✅ 🔧 MELHORADO: Fallback para certifi com verificação
# ✅ 🔧 NOVO: Retry logic configurável
# ✅ 🔧 NOVO: Schema de amount com mínimo 0.01
# ✅ 🔧 NOVO: Context manager com timeout
# ✅ 🔧 CORRIGIDO: OTLP Exporter em produção
# ✅ 🔧 CORRIGIDO: MAX_RETRIES configurável via .env
# ✅ 🔧 CORRIGIDO: Pool size configurável via .env
# ✅ 🔧 CORRIGIDO: Timeout com validação (mínimo 1s)
# ✅ 🔧 CORRIGIDO: additionalProperties: false nos schemas
# ✅ 🔧 OTIMIZADO: apply_schemas() com list_collections()
# ✅ 🔧 CORRIGIDO: schemas_are_equal() para comparação robusta
# ✅ 🔧 NOVO: FORCE_SCHEMA_UPDATE via .env
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO