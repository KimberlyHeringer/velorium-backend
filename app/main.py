from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

# Configuração MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client.finance_app

app = FastAPI(title="API Financeira Inteligente")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Importar rotas (vamos criar depois)
from app.routes import auth

# Incluir rotas
app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])

@app.get("/")
async def root():
    return {"message": "API Financeira Inteligente - Online"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "database": "connected" if client else "disconnected"}
