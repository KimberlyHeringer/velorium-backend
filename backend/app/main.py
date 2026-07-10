"""
Arquivo principal do backend Velorium - Versão Estável com i18n, Cache Redis e Categorias Personalizadas
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection, get_database
from app.indexes import create_indexes
from app.utils.rate_limiter import init_rate_limiter
from app.utils.logger import setup_logger

# ========== 🔧 NOVO: Internacionalização ==========
from app.middleware.language import LanguageMiddleware

# 🔧 NOVO: Migrations
from app.utils.migrations import run_migrations

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

# ========== 🔧 NOVO: MIDDLEWARE DE IDIOMA ==========
app.add_middleware(LanguageMiddleware)
logger.info("✅ Middleware de idioma registrado")

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
    ALLOWED_ORIGINS = [
        "http://localhost:8081",
        "http://localhost:8082",
        "http://localhost:19000",
        "http://localhost:19001",
        "http://localhost:19002",
        "http://192.168.0.242:8081",
    ]
    logger.warning("🔧 CORS: Desenvolvimento - origens locais")
else:
    if not FRONTEND_URL:
        logger.error("❌ FRONTEND_URL não configurado para produção!")
        ALLOWED_ORIGINS = ["https://expo.dev"]
    else:
        ALLOWED_ORIGINS = [FRONTEND_URL, "https://expo.dev"]
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
        await asyncio.wait_for(connect_to_mongo(), timeout=30.0)
        db = get_database()
        await asyncio.wait_for(create_indexes(db), timeout=20.0)
        # 🔧 NOVO: Executa migrações
        await asyncio.wait_for(run_migrations(db), timeout=30.0)
    
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

# ========== ROTAS (IMPORTS MANUAIS - MAIS CONFIÁVEL) ==========
from app.routes import (
    auth, 
    transactions, 
    bills, 
    credit_cards,
    credit_card_purchases, 
    ia, 
    profile, 
    score,
    goals, 
    user, 
    investments, 
    notifications,
    achievements, 
    bill_installments,
    cache,          # 🆕 Rota de cache Redis
    categories      # 🆕 Rota de categorias personalizadas
)

# Registrar rotas manualmente
app.include_router(auth.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(bills.router, prefix="/api/v1")
app.include_router(bill_installments.router, prefix="/api/v1")
app.include_router(credit_cards.router, prefix="/api/v1")
app.include_router(credit_card_purchases.router, prefix="/api/v1")
app.include_router(ia.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(score.router, prefix="/api/v1")
app.include_router(goals.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(achievements.router, prefix="/api/v1")
app.include_router(investments.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(cache.router, prefix="/api/v1")          # 🆕 Rota de cache Redis
app.include_router(categories.router, prefix="/api/v1")     # 🆕 Rota de categorias personalizadas

# 🔧 NOVO: Rota de workers (status dos workers)
try:
    from app.routes import workers
    app.include_router(workers.router, prefix="/api/v1")
    logger.info("✅ Rota de workers registrada")
except ImportError as e:
    logger.warning(f"⚠️ Rota de workers não disponível: {e}")

# ========== ENDPOINTS PÚBLICOS ==========
@app.get("/")
async def root():
    response = {
        "message": "Velorium API - Online",
        "version": "1.0.0",
        "status": "operational"
    }
    if ENVIRONMENT == "development":
        response["environment"] = ENVIRONMENT
    return response

@app.get("/health")
async def health():
    from app.database import health_check
    db_status = await health_check()
    
    response = {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
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