"""
Rotas de Autenticação
Arquivo: backend/app/routes/auth.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from typing import Annotated

from app.database import get_database
from app.models.user import UserCreate, UserLogin, UserResponse
from app.utils.auth import (
    get_password_hash,
    verify_password,
    generate_token_pair,
    TokenPair,
    get_current_user
)

from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# ========== SCHEMAS PARA AUTENTICAÇÃO ==========

class RefreshTokenRequest(BaseModel):
    """Schema para requisição de refresh token"""
    refresh_token: str


class LoginResponse(BaseModel):
    """Schema para resposta de login bem-sucedido"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


# ========== ENDPOINTS ==========

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db=Depends(get_database)):
    # Verificar se email já existe
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    # Criar hash da senha
    hashed = get_password_hash(user_data.password)

    # Preparar documento
    user_dict = user_data.model_dump(exclude={"password"})
    user_dict["password_hash"] = hashed
    user_dict["email"] = user_data.email.lower()
    user_dict["created_at"] = datetime.now(timezone.utc)
    user_dict["updated_at"] = datetime.now(timezone.utc)
    
    # Converter Decimal para float (MongoDB não aceita Decimal) e arredondar
    user_dict["monthly_income"] = round(user_dict["monthly_income"], 2)

    result = await db.users.insert_one(user_dict)
    return {"message": "Usuário criado com sucesso", "id": str(result.inserted_id)}


@router.post("/login", response_model=LoginResponse)
async def login(user_data: UserLogin, db=Depends(get_database)):
    db_user = await db.users.find_one({"email": user_data.email.lower()})
    if not db_user or not verify_password(user_data.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    token_pair = generate_token_pair(str(db_user["_id"]))

    # Constrói UserResponse seguro (sem campos sensíveis)
    user_response = UserResponse(
        id=str(db_user["_id"]),
        name=db_user["name"],
        email=db_user["email"],
        monthly_income=db_user.get("monthly_income", 0.0),
        location=db_user.get("location", ""),
        profession_type=db_user.get("profession_type", ""),
        occupation=db_user.get("occupation", ""),
        financial_goal=db_user.get("financial_goal", ""),
        created_at=db_user["created_at"]
    )

    return LoginResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
        user=user_response
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(req: RefreshTokenRequest, db=Depends(get_database)):
    """Renova o access token usando um refresh token válido"""
    from app.utils.auth import refresh_access_token
    try:
        return await refresh_access_token(req.refresh_token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token inválido ou expirado")


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
):
    """Retorna o perfil do usuário autenticado"""
    return current_user


@router.post("/logout", response_model=dict)
async def logout(current_user: Annotated[UserResponse, Depends(get_current_user)]):
    """Realiza logout (no MVP apenas descarta tokens no cliente)"""
    # Em produção: adicionar token a uma blacklist (Redis)
    return {"message": "Logout realizado com sucesso. Descarte os tokens no cliente."}