# backend/app/utils/auth.py
"""
Utilitários de Autenticação (JWT, Hash, Blacklist)
Arquivo: backend/app/utils/auth.py

🔧 MODIFICADO: Regra 2.8 - Adicionado logger para rastreamento de eventos de autenticação
"""

from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from bson import ObjectId

from app.database import get_database
from app.models.user import UserResponse
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

load_dotenv()

# =============================================================================
# CONFIGURAÇÕES DE SEGURANÇA (OBRIGATÓRIAS)
# =============================================================================

# Secret Key é OBRIGATÓRIA - não permite fallback inseguro
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    logger.error("JWT_SECRET não encontrada no .env!")
    raise ValueError(
        "JWT_SECRET não encontrada no .env! "
        "Esta variável é obrigatória para segurança da API."
    )

# Chave para Refresh Token (opcional, mas recomendado)
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET", SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30 minutos (segurança financeira)
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 7 dias para refresh

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# =============================================================================
# MODELOS DE TOKEN
# =============================================================================

class TokenData(BaseModel):
    """Dados extraídos do token JWT"""
    user_id: Optional[str] = None


class TokenPair(BaseModel):
    """Par de tokens (access + refresh)"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos até expiração do access token


# =============================================================================
# FUNÇÃO AUXILIAR PARA TRUNCAR SENHA (LIMITE DE 72 BYTES DO BCRYPT)
# =============================================================================

def _truncate_password(password: str) -> str:
    """
    Trunca a senha para 72 bytes devido à limitação do bcrypt.
    Isso evita o erro "password cannot be longer than 72 bytes".
    """
    if isinstance(password, str):
        # Converte para bytes, trunca nos primeiros 72 bytes, e volta para string
        truncated_bytes = password.encode('utf-8')[:72]
        return truncated_bytes.decode('utf-8', errors='ignore')
    return password


# =============================================================================
# FUNÇÕES DE SENHA (CORRIGIDAS PARA LIMITE DE 72 BYTES)
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha plain corresponde ao hash armazenado.
    🔧 CORRIGIDO: Trunca a senha para 72 bytes para compatibilidade com bcrypt.
    """
    truncated_password = _truncate_password(plain_password)
    result = pwd_context.verify(truncated_password, hashed_password)
    
    if not result:
        logger.debug("Falha na verificação de senha")
    return result


def get_password_hash(password: str) -> str:
    """
    Gera hash seguro da senha usando bcrypt.
    🔧 CORRIGIDO: Trunca a senha para 72 bytes antes de fazer o hash.
    """
    truncated_password = _truncate_password(password)
    hash_result = pwd_context.hash(truncated_password)
    logger.debug("Hash de senha gerado com sucesso")
    return hash_result


# =============================================================================
# FUNÇÕES DE TOKEN JWT
# =============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria um access token JWT com expiração curta.
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Access token criado para usuário: {data.get('sub', 'unknown')}")
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Cria um refresh token JWT com expiração longa.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Refresh token criado para usuário: {data.get('sub', 'unknown')}")
    return encoded_jwt


def decode_token(token: str, is_refresh: bool = False) -> TokenData:
    """
    Decodifica e valida um token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Usa chave diferente para refresh token
        secret = REFRESH_SECRET_KEY if is_refresh else SECRET_KEY
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type", "access")
        
        if user_id is None:
            logger.warning("Token sem campo 'sub' (user_id)")
            raise credentials_exception
        
        # Valida que o tipo de token está correto
        if is_refresh and token_type != "refresh":
            logger.warning(f"Tentativa de usar token {token_type} como refresh")
            raise credentials_exception
        if not is_refresh and token_type != "access":
            logger.warning(f"Tentativa de usar token {token_type} como access")
            raise credentials_exception
            
    except JWTError as e:
        logger.warning(f"Erro ao decodificar token: {e}")
        raise credentials_exception
    
    logger.debug(f"Token decodificado com sucesso para usuário: {user_id}")
    return TokenData(user_id=user_id)


# =============================================================================
# DEPENDENCY PARA USUÁRIO ATUAL
# =============================================================================

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    """
    Dependency que valida o token e retorna o usuário atual.
    Retorna UserResponse (SEM password_hash) para segurança.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decodificar token
    token_data = decode_token(token, is_refresh=False)
    
    # Buscar usuário no banco
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(token_data.user_id)})
    
    if user is None:
        logger.warning(f"Usuário não encontrado para token: {token_data.user_id}")
        raise credentials_exception
    
    # Converter para UserResponse (exclui password_hash automaticamente)
    user["_id"] = str(user["_id"])
    logger.debug(f"Usuário autenticado: {user['email']} (ID: {user['_id']})")
    return UserResponse(**user)


async def get_current_active_user(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> UserResponse:
    """
    Dependency que verifica se o usuário está ativo.
    Pode ser expandido para verificar status de conta, banimento, etc.
    """
    # Aqui você pode adicionar verificações adicionais
    # Ex: if current_user.is_active is False: raise HTTPException(...)
    return current_user


# =============================================================================
# UTILITÁRIOS DE AUTENTICAÇÃO
# =============================================================================

def generate_token_pair(user_id: str) -> TokenPair:
    """
    Gera par de tokens (access + refresh) para um usuário.
    """
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    logger.info(f"Par de tokens gerado para usuário: {user_id}")
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


async def refresh_access_token(refresh_token: str) -> TokenPair:
    """
    Usa o refresh token para gerar um novo par de tokens.
    """
    # Validar refresh token
    token_data = decode_token(refresh_token, is_refresh=True)
    
    logger.info(f"Refresh token válido, gerando novo par para usuário: {token_data.user_id}")
    # Gerar novo par
    return generate_token_pair(token_data.user_id)


# =============================================================================
# BLACKLIST DE REFRESH TOKENS (para logout real)
# =============================================================================

async def add_token_to_blacklist(token: str, user_id: str, db):
    """
    Adiciona um refresh token à blacklist.
    A expiração é extraída do próprio token (campo 'exp').
    Se não conseguir decodificar, usa expiração padrão de REFRESH_TOKEN_EXPIRE_DAYS.
    """
    try:
        # Decodifica sem verificar expiração para obter o timestamp de expiração
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    except Exception as e:
        logger.warning(f"Erro ao decodificar token para blacklist: {e}")
        # Fallback seguro
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    await db.refresh_token_blacklist.insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at
    })
    
    logger.info(f"Refresh token adicionado à blacklist para usuário: {user_id}")


async def is_token_blacklisted(token: str, db) -> bool:
    """Verifica se o refresh token está na blacklist."""
    result = await db.refresh_token_blacklist.find_one({"token": token})
    
    if result:
        logger.debug(f"Token encontrado na blacklist")
        return True
    
    return False