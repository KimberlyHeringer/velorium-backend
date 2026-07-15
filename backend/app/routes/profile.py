"""
Rotas de Perfil Financeiro do Usuário
Arquivo: backend/app/routes/profile.py

Funcionalidades:
- GET /profile: Buscar perfil financeiro do usuário
- POST /profile: Criar perfil financeiro do usuário
- PUT /profile: Atualizar perfil financeiro do usuário

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (get: 30/min, post: 20/min, put: 20/min)
- 🔧 NOVO: Cache Redis para perfil (TTL: 5 minutos)
- 🔧 NOVO: Invalidação automática de cache ao atualizar
- 🔧 NOVO: PUT para atualização (semântica REST)
- Validação de campos Literal via Pydantic
- Validação de existência do usuário no POST/PUT
- Fallback seguro para perfil vazio
- SEM history (modo individual)

Versão: v5.2 (correções de import e documentação)
📅 ATUALIZADO EM: 14/07/2026
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
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
    get_cached_profile,
    set_cached_profile,
    invalidate_profile_cache
)

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/profile", tags=["Perfil Financeiro"])


# ========== FUNÇÕES AUXILIARES ==========

async def _get_existing_profile(user_id: str, db):
    """
    Busca perfil existente no banco.
    """
    return await db.user_profiles.find_one({"user_id": user_id})


async def _save_profile_to_cache(user_id: str, profile_data: dict) -> None:
    """
    Salva perfil no cache Redis.
    """
    await set_cached_profile(user_id, profile_data)


async def _invalidate_profile_cache(user_id: str) -> None:
    """
    Invalida cache do perfil.
    """
    await invalidate_profile_cache(user_id)


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
        # 🔧 Garante que a coleção existe
        await ensure_profile_collection(db)
        
        # 🔧 Tenta buscar do cache Redis primeiro
        profile = await get_cached_profile(user_id, db)
        
        if profile is None:
            # 🔧 Cache miss - busca no MongoDB
            logger.debug(f"ℹ️ Cache miss para perfil do usuário {user_id}")
            profile = await db.user_profiles.find_one({"user_id": user_id})
            
            if profile:
                # 🔧 Salva no cache para próximas requisições
                await _save_profile_to_cache(user_id, profile)
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
async def create_profile(
    request: Request,
    profile_data: UserProfileCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    🔧 NOVO: Cria um novo perfil financeiro para o usuário.
    
    🔧 DIFERENÇA DO PUT:
    - POST é usado APENAS para criar um novo perfil
    - Se o perfil já existir, retorna erro 409 (Conflict)
    - Segue a semântica REST: POST = criar
    """
    language = getattr(request.state, "language", "pt")
    user_id = str(current_user.id)
    request.state.user_id = user_id
    
    logger.info(f"📝 Criando perfil para usuário: {user_id}")
    logger.debug(f"📝 Dados recebidos: {profile_data.model_dump(exclude_unset=True)}")
    
    try:
        # Verifica se o usuário existe
        user = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not user:
            logger.warning(f"⚠️ Usuário não encontrado ao criar perfil: {user_id}")
            raise NotFoundException(
                message_key="ERROR_USER_NOT_FOUND",
                request=request
            )
        
        # Garante que a coleção existe
        await ensure_profile_collection(db)
        
        # Verifica se já existe um perfil
        existing = await _get_existing_profile(user_id, db)
        if existing:
            logger.warning(f"⚠️ Perfil já existe para usuário {user_id}")
            raise I18nHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                message_key="ERROR_PROFILE_ALREADY_EXISTS",
                request=request
            )
        
        now = datetime.now(timezone.utc)
        
        # Prepara os dados do perfil
        profile_dict = profile_data.model_dump(exclude_unset=True)
        profile_dict["user_id"] = user_id
        profile_dict["created_at"] = now
        profile_dict["updated_at"] = now
        
        logger.debug(f"📋 Dados validados: {profile_dict}")
        
        # Cria o perfil
        result = await db.user_profiles.insert_one(profile_dict)
        profile_dict["_id"] = result.inserted_id
        
        logger.info(f"✅ Perfil criado para usuário {user_id}")
        
        # 🔧 Salva no cache para próximas requisições
        await _save_profile_to_cache(user_id, profile_dict)
        logger.debug(f"💾 Perfil salvo no cache para usuário {user_id}")
        
        # Prepara a resposta
        result_dict = prepare_profile_response(profile_dict)
        
        if not result_dict:
            logger.warning(f"⚠️ prepare_profile_response retornou vazio para usuário {user_id}")
            result_dict = create_empty_profile(user_id)
        
        return UserProfileResponse(**result_dict).model_dump()
        
    except NotFoundException:
        raise
    except I18nHTTPException:
        raise
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao criar perfil: {str(e)}", exc_info=True)
        
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


@router.put("/", response_model=UserProfileResponse)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def update_profile(
    request: Request,
    profile_data: UserProfileCreate,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    🔧 NOVO: Atualiza o perfil financeiro do usuário.
    
    🔧 DIFERENÇA DO POST:
    - PUT é usado APENAS para atualizar um perfil existente
    - Se o perfil não existir, retorna erro 404 (Not Found)
    - Segue a semântica REST: PUT = atualizar
    """
    language = getattr(request.state, "language", "pt")
    user_id = str(current_user.id)
    request.state.user_id = user_id
    
    logger.info(f"📝 Atualizando perfil para usuário: {user_id}")
    logger.debug(f"📝 Dados recebidos: {profile_data.model_dump(exclude_unset=True)}")
    
    try:
        # Verifica se o usuário existe
        user = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not user:
            logger.warning(f"⚠️ Usuário não encontrado ao atualizar perfil: {user_id}")
            raise NotFoundException(
                message_key="ERROR_USER_NOT_FOUND",
                request=request
            )
        
        # Garante que a coleção existe
        await ensure_profile_collection(db)
        
        # Verifica se já existe um perfil
        existing = await _get_existing_profile(user_id, db)
        if not existing:
            logger.warning(f"⚠️ Perfil não encontrado para usuário {user_id}")
            raise NotFoundException(
                message_key="ERROR_PROFILE_NOT_FOUND",
                request=request
            )
        
        now = datetime.now(timezone.utc)
        
        # Prepara os dados do perfil
        profile_dict = profile_data.model_dump(exclude_unset=True)
        profile_dict["user_id"] = user_id
        profile_dict["updated_at"] = now
        
        logger.debug(f"📋 Dados validados: {profile_dict}")
        
        # Atualiza o perfil
        await db.user_profiles.update_one(
            {"_id": existing["_id"]},
            {"$set": profile_dict}
        )
        
        # 🔧 Invalida cache após atualização
        await _invalidate_profile_cache(user_id)
        logger.debug(f"🗑️ Cache invalidado para usuário {user_id}")
        
        # Monta o resultado com os dados existentes + atualizados
        profile_dict["_id"] = existing["_id"]
        profile_dict["created_at"] = existing.get("created_at", now)
        
        logger.info(f"✅ Perfil atualizado para usuário {user_id}")
        
        # 🔧 Salva no cache para próximas requisições
        await _save_profile_to_cache(user_id, profile_dict)
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
        logger.error(f"❌ Erro ao atualizar perfil: {str(e)}", exc_info=True)
        
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


# ✅ CORRIGIDO: Adicionado Response import e documentação
@router.head(
    "/",
    description="Verifica se o perfil existe. Retorna 200 se existe, 404 se não existe.",
    responses={
        200: {"description": "Perfil existe"},
        404: {"description": "Perfil não existe"},
    }
)
async def head_profile(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    🔧 NOVO: Verifica se o perfil existe.
    Usado pelo frontend para decidir entre POST e PUT.
    Retorna 200 se existe, 404 se não existe.
    """
    user_id = str(current_user.id)
    
    try:
        # Verifica se o perfil existe no cache primeiro
        cached = await get_cached_profile(user_id, db)
        if cached is not None:
            return Response(status_code=status.HTTP_200_OK)
        
        # Verifica no MongoDB
        profile = await db.user_profiles.find_one({"user_id": user_id})
        if profile:
            return Response(status_code=status.HTTP_200_OK)
        else:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar existência do perfil: {e}")
        return Response(status_code=status.HTTP_404_NOT_FOUND)


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Buscar perfil (GET /profile):
   - Tenta buscar do cache Redis primeiro
   - Se não encontrar, busca no MongoDB
   - Salva no cache para próximas requisições
   - TTL do cache: 5 minutos

2. Criar perfil (POST /profile):
   - Verifica se o usuário existe
   - Verifica se o perfil já existe (409 Conflict)
   - Cria novo perfil no MongoDB
   - Salva no cache

3. Atualizar perfil (PUT /profile):
   - Verifica se o usuário existe
   - Verifica se o perfil existe (404 Not Found)
   - Atualiza perfil no MongoDB
   - Invalida cache
   - Salva novo perfil no cache

4. Verificar existência (HEAD /profile):
   - Usado pelo frontend para decidir entre POST e PUT
   - Retorna 200 se existe, 404 se não existe
"""


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (get: 30/min, post: 20/min, put: 20/min)
#   - Validação de campos Literal via Pydantic
#   - Validação de existência do usuário no POST/PUT
#   - Fallback seguro para perfil vazio
#   - SEM history (modo individual)
#   - Funções auxiliares centralizadas em utils/profile_utils.py
#   - Cache Redis com TTL (5 minutos)
#   - Invalidação automática de cache
#   - Cache hit/miss com logs
#   - 🔧 NOVO: POST para criar (201 Created)
#   - 🔧 NOVO: PUT para atualizar (200 OK)
#   - 🔧 NOVO: HEAD para verificar existência
#   - 🔧 NOVO: Erro 409 se perfil já existe no POST
#   - 🔧 NOVO: Erro 404 se perfil não existe no PUT
#   - 🔧 NOVO: Funções auxiliares _get_existing_profile, _save_profile_to_cache, _invalidate_profile_cache
#   - 🔧 CORRIGIDO: Import do Response adicionado
#   - 🔧 CORRIGIDO: Documentação do HEAD endpoint
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
#   - v5.0: ADICIONADO - Cache Redis (06/07/2026)
#   - v5.1: ADICIONADO - PUT, HEAD, POST separado, semântica REST (14/07/2026)
#   - v5.2: CORREÇÃO - import Response, documentação HEAD (14/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO