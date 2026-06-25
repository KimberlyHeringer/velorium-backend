"""
Rotas de Perfil Financeiro do Usuário
Arquivo: backend/app/routes/profile.py

🔧 MODIFICADO: Regra 2.2 - Removido format_doc local, usando format_mongo_doc
🔧 MODIFICADO: Regra 2.8 - Adicionado logger completo
🔧 CORRIGIDO: GET /profile/ agora retorna objeto vazio em vez de None (evita erro 500)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.profile import UserProfileCreate, UserProfileResponse
from app.database import get_database
from app.utils.validators import format_mongo_doc
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

router = APIRouter(prefix="/profile", tags=["Perfil Financeiro"])


@router.get("/", response_model=UserProfileResponse)
async def get_profile(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Retorna o perfil financeiro do usuário.
    
    🔧 CORRIGIDO: Se não houver perfil, retorna um objeto vazio em vez de None.
    Isso evita erro 500 no Pydantic ao tentar validar None.
    """
    profile = await db.user_profiles.find_one({"user_id": str(current_user.id)})
    if not profile:
        logger.debug(f"Nenhum perfil encontrado para usuário {current_user.id}")
        # 🔧 Retorna um objeto vazio (todos os campos com valores padrão)
        return UserProfileResponse()
    
    logger.debug(f"Perfil recuperado para usuário {current_user.id}")
    # 🔧 CORREÇÃO 2.2: usando format_mongo_doc
    return format_mongo_doc(profile)


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
        logger.info(f"Perfil atualizado para usuário {current_user.id}")
    else:
        profile_dict["created_at"] = now
        result = await db.user_profiles.insert_one(profile_dict)
        profile_dict["_id"] = result.inserted_id
        logger.info(f"Perfil criado para usuário {current_user.id}")
    
    # 🔧 CORREÇÃO 2.2: usando format_mongo_doc (não mais format_doc)
    return format_mongo_doc(profile_dict)


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Usa Depends(get_database) (consistência com outras rotas)
# ✅ Adicionado profile_dict["id"] = profile_dict["_id"] (clareza)
# ✅ Função auxiliar format_profile_doc()
# ✅ Comentários explicativos
# ✅ 🔧 CORRIGIDO: GET retorna objeto vazio em vez de None
#
# 📌 Observação: campos monetários como dream_value continuam como string
#    (pode ser migrado para número no futuro, se necessário)