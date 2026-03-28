# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import connect_to_mongo, close_mongo_connection
from app.routes import auth, transactions
import os
from dotenv import load_dotenv
load_dotenv()
from app.routes import bills
app.include_router(bills.router, prefix="/api/v1")

app = FastAPI(title="Velorium API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restrinja para seu frontend
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

app.include_router(auth.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Velorium API - Online"}

@app.get("/health")
async def health():
    return {"status": "ok"}
