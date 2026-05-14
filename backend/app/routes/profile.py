"""
Rotas de Perfil Financeiro do Usuário
Arquivo: backend/app/routes/profile.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.profile import UserProfile, UserProfileCreate, UserProfileResponse
from app.database import get_database

router = APIRouter(prefix="/profile", tags=["Perfil Financeiro"])


# ========== FUNÇÃO AUXILIAR ==========

def format_profile_doc(profile: dict) -> dict:
    """
    Converte _id para id e garante que o campo id esteja presente.
    """
    if profile and "_id" in profile:
        profile["id"] = str(profile["_id"])
    return profile


# ========== ENDPOINTS ==========

@router.get("/", response_model=Optional[UserProfileResponse])
async def get_profile(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Retorna o perfil financeiro do usuário (ou None se não existir)"""
    profile = await db.user_profiles.find_one({"user_id": current_user.id})
    if not profile:
        return None
    return format_profile_doc(profile)


@router.post("/", response_model=UserProfileResponse)
async def save_profile(
    profile_data: UserProfileCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Cria ou atualiza o perfil financeiro do usuário (upsert).
    """
    existing = await db.user_profiles.find_one({"user_id": current_user.id})
    now = datetime.now(timezone.utc)
    
    # Prepara os dados do perfil (sem campos autogerados)
    profile_dict = profile_data.model_dump(exclude_unset=True)
    profile_dict["user_id"] = current_user.id
    profile_dict["updated_at"] = now

    if existing:
        # Atualiza perfil existente
        await db.user_profiles.update_one(
            {"_id": existing["_id"]},
            {"$set": profile_dict}
        )
        profile_dict["_id"] = str(existing["_id"])
        profile_dict["created_at"] = existing.get("created_at", now)
    else:
        # Cria novo perfil
        profile_dict["created_at"] = now
        result = await db.user_profiles.insert_one(profile_dict)
        profile_dict["_id"] = str(result.inserted_id)
    
    # Garante que o campo id esteja presente (consistência com response_model)
    profile_dict["id"] = profile_dict["_id"]
    
    return profile_dict


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Usa Depends(get_database) (consistência com outras rotas)
# ✅ Adicionado profile_dict["id"] = profile_dict["_id"] (clareza)
# ✅ Função auxiliar format_profile_doc()
# ✅ Comentários explicativos
#
# 📌 Observação: campos monetários como dream_value continuam como string
#    (pode ser migrado para número no futuro, se necessário)