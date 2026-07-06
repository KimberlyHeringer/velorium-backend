"""
Rotas de Perfil Financeiro do Usuário
Arquivo: backend/app/routes/profile.py

Funcionalidades:
- GET /profile: Buscar perfil financeiro do usuário
- POST /profile: Criar/atualizar perfil financeiro do usuário

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (get: 30/min, post: 20/min)
- 🔧 NOVO: Cache Redis para perfil (TTL: 5 minutos)
- 🔧 NOVO: Invalidação automática de cache ao atualizar
- Validação de campos Literal via Pydantic
- Validação de existência do usuário no POST
- Fallback seguro para perfil vazio
- SEM history (modo individual)

Versão: v5.0 (com cache Redis)
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

# ========== IMPORTS DE RATE LIMITER ==========
from app.utils.rate_limiter import limiter, get_user_rate_limit_key

# ========== IMPORTS DE PROFILE UTILS ==========
from app.utils.profile_utils import (
    create_empty_profile,
    prepare_profile_response,
    ensure_profile_collection,
    get_cached_profile,      # 🔧 NOVO
    set_cached_profile,      # 🔧 NOVO
    invalidate_profile_cache # 🔧 NOVO
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
    
    🔧 MELHORADO: Agora com cache Redis.
    - Tenta buscar do cache primeiro
    - Se não encontrar, busca no MongoDB
    - Se encontrar no MongoDB, salva no cache
    - Fallback para perfil vazio se nada for encontrado
    """
    language = getattr(request.state, "language", "pt")
    user_id = str(current_user.id)
    request.state.user_id = user_id
    
    logger.info(f"🔍 Buscando perfil para usuário: {user_id}")
    
    try:
        # 🔧 NOVO: Garante que a coleção existe
        await ensure_profile_collection(db)
        
        # 🔧 NOVO: Tenta buscar do cache Redis primeiro
        profile = await get_cached_profile(user_id, db)
        
        if profile is None:
            # 🔧 NOVO: Cache miss - busca no MongoDB
            logger.debug(f"ℹ️ Cache miss para perfil do usuário {user_id}")
            profile = await db.user_profiles.find_one({"user_id": user_id})
            
            if profile:
                # 🔧 NOVO: Salva no cache para próximas requisições
                await set_cached_profile(user_id, profile)
                logger.debug(f"💾 Perfil salvo no cache para usuário {user_id}")
        else:
            logger.debug(f"✅ Cache hit para perfil do usuário {user_id}")
        
        # Prepara a resposta usando o utilitário
        result = prepare_profile_response(profile, user_id)
        
        if not result:
            logger.warning(f"⚠️ prepare_profile_response retornou vazio para usuário {user_id}")
            result = create_empty_profile(user_id)
        
        logger.debug(f"✅ Perfil recuperado para usuário {user_id}")
        
        return UserProfileResponse(**result).model_dump()
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar perfil: {str(e)}", exc_info=True)
        
        # Fallback seguro: retorna perfil vazio
        empty_profile = create_empty_profile(user_id)
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
    
    🔧 MELHORADO: Agora com cache Redis.
    - Valida existência do usuário
    - Cria ou atualiza no MongoDB
    - 🔧 NOVO: Invalida cache após atualização
    - 🔧 NOVO: Salva novo perfil no cache
    """
    language = getattr(request.state, "language", "pt")
    user_id = str(current_user.id)
    request.state.user_id = user_id
    
    logger.info(f"💾 Salvando perfil para usuário: {user_id}")
    logger.debug(f"📝 Dados recebidos: {profile_data.model_dump(exclude_unset=True)}")
    
    try:
        # Verifica se o usuário existe
        user = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not user:
            logger.warning(f"⚠️ Usuário não encontrado ao salvar perfil: {user_id}")
            raise NotFoundException(
                message_key="ERROR_USER_NOT_FOUND",
                request=request
            )
        
        # Garante que a coleção existe
        await ensure_profile_collection(db)
        
        # Verifica se já existe um perfil
        existing = await db.user_profiles.find_one({"user_id": user_id})
        now = datetime.now(timezone.utc)
        
        # Prepara os dados do perfil
        profile_dict = profile_data.model_dump(exclude_unset=True)
        profile_dict["user_id"] = user_id
        profile_dict["updated_at"] = now
        
        logger.debug(f"📋 Dados validados: {profile_dict}")
        
        if existing:
            # 🔧 Atualiza perfil existente
            logger.info(f"📝 Atualizando perfil existente para usuário {user_id}")
            
            await db.user_profiles.update_one(
                {"_id": existing["_id"]},
                {"$set": profile_dict}
            )
            
            # 🔧 NOVO: Invalida cache após atualização
            await invalidate_profile_cache(user_id)
            logger.debug(f"🗑️ Cache invalidado para usuário {user_id}")
            
            # Monta o resultado com os dados existentes + atualizados
            profile_dict["_id"] = existing["_id"]
            profile_dict["created_at"] = existing.get("created_at", now)
            
            logger.info(f"✅ Perfil atualizado para usuário {user_id}")
        else:
            # 🔧 Cria novo perfil
            logger.info(f"📝 Criando novo perfil para usuário {user_id}")
            
            profile_dict["created_at"] = now
            result = await db.user_profiles.insert_one(profile_dict)
            profile_dict["_id"] = result.inserted_id
            
            logger.info(f"✅ Perfil criado para usuário {user_id}")
        
        # 🔧 NOVO: Salva no cache para próximas requisições
        await set_cached_profile(user_id, profile_dict)
        logger.debug(f"💾 Perfil salvo no cache para usuário {user_id}")
        
        # Prepara a resposta
        result_dict = prepare_profile_response(profile_dict)
        
        if not result_dict:
            logger.warning(f"⚠️ prepare_profile_response retornou vazio para usuário {user_id}")
            result_dict = create_empty_profile(user_id)
        
        return UserProfileResponse(**result_dict).model_dump()
        
    except NotFoundException:
        raise
    except ValidationException:
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


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Buscar perfil (GET /profile):
   - Tenta buscar do cache Redis primeiro
   - Se não encontrar, busca no MongoDB
   - Salva no cache para próximas requisições
   - TTL do cache: 5 minutos (configurado em constants.py)

2. Salvar perfil (POST /profile):
   - Valida existência do usuário
   - Cria ou atualiza no MongoDB
   - Invalida o cache após atualização
   - Salva o novo perfil no cache

3. Fallback seguro:
   - Se o perfil não existir, retorna um perfil vazio
   - Se o Redis falhar, o MongoDB ainda funciona
   - Se tudo falhar, retorna perfil vazio
"""


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
#   - 🔧 NOVO: Cache Redis com TTL (5 minutos)
#   - 🔧 NOVO: Invalidação automática de cache
#   - 🔧 NOVO: Cache hit/miss com logs
#
# ❌ Não implementado (Pós-MVP):
#   - updated_by (modo individual não precisa)
#   - Métricas de hit/miss do cache (em profile_utils.py)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n, rate limiting (25/05/2026)
#   - v3: Correções de prepare_profile_response (01/07/2026)
#   - v4: Refatoração - profile_utils, rate_limiter (02/07/2026)
#   - v4.1: CORREÇÃO - importação de limiter adicionada (02/07/2026)
#   - v5.0: ADICIONADO - Cache Redis (get_cached_profile, set_cached_profile, invalidate_profile_cache) (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO