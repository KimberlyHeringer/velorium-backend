"""
Utilitários de autenticação sem bcrypt (usando cryptography)
"""

from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import os
import hashlib
import secrets
from dotenv import load_dotenv
from bson import ObjectId

from app.database import get_database
from app.models.user import UserResponse

load_dotenv()

# =============================================================================
# CONFIGURAÇÕES DE SEGURANÇA
# =============================================================================

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET não encontrada no .env!")

REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET", SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# =============================================================================
# FUNÇÕES DE HASH (SEM BCRYPT - USANDO HASHLIB)
# =============================================================================

def get_password_hash(password: str) -> str:
    """
    Gera hash da senha usando SHA-256 + salt.
    ⚠️ NOTA: Menos seguro que bcrypt, mas funciona em qualquer ambiente.
    """
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${hash_obj.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica a senha usando o mesmo método do hash.
    """
    try:
        salt, hash_value = hashed_password.split('$')
        test_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode(), salt.encode(), 100000).hex()
        return test_hash == hash_value
    except Exception:
        return False


# =============================================================================
# MODELOS DE TOKEN
# =============================================================================

class TokenData(BaseModel):
    user_id: Optional[str] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# =============================================================================
# FUNÇÕES DE TOKEN JWT
# =============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, is_refresh: bool = False) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        secret = REFRESH_SECRET_KEY if is_refresh else SECRET_KEY
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type", "access")
        
        if user_id is None:
            raise credentials_exception
        
        if is_refresh and token_type != "refresh":
            raise credentials_exception
        if not is_refresh and token_type != "access":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    return TokenData(user_id=user_id)


# =============================================================================
# DEPENDENCY PARA USUÁRIO ATUAL
# =============================================================================

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = decode_token(token, is_refresh=False)
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(token_data.user_id)})
    
    if user is None:
        raise credentials_exception
    
    user["_id"] = str(user["_id"])
    return UserResponse(**user)


async def get_current_active_user(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> UserResponse:
    return current_user


# =============================================================================
# UTILITÁRIOS DE AUTENTICAÇÃO
# =============================================================================

def generate_token_pair(user_id: str) -> TokenPair:
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


async def refresh_access_token(refresh_token: str) -> TokenPair:
    token_data = decode_token(refresh_token, is_refresh=True)
    return generate_token_pair(token_data.user_id)


# =============================================================================
# BLACKLIST DE REFRESH TOKENS
# =============================================================================

async def add_token_to_blacklist(token: str, user_id: str, db):
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    except Exception:
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    await db.refresh_token_blacklist.insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at
    })


async def is_token_blacklisted(token: str, db) -> bool:
    result = await db.refresh_token_blacklist.find_one({"token": token})
    return result is not None