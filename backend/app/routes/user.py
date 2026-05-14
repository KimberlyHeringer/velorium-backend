"""
Rotas de Usuário (Perfil, Senha, Consentimento, Preferências)
Arquivo: backend/app/routes/user.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.user import UserResponse, UserUpdate
from app.utils.auth import get_current_user, get_password_hash, verify_password

router = APIRouter(prefix="/users", tags=["Usuário"])


# ========== SCHEMAS ==========

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class PreferencesUpdate(BaseModel):
    language: Optional[str] = None   # pt, en, es, zh
    currency: Optional[str] = None   # BRL, USD, EUR, CNY


# ========== ENDPOINTS DE PERFIL ==========

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    update_data = {}
    if profile_data.name is not None:
        update_data["name"] = profile_data.name
    if profile_data.email is not None:
        update_data["email"] = profile_data.email.lower()
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    if "email" in update_data:
        existing = await db.users.find_one({"email": update_data["email"]})
        if existing and str(existing["_id"]) != str(current_user.id):
            raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    updated_user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    updated_user["_id"] = str(updated_user["_id"])
    return UserResponse(**updated_user)


@router.put("/change-password", response_model=dict)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if not verify_password(password_data.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Senha atual incorreta")
    
    new_hash = get_password_hash(password_data.new_password)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Senha alterada com sucesso"}


# ========== ENDPOINTS DE PREFERÊNCIAS ==========

@router.get("/preferences", response_model=dict)
async def get_preferences(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna as preferências do usuário (idioma, moeda)"""
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {
        "language": user.get("language", "pt"),
        "currency": user.get("currency", "BRL")
    }


@router.put("/preferences", response_model=dict)
async def update_preferences(
    prefs: PreferencesUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza as preferências do usuário (idioma, moeda)"""
    update_data = {}
    if prefs.language is not None:
        if prefs.language not in ["pt", "en", "es", "zh"]:
            raise HTTPException(status_code=400, detail="Idioma inválido")
        update_data["language"] = prefs.language
    if prefs.currency is not None:
        if prefs.currency not in ["BRL", "USD", "EUR", "CNY"]:
            raise HTTPException(status_code=400, detail="Moeda inválida")
        update_data["currency"] = prefs.currency
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhuma preferência para atualizar")
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    return {"message": "Preferências atualizadas com sucesso"}


# ========== ENDPOINTS DE CONSENTIMENTO ==========

class ConsentUpdate(BaseModel):
    terms_accepted: bool
    research_consent: bool


class ConsentStatusResponse(BaseModel):
    terms_accepted: bool
    research_consent: bool
    terms_accepted_at: Optional[datetime] = None


@router.put("/consent", response_model=dict)
async def update_consent(
    consent_data: ConsentUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    update_fields = {
        "research_consent": consent_data.research_consent,
        "updated_at": datetime.now(timezone.utc),
        "consent_updated_at": datetime.now(timezone.utc)
    }
    if consent_data.terms_accepted:
        update_fields["terms_accepted"] = True
        update_fields["terms_accepted_at"] = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail="Os Termos de Uso não podem ser desmarcados depois de aceitos.")
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_fields}
    )
    return {"message": "Consentimento atualizado com sucesso"}


@router.get("/consent-status", response_model=ConsentStatusResponse)
async def get_consent_status(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return ConsentStatusResponse(
        terms_accepted=user.get("terms_accepted", False),
        research_consent=user.get("research_consent", False),
        terms_accepted_at=user.get("terms_accepted_at")
    )

# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Endpoint PUT /users/profile: atualiza nome e email
# ✅ Endpoint PUT /users/change-password: altera senha com validação da senha atual
# ✅ Verificação de email duplicado ao alterar email
# ✅ Normalização do email (lowercase)
# ✅ Atualização do campo updated_at
# ✅ Comentários explicativos