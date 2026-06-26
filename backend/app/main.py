"""
Arquivo principal do backend Velorium - Versão Estável sem Workers
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import atexit

from app.database import connect_to_mongo, close_mongo_connection, get_database
from app.indexes import create_indexes
from app.routes import auth, transactions, bills, credit_cards, credit_card_purchases, ia, profile, score, goals, user, investments, notifications
from app.routes import achievements, bill_installments
from app.utils.rate_limiter import init_rate_limiter
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# Cria a aplicação FastAPI
app = FastAPI(
    title="Velorium API",
    description="API do app de gestão financeira Velorium",
    version="1.0.0"
)

# ========== 🔧 NOVO: OpenTelemetry - Inicialização ==========
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"

if OTEL_ENABLED:
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        
        # Instrumenta o FastAPI
        FastAPIInstrumentor.instrument_app(app)
        logger.info("✅ OpenTelemetry instrumentado no FastAPI")
    except ImportError as e:
        logger.warning(f"⚠️ OpenTelemetry FastAPI não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao instrumentar FastAPI: {e}", exc_info=True)

# ========== INICIALIZA RATE LIMITER ==========
init_rate_limiter(app)

# ========== CONFIGURAÇÃO DO CORS ==========
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "development":
    ALLOWED_ORIGINS = ["*"]
    logger.warning("🔧 CORS: Desenvolvimento - permitindo todas as origens")
else:
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://seuapp.expo.app")
    ALLOWED_ORIGINS = [
        FRONTEND_URL,
        "https://expo.dev",
        "exp://",
    ]
    logger.info(f"🔧 CORS: Produção - origens permitidas: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== FUNÇÃO PARA INICIAR SCHEDULER (DESABILITADA) ==========
def start_scheduler():
    """Scheduler desabilitado temporariamente para troubleshooting"""
    logger.info("⏰ Scheduler desabilitado (workers em manutenção)")
    return None


# ========== EVENTOS DE INICIALIZAÇÃO E DESLIGAMENTO ==========
@app.on_event("startup")
async def startup():
    """Executado quando o servidor inicia"""
    logger.info("🚀 Iniciando Velorium API...")
    
    # 🔧 NOVO: Span para startup (OpenTelemetry)
    if OTEL_ENABLED:
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("startup") as span:
                span.set_attribute("app.name", "velorium")
                await connect_to_mongo()
                db = get_database()
                await create_indexes(db)
        except Exception as e:
            logger.error(f"❌ Erro no startup com OpenTelemetry: {e}", exc_info=True)
            await connect_to_mongo()
            db = get_database()
            await create_indexes(db)
    else:
        await connect_to_mongo()
        db = get_database()
        await create_indexes(db)
    
    start_scheduler()
    logger.info("✅ Velorium API pronta para uso!")


@app.on_event("shutdown")
async def shutdown():
    """Executado quando o servidor desliga"""
    logger.info("🛑 Desligando Velorium API...")
    await close_mongo_connection()
    logger.info("✅ Desligamento concluído")


# ========== ROTAS DA API ==========
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


# ========== ENDPOINTS PÚBLICOS ==========
@app.get("/")
async def root():
    return {
        "message": "Velorium API - Online",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health():
    from app.database import health_check
    db_status = await health_check()
    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }