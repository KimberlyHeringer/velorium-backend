"""
Arquivo principal do backend Velorium - Versão Estável
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
import importlib
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection, get_database
from app.indexes import create_indexes
from app.utils.rate_limiter import init_rate_limiter
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# ========== CONFIGURAÇÕES ==========
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL")

# 🔧 CORRIGIDO: Validação de FRONTEND_URL em produção
if ENVIRONMENT == "production" and not FRONTEND_URL:
    logger.error("❌ FRONTEND_URL não configurado em produção! Usando fallback seguro.")
    FRONTEND_URL = "https://expo.dev"

# ========== CRIA APLICAÇÃO ==========
app = FastAPI(
    title="Velorium API",
    description="API do app de gestão financeira Velorium",
    version="1.0.0"
)

# ========== OPENTELEMETRY ==========
if OTEL_ENABLED:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("✅ OpenTelemetry instrumentado no FastAPI")
    except ImportError as e:
        logger.warning(f"⚠️ OpenTelemetry FastAPI não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao instrumentar FastAPI: {e}", exc_info=True)

# ========== RATE LIMITER ==========
try:
    init_rate_limiter(app)
    logger.info("✅ Rate limiter inicializado")
except Exception as e:
    logger.warning(f"⚠️ Rate limiter não inicializado: {e}")

# ========== CORS ==========
# 🔧 CORRIGIDO: CORS com lista específica em desenvolvimento
if ENVIRONMENT == "development":
    ALLOWED_ORIGINS = [
        "http://localhost:8081",
        "http://localhost:8082",
        "exp://",
        "http://localhost:19000",
        "http://localhost:19001",
        "http://localhost:19002",
        "http://192.168.0.242:8081",
    ]
    logger.warning("🔧 CORS: Desenvolvimento - origens locais")
else:
    if not FRONTEND_URL:
        logger.error("❌ FRONTEND_URL não configurado para produção!")
        ALLOWED_ORIGINS = ["https://expo.dev", "exp://"]
    else:
        ALLOWED_ORIGINS = [FRONTEND_URL, "https://expo.dev", "exp://"]
    logger.info(f"🔧 CORS: Produção - origens permitidas: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== SCHEDULER ==========
def start_scheduler():
    """Inicia o scheduler se habilitado."""
    if not SCHEDULER_ENABLED:
        logger.info("⏰ Scheduler desabilitado (SCHEDULER_ENABLED=false)")
        return None
    
    try:
        from app.scheduler import start_scheduler as start
        logger.info("✅ Scheduler iniciado")
        return start()
    except ImportError:
        logger.warning("⚠️ Scheduler não disponível")
        return None
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar scheduler: {e}", exc_info=True)
        return None

# ========== EVENTOS ==========
@app.on_event("startup")
async def startup():
    """Executado quando o servidor inicia."""
    logger.info("🚀 Iniciando Velorium API...")
    
    # 🔧 CORRIGIDO: Timeout no startup
    async def initialize():
        await asyncio.wait_for(connect_to_mongo(), timeout=30.0)
        db = get_database()
        await asyncio.wait_for(create_indexes(db), timeout=20.0)
    
    try:
        if OTEL_ENABLED:
            try:
                from opentelemetry import trace
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span("startup") as span:
                    span.set_attribute("app.name", "velorium")
                    span.set_attribute("app.environment", ENVIRONMENT)
                    await initialize()
            except Exception as e:
                logger.error(f"❌ Erro no startup com OpenTelemetry: {e}", exc_info=True)
                await initialize()
        else:
            await initialize()
        
        start_scheduler()
        logger.info("✅ Velorium API pronta para uso!")
        
    except asyncio.TimeoutError:
        logger.error("❌ Timeout na inicialização do banco de dados")
        raise RuntimeError("Banco de dados não respondeu dentro do tempo limite")
    except Exception as e:
        logger.error(f"❌ Erro fatal no startup: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown():
    """Executado quando o servidor desliga."""
    logger.info("🛑 Desligando Velorium API...")
    await close_mongo_connection()
    logger.info("✅ Desligamento concluído")

# ========== ROTAS (CARREGAMENTO SEGURO) ==========
# 🔧 CORRIGIDO: Verifica existência de arquivos antes de importar

ROUTERS = [
    "auth", "transactions", "bills", "credit_cards",
    "credit_card_purchases", "ia", "profile", "score",
    "goals", "user", "investments", "notifications",
    "achievements", "bill_installments"
]

for router_name in ROUTERS:
    try:
        # 🔧 CORRIGIDO: Verifica se o arquivo existe
        router_path = Path(__file__).parent / "app" / "routes" / f"{router_name}.py"
        if not router_path.exists():
            logger.warning(f"⚠️ Arquivo de rota {router_name}.py não encontrado, pulando...")
            continue
            
        module = importlib.import_module(f"app.routes.{router_name}")
        if hasattr(module, "router"):
            app.include_router(module.router, prefix="/api/v1")
            logger.info(f"✅ Rota /api/v1/{router_name} carregada")
        else:
            logger.warning(f"⚠️ Módulo {router_name} não possui 'router'")
            
    except ImportError as e:
        logger.warning(f"⚠️ Rota {router_name} não encontrada: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao carregar rota {router_name}: {e}", exc_info=True)

# ========== ENDPOINTS PÚBLICOS ==========
@app.get("/")
async def root():
    response = {
        "message": "Velorium API - Online",
        "version": "1.0.0",
        "status": "operational"
    }
    # 🔧 CORRIGIDO: Só expõe environment em desenvolvimento
    if ENVIRONMENT == "development":
        response["environment"] = ENVIRONMENT
    return response

@app.get("/health")
async def health():
    from app.database import health_check
    db_status = await health_check()
    
    # 🔧 CORRIGIDO: Não expõe environment em produção
    response = {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Apenas em desenvolvimento para debug
    if ENVIRONMENT == "development":
        response["environment"] = ENVIRONMENT
    
    if OTEL_ENABLED:
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("health_check") as span:
                span.set_attribute("db.status", db_status.get("status", "unknown"))
                span.set_attribute("db.database", db_status.get("database", "unknown"))
        except Exception as e:
            logger.warning(f"⚠️ Erro no span health_check: {e}")
    
    return response

logger.info(f"✅ Velorium API configurada (Ambiente: {ENVIRONMENT})")