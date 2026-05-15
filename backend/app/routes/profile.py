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
from app.models.profile import UserProfileCreate, UserProfileResponse
from app.database import get_database

router = APIRouter(prefix="/profile", tags=["Perfil Financeiro"])


# ========== FUNÇÃO AUXILIAR PADRONIZADA ==========
def format_doc(doc: dict) -> dict:
    """Converte _id para id e padroniza resposta"""
    if doc and "_id" in doc:
        result = dict(doc)
        result["id"] = str(result.pop("_id"))
        return result
    return doc


# ========== ENDPOINTS ==========

@router.get("/", response_model=Optional[UserProfileResponse])
async def get_profile(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Retorna o perfil financeiro do usuário"""
    profile = await db.user_profiles.find_one({"user_id": str(current_user.id)})
    if not profile:
        return None
    return format_doc(profile)


@router.post("/", response_model=UserProfileResponse)
async def save_profile(
    profile_data: UserProfileCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Cria ou atualiza o perfil financeiro do usuário"""
    existing = await db.user_profiles.find_one({"user_id": str(current_user.id)})
    now = datetime.now(timezone.utc)
    
    profile_dict = profile_data.model_dump(exclude_unset=True)
    profile_dict["user_id"] = str(current_user.id)
    profile_dict["updated_at"] = now

    if existing:
        await db.user_profiles.update_one(
            {"_id": existing["_id"]},
            {"$set": profile_dict}
        )
        profile_dict["_id"] = existing["_id"]
        profile_dict["created_at"] = existing.get("created_at", now)
    else:
        profile_dict["created_at"] = now
        result = await db.user_profiles.insert_one(profile_dict)
        profile_dict["_id"] = result.inserted_id
    
    return format_doc(profile_dict)

# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Usa Depends(get_database) (consistência com outras rotas)
# ✅ Adicionado profile_dict["id"] = profile_dict["_id"] (clareza)
# ✅ Função auxiliar format_profile_doc()
# ✅ Comentários explicativos
#
# 📌 Observação: campos monetários como dream_value continuam como string
#    (pode ser migrado para número no futuro, se necessário)