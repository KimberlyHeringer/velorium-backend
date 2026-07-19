"""
Rotas de Conquistas do Usuário (sincronização)
Arquivo: backend/app/routes/achievements.py

Funcionalidades:
- GET /achievements: Listar conquistas com paginação e filtros (type, year, month)
- POST /achievements: Criar conquista individual (com validação de duplicação)
- POST /achievements/sync: Sincronizar múltiplas conquistas (batch + bulk insert)
- GET /achievements/{id}: Buscar conquista específica
- DELETE /achievements/{id}: Remover conquista

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting no sync (10/minuto)
- Limite de batch (MAX_SYNC_BATCH = 100)
- Bulk insert para performance
- Filtros avançados no GET (type, year, month)
- Validação de tipo de conquista
- 🔧 Validação robusta no sync (v4.3)

Versão: v4.3 (validação robusta no sync)
📅 ATUALIZADO EM: 20/07/2026
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.achievement import AchievementCreate, AchievementResponse, TIPOS_VALIDOS
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import validate_object_id, convert_objectid_to_str
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter, get_user_rate_limit_key

# ========== NOVOS IMPORTS ==========
from app.core.constants import MAX_SYNC_BATCH

# ========== I18N ==========
from app.utils.i18n import get_message
from app.utils.exceptions import (
    I18nHTTPException,
    NotFoundException,
    ValidationException,
    ConflictException
)

logger = setup_logger(__name__)

router = APIRouter(prefix="/achievements", tags=["Conquistas"])


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def get_achievements(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    type: Optional[str] = Query(None, description="Filtrar por tipo de conquista"),
    year: Optional[int] = Query(None, ge=1900, le=2100, description="Ano da conquista"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Mês da conquista (1-12)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna todas as conquistas do usuário com paginação e filtros opcionais.
    
    Filtros disponíveis:
    - type: Filtrar por tipo de conquista (validado contra TIPOS_VALIDOS)
    - year: Filtrar por ano (ex: 2025)
    - month: Filtrar por mês (ex: 6 para junho)
    """
    user_id = str(current_user.id)
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": user_id}
    
    if type:
        if type not in TIPOS_VALIDOS:
            raise ValidationException(
                message_key="ERROR_INVALID_ACHIEVEMENT_TYPE",
                request=request
            )
        query["type"] = type
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month

    # 🔧 CORRIGIDO: Adicionado collection_name
    items, total = await paginate_query(
        collection=db.achievements,
        collection_name="achievements",
        query=query,
        params=params,
        user_id=user_id,
        sort=[("date", -1)]
    )
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.info(f"📊 {len(formatted_items)} conquistas listadas para usuário {user_id}")
    
    return paginate(formatted_items, total, params).model_dump()


@router.post("/", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    ach_data: AchievementCreate,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Cria uma nova conquista para o usuário atual.
    
    🔧 CORRIGIDO: Query de duplicação com condições para year/month None.
    """
    user_id = str(current_user.id)
    ach_dict = ach_data.model_dump()
    ach_dict["user_id"] = user_id
    ach_dict["date"] = datetime.now(timezone.utc)
    
    query = {"user_id": user_id, "type": ach_data.type}
    if ach_data.year is not None:
        query["year"] = ach_data.year
    if ach_data.month is not None:
        query["month"] = ach_data.month
    
    existing = await db.achievements.find_one(query)
    
    if existing:
        logger.warning(f"⚠️ Tentativa de duplicar conquista: {ach_data.type} para usuário {user_id}")
        raise ConflictException(
            message_key="ACHIEVEMENT_ALREADY_EXISTS",
            request=request
        )
    
    result = await db.achievements.insert_one(ach_dict)
    created = await db.achievements.find_one({"_id": result.inserted_id})
    
    logger.info(f"✅ Conquista criada para usuário {user_id}: {ach_data.type}")
    
    return convert_objectid_to_str(created)


@router.post("/sync", response_model=dict)
@limiter.limit("10/minute")
async def sync_achievements(
    achievements: List[AchievementCreate],
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Sincroniza múltiplas conquistas do frontend em lote.
    
    🔧 MELHORIA v4.3:
    - Validação robusta de cada conquista antes de inserir
    - Log detalhado de erros para debug
    - Fallback seguro para dados inválidos
    - Mensagens de erro detalhadas
    """
    user_id = str(current_user.id)
    language = getattr(request.state, "language", "pt")
    
    # 🔧 CORRIGIDO: Valida se a lista não está vazia
    if not achievements:
        logger.warning(f"⚠️ Lista de conquistas vazia para usuário {user_id}")
        return {
            "synced": 0,
            "message": get_message("ACHIEVEMENT_SYNC_NONE", language),
            "errors": ["Lista de conquistas vazia"]
        }
    
    if len(achievements) > MAX_SYNC_BATCH:
        logger.warning(f"⚠️ Batch excedeu limite: {len(achievements)} > {MAX_SYNC_BATCH} para usuário {user_id}")
        raise ValidationException(
            message_key="ACHIEVEMENT_SYNC_BATCH_TOO_LARGE",
            request=request
        )
    
    achievements_to_insert = []
    errors = []
    
    for idx, ach in enumerate(achievements):
        try:
            # 🔧 CORRIGIDO: Validação individual de cada conquista
            
            # Verifica se o tipo é válido
            if ach.type not in TIPOS_VALIDOS:
                errors.append({
                    "index": idx,
                    "type": ach.type,
                    "error": f"Tipo inválido: {ach.type}. Tipos válidos: {', '.join(TIPOS_VALIDOS)}"
                })
                continue
            
            # Verifica se os campos obrigatórios estão presentes
            if not ach.name or not ach.name.strip():
                errors.append({
                    "index": idx,
                    "type": ach.type,
                    "error": "Campo 'name' é obrigatório"
                })
                continue
            
            # Verifica duplicação
            query = {"user_id": user_id, "type": ach.type}
            if ach.year is not None:
                query["year"] = ach.year
            if ach.month is not None:
                query["month"] = ach.month
            if ach.name:
                query["name"] = ach.name
            
            existing = await db.achievements.find_one(query)
            
            if existing:
                logger.debug(f"ℹ️ Conquista já existe: {ach.type} para usuário {user_id}")
                continue
            
            ach_dict = ach.model_dump()
            ach_dict["user_id"] = user_id
            ach_dict["date"] = datetime.now(timezone.utc)
            achievements_to_insert.append(ach_dict)
            
        except Exception as e:
            errors.append({
                "index": idx,
                "type": ach.type if hasattr(ach, 'type') else 'unknown',
                "error": str(e)
            })
            logger.warning(f"⚠️ Erro ao validar conquista {idx}: {e}")
    
    inserted = 0
    if achievements_to_insert:
        try:
            result = await db.achievements.insert_many(achievements_to_insert)
            inserted = len(result.inserted_ids)
            logger.info(f"✅ {inserted} conquistas inseridas em bulk para usuário {user_id}")
        except Exception as e:
            logger.error(f"❌ Erro ao inserir conquistas em bulk: {e}")
            errors.append({
                "error": "Falha ao inserir conquistas no banco",
                "details": str(e)
            })
    
    # 🔧 CORRIGIDO: Mensagem mais informativa
    if inserted == 0 and not errors:
        message = get_message("ACHIEVEMENT_SYNC_NONE", language)
    elif inserted == 1:
        message = get_message("ACHIEVEMENT_SYNC_ONE", language)
    elif inserted > 1:
        message = get_message("ACHIEVEMENT_SYNC_MULTIPLE", language).format(count=inserted)
    else:
        message = f"{len(errors)} erro(s) ao sincronizar conquistas"
    
    logger.info(f"📊 Sync concluído: {inserted} novas conquistas para usuário {user_id}, {len(errors)} erros")
    
    return {
        "synced": inserted,
        "message": message,
        "errors": errors if errors else None
    }


@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma conquista específica pelo ID."""
    user_id = str(current_user.id)
    validate_object_id(achievement_id, "achievement_id")
    obj_id = ObjectId(achievement_id)
    
    achievement = await db.achievements.find_one({
        "_id": obj_id,
        "user_id": user_id
    })
    
    if not achievement:
        logger.warning(f"⚠️ Conquista não encontrada: {achievement_id} para usuário {user_id}")
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    return convert_objectid_to_str(achievement)


@router.delete("/{achievement_id}", response_model=dict)
async def delete_achievement(
    achievement_id: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Remove uma conquista do usuário.
    
    🔧 CORRIGIDO: Removido try/except desnecessário.
    validate_object_id já levanta exceção se o ID for inválido.
    """
    user_id = str(current_user.id)
    validate_object_id(achievement_id, "achievement_id")
    obj_id = ObjectId(achievement_id)
    
    result = await db.achievements.delete_one({
        "_id": obj_id,
        "user_id": user_id
    })
    
    if result.deleted_count == 0:
        logger.warning(f"⚠️ Tentativa de deletar conquista inexistente: {achievement_id}")
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    language = getattr(request.state, "language", "pt")
    message = get_message("ACHIEVEMENT_DELETED", language)
    
    logger.info(f"🗑️ Conquista removida: {achievement_id} (usuário {user_id})")
    
    return {"message": message}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting no sync (10/min)
#   - Limite de batch (MAX_SYNC_BATCH = 100)
#   - Bulk insert para performance
#   - Filtros por type, year, month
#   - Pluralização nas mensagens de sync
#   - Verificação de duplicação antes de criar/sync
#   - Validação de type contra TIPOS_VALIDOS no GET
#   - 🔧 Validação robusta de cada conquista no sync (v4.3)
#   - 🔧 Log detalhado de erros
#   - 🔧 Mensagens de erro informativas
#
# ✅ CORRIGIDO (18/07/2026):
#   - 🔧 Adicionado collection_name="achievements" no paginate_query
#   - 🔧 Adicionado user_id no paginate_query
#
# ❌ Não implementado (Pós-MVP):
#   - Transação MongoDB: Free Tier não suporta (M10+ necessário)
#     Alternativa: Frontend pode re-sync se falhar
#   - Validação extra de type no sync: Já validado pelo Pydantic no AchievementCreate
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções de query (25/05/2026)
#   - v3: Batch limit, bulk insert, filtros (30/06/2026)
#   - v4: Refatoração - MAX_SYNC_BATCH movido para core/constants.py (02/07/2026)
#   - v4.1: Validação de type no GET (02/07/2026)
#   - v4.2: CORREÇÃO - collection_name no paginate_query (18/07/2026)
#   - v4.3: CORREÇÃO - Validação robusta no sync, logs detalhados (20/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO