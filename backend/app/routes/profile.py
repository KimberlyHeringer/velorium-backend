"""
Rotas de Perfil Financeiro do Usuário
Arquivo: backend/app/routes/profile.py

Funcionalidades:
- GET /profile: Buscar perfil financeiro do usuário
- POST /profile: Criar/atualizar perfil financeiro do usuário

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (get: 30/min, post: 20/min)
- Validação de campos Literal via Pydantic
- Validação de existência do usuário no POST
- Fallback seguro para perfil vazio
- SEM history (modo individual)

Versão: v4.1 (corrigido)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.profile import UserProfileCreate, UserProfileResponse
from app.database import get_database
from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger

# ========== NOVOS IMPORTS ==========
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.profile_utils import (
    create_empty_profile,
    prepare_profile_response,
    ensure_profile_collection
)

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/profile", tags=["Perfil Financeiro"])


# ========== ENDPOINTS ==========

@router.get("/", response_model=UserProfileResponse)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_profile(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Retorna o perfil financeiro do usuário.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    logger.info(f"🔍 Buscando perfil para usuário: {current_user.id}")
    
    try:
        await ensure_profile_collection(db)
        
        profile = await db.user_profiles.find_one({"user_id": str(current_user.id)})
        logger.info(f"📝 Perfil encontrado: {profile is not None}")
        
        result = prepare_profile_response(profile, str(current_user.id))
        
        if not result:
            logger.warning(f"⚠️ prepare_profile_response retornou vazio para usuário {current_user.id}")
            result = create_empty_profile(str(current_user.id))
        
        logger.debug(f"✅ Perfil recuperado para usuário {current_user.id}")
        
        return UserProfileResponse(**result).model_dump()
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar perfil: {str(e)}", exc_info=True)
        
        empty_profile = create_empty_profile(str(current_user.id))
        return UserProfileResponse(**empty_profile).model_dump()


@router.post("/", response_model=UserProfileResponse)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def save_profile(
    request: Request,
    profile_data: UserProfileCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Cria ou atualiza o perfil financeiro do usuário.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    logger.info(f"💾 Salvando perfil para usuário: {current_user.id}")
    logger.debug(f"📝 Dados recebidos: {profile_data.model_dump(exclude_unset=True)}")
    
    try:
        user = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not user:
            logger.warning(f"⚠️ Usuário não encontrado ao salvar perfil: {current_user.id}")
            raise NotFoundException(
                message_key="ERROR_USER_NOT_FOUND",
                request=request
            )
        
        await ensure_profile_collection(db)
        
        existing = await db.user_profiles.find_one({"user_id": str(current_user.id)})
        now = datetime.now(timezone.utc)
        
        profile_dict = profile_data.model_dump(exclude_unset=True)
        profile_dict["user_id"] = str(current_user.id)
        profile_dict["updated_at"] = now
        
        logger.debug(f"📋 Dados validados: {profile_dict}")
        
        if existing:
            logger.info(f"📝 Atualizando perfil existente para usuário {current_user.id}")
            
            await db.user_profiles.update_one(
                {"_id": existing["_id"]},
                {"$set": profile_dict}
            )
            
            profile_dict["_id"] = existing["_id"]
            profile_dict["created_at"] = existing.get("created_at", now)
            
            logger.info(f"✅ Perfil atualizado para usuário {current_user.id}")
        else:
            logger.info(f"📝 Criando novo perfil para usuário {current_user.id}")
            
            profile_dict["created_at"] = now
            result = await db.user_profiles.insert_one(profile_dict)
            profile_dict["_id"] = result.inserted_id
            
            logger.info(f"✅ Perfil criado para usuário {current_user.id}")
        
        result_dict = prepare_profile_response(profile_dict)
        
        if not result_dict:
            logger.warning(f"⚠️ prepare_profile_response retornou vazio para usuário {current_user.id}")
            result_dict = create_empty_profile(str(current_user.id))
        
        return UserProfileResponse(**result_dict).model_dump()
        
    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao salvar perfil: {str(e)}", exc_info=True)
        
        if "validation" in str(e).lower():
            raise ValidationException(
                message_key="ERROR_VALIDATION",
                request=request
            )
        
        raise I18nHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message_key="ERROR_SERVER",
            request=request
        )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (get: 30/min, post: 20/min)
#   - Validação de campos Literal via Pydantic
#   - Validação de existência do usuário no POST
#   - Fallback seguro para perfil vazio
#   - SEM history (modo individual)
#   - Funções auxiliares centralizadas em utils/profile_utils.py
#   - 🔧 CORRIGIDO: importação de limiter
#
# ❌ Não implementado (Pós-MVP):
#   - Cache (Redis)
#   - updated_by (modo individual não precisa)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n, rate limiting (25/05/2026)
#   - v3: Correções de prepare_profile_response (01/07/2026)
#   - v4: Refatoração - profile_utils, rate_limiter (02/07/2026)
#   - v4.1: CORREÇÃO - importação de limiter adicionada (02/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO