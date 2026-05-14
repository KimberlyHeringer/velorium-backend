"""
Rotas de Autenticação
Arquivo: backend/app/routes/auth.py
"""
"""
Rotas de Autenticação
Arquivo: backend/app/routes/auth.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, timezone
from typing import Annotated
import secrets

from app.database import get_database
from app.models.user import UserCreate, UserLogin, UserResponse
from app.utils.auth import (
    get_password_hash,
    verify_password,
    generate_token_pair,
    TokenPair,
    get_current_user
)

from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# ========== SCHEMAS PARA AUTENTICAÇÃO ==========

class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


# ========== SCHEMAS PARA RECUPERAÇÃO DE SENHA ==========

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


# ========== ENDPOINTS ==========

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db=Depends(get_database)):
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    hashed = get_password_hash(user_data.password)

    user_dict = user_data.model_dump(exclude={"password"})
    user_dict["password_hash"] = hashed
    user_dict["email"] = user_data.email.lower()
    user_dict["created_at"] = datetime.now(timezone.utc)
    user_dict["updated_at"] = datetime.now(timezone.utc)
    user_dict["monthly_income"] = round(user_dict["monthly_income"], 2)

    result = await db.users.insert_one(user_dict)
    return {"message": "Usuário criado com sucesso", "id": str(result.inserted_id)}


@router.post("/login", response_model=LoginResponse)
async def login(user_data: UserLogin, db=Depends(get_database)):
    db_user = await db.users.find_one({"email": user_data.email.lower()})
    if not db_user or not verify_password(user_data.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    token_pair = generate_token_pair(str(db_user["_id"]))

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
    from app.utils.auth import refresh_access_token, is_token_blacklisted
    
    # Verifica se o refresh token está na blacklist
    if await is_token_blacklisted(req.refresh_token, db):
        raise HTTPException(status_code=401, detail="Token revogado. Faça login novamente.")
    
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
    return current_user


@router.post("/logout", response_model=dict)
async def logout(
    refresh_token: str,  # recebido no corpo da requisição
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    from app.utils.auth import add_token_to_blacklist
    await add_token_to_blacklist(refresh_token, current_user.id, db)
    return {"message": "Logout realizado com sucesso. Token revogado."}


# ========== NOVOS ENDPOINTS: RECUPERAÇÃO DE SENHA ==========

@router.post("/forgot-password", response_model=dict)
async def forgot_password(
    request: ForgotPasswordRequest,
    db=Depends(get_database)
):
    """Gera um token de recuperação e envia email (mock)."""
    user = await db.users.find_one({"email": request.email})
    if not user:
        # Por segurança, não informar se o email existe
        return {"message": "Se o email estiver cadastrado, você receberá um link de redefinição."}
    
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "reset_token": token,
            "reset_token_expires": expires
        }}
    )
    
    # Para desenvolvimento: exibe o link no terminal do servidor
    reset_link = f"https://velorium-frontend.com/reset-password?token={token}"
    print(f"🔐 [MOCK] Link para redefinir senha: {reset_link}")
    
    # Em produção: enviar email real (SendGrid, SMTP, etc.)
    return {"message": "Se o email estiver cadastrado, você receberá um link de redefinição."}


@router.post("/reset-password", response_model=dict)
async def reset_password(
    request: ResetPasswordRequest,
    db=Depends(get_database)
):
    """Redefine a senha usando um token válido."""
    user = await db.users.find_one({
        "reset_token": request.token,
        "reset_token_expires": {"$gt": datetime.now(timezone.utc)}
    })
    if not user:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.")
    
    new_hash = get_password_hash(request.new_password)
    
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": new_hash,
            "reset_token": None,
            "reset_token_expires": None,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"message": "Senha alterada com sucesso."}