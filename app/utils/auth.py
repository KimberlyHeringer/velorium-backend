# backend/app/utils/auth.py
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

load_dotenv()

# =============================================================================
# CONFIGURAÇÕES DE SEGURANÇA (OBRIGATÓRIAS)
# =============================================================================

# Secret Key é OBRIGATÓRIA - não permite fallback inseguro
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise ValueError(
        "JWT_SECRET não encontrada no .env! "
        "Esta variável é obrigatória para segurança da API."
    )

# Chave para Refresh Token (opcional, mas recomendado)
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET", SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30 minutos (segurança financeira)
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 7 dias para refresh

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
# FUNÇÕES DE SENHA
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha plain corresponde ao hash armazenado.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera hash seguro da senha usando bcrypt.
    """
    return pwd_context.hash(password)


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
            raise credentials_exception
        
        # Valida que o tipo de token está correto
        if is_refresh and token_type != "refresh":
            raise credentials_exception
        if not is_refresh and token_type != "access":
            raise credentials_exception
            
    except JWTError as e:
        raise credentials_exception
    
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
        raise credentials_exception
    
    # Converter para UserResponse (exclui password_hash automaticamente)
    user["_id"] = str(user["_id"])
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
    
    # Gerar novo par
    return generate_token_pair(token_data.user_id)