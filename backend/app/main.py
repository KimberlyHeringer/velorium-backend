"""
Arquivo principal do backend Velorium
Ponto de entrada da API FastAPI
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_helmet import HelmetMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv

from app.database import connect_to_mongo, close_mongo_connection, create_indexes
from app.routes import auth, transactions, bills, credit_cards, credit_card_purchases, ia, profile, score, goals, user
from app.routes import achievements  
from app.utils.rate_limiter import init_rate_limiter

# Carrega variáveis de ambiente
load_dotenv()


# ========== #35 - SANITIZAÇÃO DE SAÍDA (prevenir XSS) ==========
class SanitizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware que sanitiza respostas JSON para prevenir XSS.
    Remove ou escapa caracteres perigosos: < > & ' "
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.patterns = [
            (re.compile(r'&'), '&amp;'),
            (re.compile(r'<'), '&lt;'),
            (re.compile(r'>'), '&gt;'),
            (re.compile(r'"'), '&quot;'),
            (re.compile(r"'"), '&#x27;'),
        ]
    
    def sanitize_string(self, value):
        if isinstance(value, str):
            for pattern, replacement in self.patterns:
                value = pattern.sub(replacement, value)
        return value
    
    def sanitize_dict(self, obj):
        if isinstance(obj, dict):
            return {key: self.sanitize_dict(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self.sanitize_dict(item) for item in obj]
        elif isinstance(obj, str):
            return self.sanitize_string(obj)
        else:
            return obj
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        if 200 <= response.status_code < 300:
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = b""
                    async for chunk in response.body_iterator:
                        body += chunk
                    
                    data = json.loads(body.decode('utf-8'))
                    sanitized_data = self.sanitize_dict(data)
                    sanitized_body = json.dumps(sanitized_data, ensure_ascii=False).encode('utf-8')
                    
                    return Response(
                        content=sanitized_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
                except Exception:
                    pass
        
        return response


# Cria a aplicação FastAPI
app = FastAPI(
    title="Velorium API",
    description="API do app de gestão financeira Velorium",
    version="1.0.0"
)

# ========== #34 - HELMET (headers de segurança) ==========
app.add_middleware(FastAPIHelmet)

# ========== #36 - COMPRESSÃO GZIP ==========
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ========== #35 - SANITIZAÇÃO XSS ==========
app.add_middleware(SanitizeMiddleware)

# ========== INICIALIZA RATE LIMITER ==========
init_rate_limiter(app)

# ========== CONFIGURAÇÃO DO CORS ==========
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8081")

if os.getenv("PRODUCTION", "false").lower() == "true":
    allowed_origins = [FRONTEND_URL]
    print(f"🔒 CORS em modo produção: {allowed_origins}")
else:
    allowed_origins = [
        "http://localhost:8081",
        "http://localhost:3000",
        "http://localhost:19006",
        FRONTEND_URL
    ]
    print(f"🛠️ CORS em modo desenvolvimento: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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