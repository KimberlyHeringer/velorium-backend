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

router = APIRouter(prefix="/auth", tags=["Autenticação"])


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
    
    # Converter Decimal para float (MongoDB não aceita Decimal)
    user_dict["monthly_income"] = float(user_dict["monthly_income"])

    result = await db.users.insert_one(user_dict)
    return {"message": "Usuário criado com sucesso", "id": str(result.inserted_id)}


@router.post("/login", response_model=dict)  # Altere o response_model para dict
async def login(user_data: UserLogin, db=Depends(get_database)):
    db_user = await db.users.find_one({"email": user_data.email.lower()})
    if not db_user or not verify_password(user_data.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    token_pair = generate_token_pair(str(db_user["_id"]))

    # Converter ObjectId para string
    db_user["_id"] = str(db_user["_id"])
    # Remover campos sensíveis
    del db_user["password_hash"]

    return {
        "access_token": token_pair.access_token,
        "refresh_token": token_pair.refresh_token,
        "token_type": "bearer",
        "expires_in": token_pair.expires_in,
        "user": db_user  # ✅ inclui os dados do usuário
    }


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(refresh_token_data: dict, db=Depends(get_database)):
    from app.utils.auth import refresh_access_token
    refresh_token = refresh_token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token não fornecido")
    try:
        return await refresh_access_token(refresh_token)
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
async def logout(current_user: Annotated[UserResponse, Depends(get_current_user)]):
    # Em produção: adicionar token a uma blacklist
    return {"message": "Logout realizado com sucesso. Descarte os tokens no cliente."}