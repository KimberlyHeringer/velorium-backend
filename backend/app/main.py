"""
Arquivo principal do backend Velorium - Versão Estável com i18n, Cache Redis e Categorias Personalizadas
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.timeout import TimeoutMiddleware
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

# 🔧 NOVO: Scheduler
from app.utils.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

logger = setup_logger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# ================================================================
# CONFIGURAÇÕES
# ================================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"

# 🔧 CORRIGIDO: Timeouts configuráveis
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "30"))
MIGRATION_TIMEOUT = int(os.getenv("MIGRATION_TIMEOUT", "60"))
SHUTDOWN_TIMEOUT = int(os.getenv("SHUTDOWN_TIMEOUT", "10"))

# 🔧 CORRIGIDO: FRONTEND_URL obrigatório em produção
FRONTEND_URL = os.getenv("FRONTEND_URL")

if ENVIRONMENT == "production" and not FRONTEND_URL:
    logger.critical("❌ FRONTEND_URL não configurado em produção!")
    raise ValueError("FRONTEND_URL é obrigatório em produção")

# ================================================================
# CRIA APLICAÇÃO
# ================================================================

app = FastAPI(
    title="Velorium API",
    description="API do app de gestão financeira Velorium",
    version="1.0.0"
)

# ================================================================
# MIDDLEWARES
# ================================================================

# 1. Idioma
app.add_middleware(LanguageMiddleware)
logger.info("✅ Middleware de idioma registrado")

# 2. Timeout global
app.add_middleware(TimeoutMiddleware, timeout=30.0)
logger.info("⏱️ Middleware de timeout global registrado (30s)")

# ================================================================
# OPENTELEMETRY
# ================================================================

scheduler_instance = None

if OTEL_ENABLED:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("✅ OpenTelemetry instrumentado no FastAPI")
    except ImportError as e:
        logger.warning(f"⚠️ OpenTelemetry FastAPI não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao instrumentar FastAPI: {e}", exc_info=True)

# ================================================================
# RATE LIMITER
# ================================================================

try:
    init_rate_limiter(app)
    logger.info("✅ Rate limiter inicializado")
except Exception as e:
    logger.warning(f"⚠️ Rate limiter não inicializado: {e}")

# ================================================================
# CORS
# ================================================================

# 🔧 S5332/S1313: URLs locais são aceitáveis em desenvolvimento
if ENVIRONMENT == "development":
    ALLOWED_ORIGINS = [
        "http://localhost:8081",
        "http://localhost:8082",
        "http://localhost:19000",
        "http://localhost:19001",
        "http://localhost:19002",
        # 🔧 S1313: IP local permitido em desenvolvimento (não é hardcoded em produção)
        "http://192.168.0.242:8081",
    ]
    logger.warning("🔧 CORS: Desenvolvimento - origens locais")
else:
    if not FRONTEND_URL:
        # 🔧 CORRIGIDO: Não usa fallback inseguro
        logger.critical("❌ FRONTEND_URL não configurado para produção!")
        raise ValueError("FRONTEND_URL é obrigatório em produção")
    
    ALLOWED_ORIGINS = [FRONTEND_URL]
    logger.info(f"🔧 CORS: Produção - origens permitidas: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================================================
# MIDDLEWARE: VERSION HEADER
# ================================================================

@app.middleware("http")
async def add_version_header(request, call_next):
    """Adiciona header com versão da API em todas as respostas."""
    response = await call_next(request)
    response.headers["X-API-Version"] = "1.0.0"
    return response

# ================================================================
# EVENTOS
# ================================================================

@app.on_event("startup")
async def startup():
    """Executado quando o servidor inicia."""
    logger.info({
        "event": "startup",
        "environment": ENVIRONMENT,
        "otel_enabled": OTEL_ENABLED,
        "scheduler_enabled": SCHEDULER_ENABLED,
        "frontend_url": FRONTEND_URL,
        "allowed_origins": ALLOWED_ORIGINS
    })
    
    migrations_success = False
    
    async def initialize():
        nonlocal migrations_success
        
        # 1. Conecta ao MongoDB
        logger.info("🔌 Conectando ao MongoDB...")
        await asyncio.wait_for(connect_to_mongo(), timeout=CONNECT_TIMEOUT)
        
        # 2. Verifica se conectou
        db = get_database()
        if db is None:
            raise RuntimeError("Banco de dados não conectado após connect_to_mongo()")
        logger.info("✅ MongoDB conectado com sucesso")
        
        # 3. Cria índices
        logger.info("📊 Criando/verificando índices...")
        await asyncio.wait_for(create_indexes(db), timeout=CONNECT_TIMEOUT)
        logger.info("✅ Índices criados/verificados")
        
        # 4. Executa migrações
        logger.info("🔄 Executando migrações...")
        try:
            await asyncio.wait_for(run_migrations(db), timeout=MIGRATION_TIMEOUT)
            migrations_success = True
            logger.info("✅ Migrações executadas com sucesso")
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout nas migrações ({MIGRATION_TIMEOUT}s)")
            migrations_success = False
            raise
        except Exception as e:
            logger.error(f"❌ Erro nas migrações: {e}", exc_info=True)
            migrations_success = False
            raise
    
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
        
        # 🔧 CORRIGIDO: Scheduler só inicia se migrações foram bem-sucedidas
        if SCHEDULER_ENABLED and migrations_success:
            try:
                global scheduler_instance
                scheduler_instance = start_scheduler()
                logger.info("✅ Scheduler iniciado com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao iniciar scheduler: {e}", exc_info=True)
        elif SCHEDULER_ENABLED and not migrations_success:
            logger.warning("⚠️ Scheduler não iniciado devido a falha nas migrações")
        else:
            logger.info("⏰ Scheduler desabilitado (SCHEDULER_ENABLED=false)")
        
        logger.info("✅ Velorium API pronta para uso!")
        
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout na inicialização (limite: {CONNECT_TIMEOUT}s)")
        raise RuntimeError("Banco de dados não respondeu dentro do tempo limite")
    except Exception as e:
        logger.error(f"❌ Erro fatal no startup: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown():
    """Executado quando o servidor desliga."""
    logger.info("🛑 Desligando Velorium API...")
    
    # 1. Para scheduler com timeout
    global scheduler_instance
    if scheduler_instance:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(stop_scheduler),
                timeout=SHUTDOWN_TIMEOUT
            )
            logger.info("✅ Scheduler parado")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Timeout ao parar scheduler ({SHUTDOWN_TIMEOUT}s)")
        except Exception as e:
            logger.error(f"❌ Erro ao parar scheduler: {e}", exc_info=True)
    
    # 2. Fecha conexão MongoDB com timeout
    try:
        await asyncio.wait_for(
            close_mongo_connection(),
            timeout=SHUTDOWN_TIMEOUT
        )
        logger.info("✅ Conexão MongoDB fechada")
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Timeout ao fechar MongoDB ({SHUTDOWN_TIMEOUT}s), forçando...")
    except Exception as e:
        logger.error(f"❌ Erro ao fechar MongoDB: {e}", exc_info=True)
    
    logger.info("✅ Desligamento concluído")


# ================================================================
# ROTAS (IMPORTS MANUAIS - MAIS CONFIÁVEL)
# ================================================================

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
    cache,
    categories,
    workers
)

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
app.include_router(cache.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")

# 🔧 CORRIGIDO: Importação segura da rota workers
try:
    from app.routes import workers
    app.include_router(workers.router, prefix="/api/v1")
    logger.info("✅ Rota de workers registrada")
except ModuleNotFoundError:
    logger.info("ℹ️ Rota de workers não disponível (módulo não encontrado)")
except Exception as e:
    logger.error(f"❌ Erro ao importar workers: {e}", exc_info=True)
    # Em produção, pode querer falhar aqui
    if ENVIRONMENT == "production":
        raise


# ================================================================
# ENDPOINTS PÚBLICOS
# ================================================================

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


@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe - verifica se o app está rodando."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe - verifica se o app está pronto para tráfego."""
    from app.database import health_check
    db_status = await health_check()
    
    if db_status.get("status") != "healthy":
        return {
            "status": "not_ready",
            "database": db_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, 503
    
    # Status do scheduler
    scheduler_status = "unknown"
    try:
        scheduler_status = get_scheduler_status()
    except Exception:
        pass
    
    return {
        "status": "ready",
        "database": db_status,
        "scheduler": scheduler_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health")
async def health():
    """Health check completo (compatibilidade)."""
    from app.database import health_check
    db_status = await health_check()
    
    scheduler_status = "unknown"
    try:
        scheduler_status = get_scheduler_status()
    except Exception:
        pass
    
    response = {
        "status": "ok",
        "database": db_status,
        "scheduler": scheduler_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if ENVIRONMENT == "development":
        response["environment"] = ENVIRONMENT
    
    return response


logger.info(f"✅ Velorium API configurada (Ambiente: {ENVIRONMENT})")