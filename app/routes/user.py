"""
Rotas de Usuário (Perfil, Senha, etc.)
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
    """Schema para atualização de nome e email"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    """Schema para alteração de senha"""
    current_password: str
    new_password: str


# ========== ENDPOINTS ==========

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Atualiza o nome e/ou email do usuário autenticado.
    """
    # Prepara os dados para atualização
    update_data = {}
    if profile_data.name is not None:
        update_data["name"] = profile_data.name
    if profile_data.email is not None:
        # Normaliza o email (lowercase)
        update_data["email"] = profile_data.email.lower()
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum dado para atualizar"
        )
    
    # Se o email está sendo alterado, verifica se já não existe
    if "email" in update_data:
        existing = await db.users.find_one({"email": update_data["email"]})
        if existing and str(existing["_id"]) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado por outro usuário"
            )
    
    # Atualiza o usuário
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    # Busca o usuário atualizado
    updated_user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    updated_user["_id"] = str(updated_user["_id"])
    
    return UserResponse(**updated_user)


@router.put("/change-password", response_model=dict)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Altera a senha do usuário autenticado.
    Requer a senha atual para validação.
    """
    # Busca o usuário no banco (para obter o hash da senha)
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Verifica se a senha atual está correta
    if not verify_password(password_data.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha atual incorreta"
        )
    
    # Gera o hash da nova senha
    new_password_hash = get_password_hash(password_data.new_password)
    
    # Atualiza a senha
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {
            "password_hash": new_password_hash,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"message": "Senha alterada com sucesso"}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Endpoint PUT /users/profile: atualiza nome e email
# ✅ Endpoint PUT /users/change-password: altera senha com validação da senha atual
# ✅ Verificação de email duplicado ao alterar email
# ✅ Normalização do email (lowercase)
# ✅ Atualização do campo updated_at
# ✅ Comentários explicativos