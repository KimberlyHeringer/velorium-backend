"""
Arquivo principal do backend Velorium
Ponto de entrada da API FastAPI
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection, create_indexes
from app.routes import auth, transactions, bills, credit_cards, credit_card_purchases, ia, profile, score, goals, user

# Carrega variáveis de ambiente
load_dotenv()

# Cria a aplicação FastAPI
app = FastAPI(
    title="Velorium API",
    description="API do app de gestão financeira Velorium",
    version="1.0.0"
)

# ========== CONFIGURAÇÃO DO CORS ==========
# ⚠️ ATENÇÃO: Em produção, troque pela URL real do seu frontend!
# Exemplo: allow_origins=["https://velorium-frontend.onrender.com"]

# Pega a URL do frontend do ambiente (ou usa padrão para desenvolvimento)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8081")

# Em desenvolvimento, pode usar localhost
# Em produção, use a URL real
if os.getenv("PRODUCTION", "false").lower() == "true":
    # PRODUÇÃO: use apenas a URL real
    allowed_origins = [FRONTEND_URL]
    print(f"🔒 CORS em modo produção: {allowed_origins}")
else:
    # DESENVOLVIMENTO: permite localhost para testes
    allowed_origins = [
        "http://localhost:8081",   # Expo web
        "http://localhost:3000",   # React Native web
        "http://localhost:19006",  # Expo default
        FRONTEND_URL               # Se tiver outra configurada
    ]
    print(f"🛠️ CORS em modo desenvolvimento: {allowed_origins}")

# Adiciona middleware CORS
# NUNCA use allow_origins=["*"] com allow_credentials=True em produção
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,           # ← URLs específicas, não "*"
    allow_credentials=True,                  # Permite enviar cookies/tokens
    allow_methods=["*"],                     # Permite todos os métodos HTTP
    allow_headers=["*"],                     # Permite todos os headers
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
# Todas as rotas estão prefixadas com /api/v1
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
        "timestamp": "2025-05-01"
    }