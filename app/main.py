# ========== IMPORTS PRINCIPAIS ==========
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# ========== IMPORTS INTERNOS ==========
from app.database import connect_to_mongo, close_mongo_connection
from app.routes import auth, transactions, bills, credit_cards, credit_card_purchases, ia, profile  # <-- ADICIONADO PROFILE

# ========== CARREGAR VARIÁVEIS DE AMBIENTE ==========
load_dotenv()

# ========== INICIALIZAÇÃO DO APP ==========
app = FastAPI(title="Velorium API")

# ========== CONFIGURAÇÃO CORS ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens (ajustar em produção)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== EVENTOS DE CICLO DE VIDA ==========
@app.on_event("startup")
async def startup():
    """Conecta ao MongoDB quando o servidor inicia"""
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown():
    """Fecha conexão com MongoDB quando o servidor encerra"""
    await close_mongo_connection()

# ========== ROTAS DA API (PREFIXO /api/v1) ==========
app.include_router(auth.router, prefix="/api/v1")                     # Autenticação
app.include_router(transactions.router, prefix="/api/v1")             # Transações
app.include_router(bills.router, prefix="/api/v1")                    # Contas a pagar
app.include_router(credit_cards.router, prefix="/api/v1")             # Cartões de crédito
app.include_router(credit_card_purchases.router, prefix="/api/v1")    # Compras com cartão
app.include_router(ia.router, prefix="/api/v1")                       # Chat com IA (Veloria)
app.include_router(profile.router, prefix="/api/v1")                  # Perfil financeiro do usuário <-- NOVA ROTA

# ========== ENDPOINTS DE STATUS ==========
@app.get("/")
async def root():
    return {"message": "Velorium API - Online"}

@app.get("/health")
async def health():
    return {"status": "ok"}