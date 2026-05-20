"""
Arquivo principal do backend Velorium
Ponto de entrada da API FastAPI
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection, create_indexes
from app.routes import auth, transactions, bills, credit_cards, credit_card_purchases, ia, profile, score, goals, user
from app.routes import achievements  
from app.utils.rate_limiter import init_rate_limiter

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

print(f"🔧 CORS configurado para permitir todas as origens (TEMPORÁRIO PARA TESTE)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== EVENTOS DE INICIALIZAÇÃO E DESLIGAMENTO ==========
@app.on_event("startup")
async def startup():
    """Executado quando o servidor inicia"""
    print("🚀 Iniciando Velorium API...")
    await connect_to_mongo()
    await create_indexes()
    print("✅ Velorium API pronta para uso!")


@app.on_event("shutdown")
async def shutdown():
    """Executado quando o servidor desliga"""
    print("🛑 Desligando Velorium API...")
    await close_mongo_connection()
    print("✅ Desligamento concluído")


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