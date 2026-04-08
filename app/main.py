from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection
from app.routes import auth, transactions, bills, credit_cards, credit_card_purchases, ia

load_dotenv()

app = FastAPI(title="Velorium API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Eventos de inicialização e encerramento
@app.on_event("startup")
async def startup():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()

# Incluir rotas (todas com prefixo /api/v1)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(bills.router, prefix="/api/v1")
app.include_router(credit_cards.router, prefix="/api/v1")
app.include_router(credit_card_purchases.router, prefix="/api/v1")
app.include_router(ia.router, prefix="/api/v1")   # <--- rota da IA

@app.get("/")
async def root():
    return {"message": "Velorium API - Online"}

@app.get("/health")
async def health():
    return {"status": "ok"}