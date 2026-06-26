"""
Arquivo principal do backend Velorium - Versão Estável
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timezone
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
if ENVIRONMENT == "development":
    ALLOWED_ORIGINS = ["*"]
    logger.warning("🔧 CORS: Desenvolvimento - permitindo todas as origens")
else:
    if not FRONTEND_URL:
        logger.warning("⚠️ FRONTEND_URL não configurado! CORS pode bloquear requisições.")
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
    
    async def initialize():
        await connect_to_mongo()
        db = get_database()
        await create_indexes(db)
    
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

@app.on_event("shutdown")
async def shutdown():
    """Executado quando o servidor desliga."""
    logger.info("🛑 Desligando Velorium API...")
    await close_mongo_connection()
    logger.info("✅ Desligamento concluído")

# ========== ROTAS (CARREGAMENTO SEGURO) ==========
# 🔧 REMOVIDOS: imports diretos (não são mais necessários)
# As rotas são carregadas dinamicamente pelo loop abaixo

ROUTERS = [
    "auth", "transactions", "bills", "credit_cards",
    "credit_card_purchases", "ia", "profile", "score",
    "goals", "user", "investments", "notifications",
    "achievements", "bill_installments"
]

for router_name in ROUTERS:
    try:
        module = __import__(f"app.routes.{router_name}", fromlist=["router"])
        app.include_router(module.router, prefix="/api/v1")
        logger.info(f"✅ Rota /api/v1/{router_name} carregada")
    except ImportError as e:
        logger.warning(f"⚠️ Rota {router_name} não encontrada: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao carregar rota {router_name}: {e}", exc_info=True)

# ========== ENDPOINTS PÚBLICOS ==========
@app.get("/")
async def root():
    return {
        "message": "Velorium API - Online",
        "version": "1.0.0",
        "status": "operational",
        "environment": ENVIRONMENT
    }

@app.get("/health")
async def health():
    from app.database import health_check
    db_status = await health_check()
    
    response = {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": ENVIRONMENT
    }
    
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