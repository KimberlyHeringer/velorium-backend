"""
Arquivo principal do backend Velorium
Ponto de entrada da API FastAPI
Arquivo: backend/main.py

🔧 MODIFICADO: Regra 2.8 - Logs
- Substituído print por logger.info/error
- Adicionado logger configurado

🔧 MODIFICADO: Regra 3.1 - Score Financeiro
- Adicionado scheduler APScheduler para worker diário (03:00)
- Adicionada função start_score_scheduler()
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

from app.database import connect_to_mongo, close_mongo_connection, create_indexes
from app.routes import auth, transactions, bills, credit_cards, credit_card_purchases, ia, profile, score, goals, user, investments
from app.routes import achievements  
from app.utils.rate_limiter import init_rate_limiter
from app.utils.logger import setup_logger
from workers.score_worker import run_score_worker_sync

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# Cria a aplicação FastAPI
app = FastAPI(
    title="Velorium API",
    description="API do app de gestão financeira Velorium",
    version="1.0.0"
)

# ========== INICIALIZA RATE LIMITER ==========
init_rate_limiter(app)

# ========== CONFIGURAÇÃO DO CORS ==========
# 🔧 TEMPORARIAMENTE: permite todas as origens para resolver o problema de conexão
# ⚠️ DEPOIS DOS TESTES, REVERTA PARA A CONFIGURAÇÃO ORIGINAL
allowed_origins = ["*"]

logger.info("🔧 CORS configurado para permitir todas as origens (TEMPORÁRIO PARA TESTE)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== FUNÇÃO PARA INICIAR SCHEDULER ==========
def start_score_scheduler():
    """
    Inicia o scheduler para executar worker de score diariamente às 03:00
    🔧 REGRA 3.1: Score Financeiro - Worker Diário
    """
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    
    # Agenda o job para rodar todos os dias às 03:00
    scheduler.add_job(
        func=run_score_worker_sync,
        trigger="cron",
        hour=3,
        minute=0,
        id="score_daily_worker",
        replace_existing=True,
        misfire_grace_time=3600  # 1 hora de tolerância se o scheduler estava off
    )
    
    scheduler.start()
    logger.info("⏰ Scheduler de score iniciado! Executará diariamente às 03:00")
    
    # Garante que o scheduler será desligado ao final do processo
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler


# ========== EVENTOS DE INICIALIZAÇÃO E DESLIGAMENTO ==========
@app.on_event("startup")
async def startup():
    """Executado quando o servidor inicia"""
    logger.info("🚀 Iniciando Velorium API...")
    await connect_to_mongo()
    await create_indexes()
    
    # 🔧 REGRA 3.1: Iniciar scheduler de score
    start_score_scheduler()
    
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
app.include_router(credit_cards.router, prefix="/api/v1")
app.include_router(credit_card_purchases.router, prefix="/api/v1")
app.include_router(ia.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(score.router, prefix="/api/v1")
app.include_router(goals.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(achievements.router, prefix="/api/v1")
app.include_router(investments.router, prefix="/api/v1")


# ========== ENDPOINTS PÚBLICOS ==========
@app.get("/")
async def root():
    """Endpoint raiz para verificar se a API está no ar"""
    return {
        "message": "Velorium API - Online",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health():
    """Endpoint de saúde para monitoramento (ex: Render.com)"""
    from app.database import health_check
    db_status = await health_check()
    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }