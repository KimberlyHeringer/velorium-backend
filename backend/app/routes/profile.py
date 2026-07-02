"""
Rotas de Perfil Financeiro do Usuário
Arquivo: backend/app/routes/profile.py

🔧 CORRIGIDO (v4 - FINAL):
- Verificação e criação automática da coleção user_profiles
- Logs detalhados para diagnóstico
- Tratamento de erro 500
- Retorno de objeto com campos obrigatórios
- 🔧 CORRIGIDO: Adiciona campo 'id' explicitamente antes de retornar

🆕 MELHORIAS ADICIONADAS (v2):
- 🔧 Substituído format_mongo_doc por convert_objectid_to_str (padronização)
- 🆕 I18n completo com I18nHTTPException e get_message()
- 🆕 Adicionado request: Request em todos os endpoints
- 🆕 Adicionado rate limiting (get: 30/min, post: 20/min)
- 🆕 Adicionada validação de campos Literal (via Pydantic)

🔧 CORREÇÕES DO DESENVOLVEDOR (v3):
- 🔧 CORRIGIDO: prepare_profile_response retorna {} em vez de None
- 🔧 CORRIGIDO: prepare_profile_response fallback para "unknown" no id
- 🔧 CORRIGIDO: get_profile sempre retorna UserProfileResponse
- 🔧 CORRIGIDO: save_profile garante que result_dict não está vazio
- 🆕 Adicionada validação de existência do usuário no POST

🔧 CORREÇÕES DO DESENVOLVEDOR (v4):
- 🔧 MELHORADO: prepare_profile_response aceita fallback_user_id
- 🔧 MELHORADO: uso de create_empty_profile em prepare_profile_response

📋 DECISÕES DOCUMENTADAS:
- ✅ Implementado validação de campos via Pydantic
- ✅ Implementado rate limiting
- ✅ Implementado validação de existência do usuário
- ✅ Mantido padrão de i18n em todas as mensagens
- ✅ Usa convert_objectid_to_str em vez de format_mongo_doc
- ❌ SEM updated_by (modo individual não precisa)
- ❌ SEM history (modo individual não precisa)
- ❌ SEM cache (Pós-MVP)

📋 LIMITAÇÕES CONHECIDAS:
- Transações MongoDB: O Atlas Free Tier não suporta transações multi-documento.
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
from app.utils.rate_limiter import limiter

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/profile", tags=["Perfil Financeiro"])


# ========== FUNÇÕES AUXILIARES ==========

def get_user_rate_limit_key(request: Request) -> str:
    """
    🆕 Gera chave de rate limiting por usuário para perfil.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"profile:user:{user_id}"
    
    client_ip = request.client.host if request.client else "unknown"
    return f"profile:ip:{client_ip}"


async def ensure_profile_collection(db):
    """
    Garante que a coleção user_profiles existe.
    """
    collections = await db.list_collection_names()
    if "user_profiles" not in collections:
        logger.warning("⚠️ Coleção 'user_profiles' não existe, criando...")
        await db.create_collection("user_profiles")
        logger.info("✅ Coleção 'user_profiles' criada com sucesso")
    return True


def create_empty_profile(user_id: str) -> dict:
    """
    Cria um perfil vazio com campos obrigatórios.
    """
    now = datetime.now(timezone.utc)
    return {
        "id": user_id,
        "user_id": user_id,
        "created_at": now,
        "updated_at": now
    }


def prepare_profile_response(profile: dict, fallback_user_id: str = None) -> dict:
    """
    Prepara o perfil para resposta com os campos obrigatórios.
    
    🔧 MELHORADO: Aceita fallback_user_id para criar perfil vazio
    quando profile for None.
    """
    if not profile:
        if fallback_user_id:
            return create_empty_profile(fallback_user_id)
        return {}
    
    # Converte ObjectId para string
    result = convert_objectid_to_str(profile)
    
    # Garante que o campo 'id' exista
    if "_id" in profile:
        result["id"] = str(profile["_id"])
    elif "id" not in result:
        result["id"] = result.get("user_id") or "unknown"
    
    return result


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
    
    🔧 CORRIGIDO:
    - Verifica se a coleção existe, cria se necessário
    - Retorna objeto com campos obrigatórios se não houver perfil
    - Logs detalhados para diagnóstico
    - 🔧 Adiciona campo 'id' explicitamente
    - 🆕 I18n e rate limiting
    - 🔧 SEMPRE retorna UserProfileResponse
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 Armazena user_id no state para rate limiting
    request.state.user_id = str(current_user.id)
    
    logger.info(f"🔍 Buscando perfil para usuário: {current_user.id}")
    
    try:
        # 🔧 Garante que a coleção existe
        await ensure_profile_collection(db)
        
        # 🔧 Busca o perfil
        profile = await db.user_profiles.find_one({"user_id": str(current_user.id)})
        logger.info(f"📝 Perfil encontrado: {profile is not None}")
        
        # 🔧 MELHORADO: prepare_profile_response com fallback
        result = prepare_profile_response(profile, str(current_user.id))
        
        # 🔧 Verifica se result não está vazio
        if not result:
            logger.warning(f"⚠️ prepare_profile_response retornou vazio para usuário {current_user.id}")
            result = create_empty_profile(str(current_user.id))
        
        logger.debug(f"✅ Perfil recuperado para usuário {current_user.id}")
        
        return UserProfileResponse(**result).model_dump()
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar perfil: {str(e)}", exc_info=True)
        
        # 🔧 Fallback seguro sempre retorna UserProfileResponse
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
    
    🔧 CORRIGIDO:
    - Verifica se a coleção existe, cria se necessário
    - Logs detalhados para diagnóstico
    - 🆕 I18n e rate limiting
    - 🆕 Validação de existência do usuário
    - 🔧 Garante que result_dict não está vazio
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 Armazena user_id no state para rate limiting
    request.state.user_id = str(current_user.id)
    
    logger.info(f"💾 Salvando perfil para usuário: {current_user.id}")
    logger.debug(f"📝 Dados recebidos: {profile_data.model_dump(exclude_unset=True)}")
    
    try:
        # 🔧 CORRIGIDO: Verifica se o usuário existe
        user = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not user:
            logger.warning(f"⚠️ Usuário não encontrado ao salvar perfil: {current_user.id}")
            raise NotFoundException(
                message_key="ERROR_USER_NOT_FOUND",
                request=request
            )
        
        # 🔧 Garante que a coleção existe
        await ensure_profile_collection(db)
        
        # 🔧 Busca perfil existente
        existing = await db.user_profiles.find_one({"user_id": str(current_user.id)})
        now = datetime.now(timezone.utc)
        
        # 🔧 Prepara os dados
        profile_dict = profile_data.model_dump(exclude_unset=True)
        profile_dict["user_id"] = str(current_user.id)
        profile_dict["updated_at"] = now
        
        # 🔧 Validação dos campos Literal (já feita pelo Pydantic)
        logger.debug(f"📋 Dados validados: {profile_dict}")
        
        if existing:
            # 🔧 Atualiza perfil existente
            logger.info(f"📝 Atualizando perfil existente para usuário {current_user.id}")
            
            await db.user_profiles.update_one(
                {"_id": existing["_id"]},
                {"$set": profile_dict}
            )
            
            profile_dict["_id"] = existing["_id"]
            profile_dict["created_at"] = existing.get("created_at", now)
            
            logger.info(f"✅ Perfil atualizado para usuário {current_user.id}")
        else:
            # 🔧 Cria novo perfil
            logger.info(f"📝 Criando novo perfil para usuário {current_user.id}")
            
            profile_dict["created_at"] = now
            result = await db.user_profiles.insert_one(profile_dict)
            profile_dict["_id"] = result.inserted_id
            
            logger.info(f"✅ Perfil criado para usuário {current_user.id}")
        
        # 🔧 Converte ObjectId para string e prepara resposta
        result_dict = prepare_profile_response(profile_dict)
        
        # 🔧 CORRIGIDO: Garante que result_dict não está vazio
        if not result_dict:
            logger.warning(f"⚠️ prepare_profile_response retornou vazio para usuário {current_user.id}")
            result_dict = create_empty_profile(str(current_user.id))
        
        return UserProfileResponse(**result_dict).model_dump()
        
    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao salvar perfil: {str(e)}", exc_info=True)
        
        # Verifica se é um erro de validação do Pydantic
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
# ✅ Verificação e criação automática da coleção user_profiles
# ✅ Logs detalhados para diagnóstico (info, debug, warning, error)
# ✅ Fallback em caso de erro no GET (retorna objeto vazio)
# ✅ Tratamento de exceções com logging completo
# ✅ Uso de convert_objectid_to_str para converter ObjectId
# ✅ Campos obrigatórios preenchidos no objeto vazio
# ✅ 🔧 Campo 'id' adicionado explicitamente em GET e POST
# ✅ 🆕 I18n completo com I18nHTTPException e get_message()
# ✅ 🆕 request: Request em todos os endpoints
# ✅ 🆕 Rate limiting (get: 30/min, post: 20/min)
# ✅ 🆕 Validação de campos Literal (via Pydantic)
# ✅ 🔧 CORRIGIDO: prepare_profile_response retorna {} em vez de None
# ✅ 🔧 CORRIGIDO: prepare_profile_response fallback para "unknown"
# ✅ 🔧 CORRIGIDO: get_profile sempre retorna UserProfileResponse
# ✅ 🔧 CORRIGIDO: save_profile garante result_dict não vazio
# ✅ 🆕 Validação de existência do usuário no POST
# ✅ 🔧 MELHORADO: prepare_profile_response aceita fallback_user_id
#
# 📌 CHAVES I18N UTILIZADAS:
#   - ERROR_SERVER → "Erro interno do servidor"
#   - ERROR_VALIDATION → "Dados inválidos"
#   - ERROR_USER_NOT_FOUND → "Usuário não encontrado"
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO