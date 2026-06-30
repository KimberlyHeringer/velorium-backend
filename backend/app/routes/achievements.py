"""
Rotas de Conquistas do Usuário (sincronização)
Arquivo: backend/app/routes/achievements.py

🔧 CORRIGIDO:
- Substituído HTTPException por I18nHTTPException
- Adicionado suporte a internacionalização
- Usa get_message() para mensagens de sucesso
- Adicionado request: Request nos endpoints
- 🔧 CORRIGIDO: Usa convert_objectid_to_str em vez de format_mongo_doc
- 🔧 CORRIGIDO: Query de duplicação no create com year/month None
- 🔧 CORRIGIDO: Query de duplicação no sync com year/month None
- 🔧 CORRIGIDO: Mensagens de sync com pluralização
- 🔧 CORRIGIDO: Removido try/except desnecessário no delete
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.achievement import AchievementCreate, AchievementResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import validate_object_id, convert_objectid_to_str
from app.utils.logger import setup_logger

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
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna todas as conquistas do usuário com paginação"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}

    items, total = await paginate_query(
        db.achievements, query, params, sort=[("date", -1)]
    )
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    return paginate(formatted_items, total, params).model_dump()


@router.post("/", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    ach_data: AchievementCreate,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova conquista"""
    ach_dict = ach_data.model_dump()
    ach_dict["user_id"] = str(current_user.id)
    ach_dict["date"] = datetime.now(timezone.utc)
    
    # 🔧 CORRIGIDO: Query com condições (year/month podem ser None)
    query = {"user_id": str(current_user.id), "type": ach_data.type}
    if ach_data.year is not None:
        query["year"] = ach_data.year
    if ach_data.month is not None:
        query["month"] = ach_data.month
    
    existing = await db.achievements.find_one(query)
    
    if existing:
        raise ConflictException(
            message_key="ACHIEVEMENT_ALREADY_EXISTS",
            request=request
        )
    
    result = await db.achievements.insert_one(ach_dict)
    created = await db.achievements.find_one({"_id": result.inserted_id})
    
    logger.info(f"✅ Conquista criada para usuário {current_user.id}: {ach_data.type}")
    
    return convert_objectid_to_str(created)


@router.post("/sync", response_model=dict)
async def sync_achievements(
    achievements: List[AchievementCreate],
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Sincroniza múltiplas conquistas do frontend"""
    user_id = str(current_user.id)
    inserted = 0
    
    for ach in achievements:
        # 🔧 CORRIGIDO: Query com condições (year/month podem ser None)
        query = {"user_id": user_id, "type": ach.type}
        if ach.year is not None:
            query["year"] = ach.year
        if ach.month is not None:
            query["month"] = ach.month
        if ach.name:
            query["name"] = ach.name
        
        existing = await db.achievements.find_one(query)
        
        if not existing:
            ach_dict = ach.model_dump()
            ach_dict["user_id"] = user_id
            ach_dict["date"] = datetime.now(timezone.utc)
            await db.achievements.insert_one(ach_dict)
            inserted += 1
    
    language = getattr(request.state, "language", "pt")
    
    # 🔧 CORRIGIDO: Mensagem com pluralização
    if inserted == 0:
        message = get_message("ACHIEVEMENT_SYNC_NONE", language)
    elif inserted == 1:
        message = get_message("ACHIEVEMENT_SYNC_ONE", language)
    else:
        message = get_message("ACHIEVEMENT_SYNC_MULTIPLE", language).format(count=inserted)
    
    logger.info(f"✅ {inserted} conquistas sincronizadas para usuário {user_id}")
    
    return {
        "synced": inserted,
        "message": message
    }


@router.delete("/{achievement_id}", response_model=dict)
async def delete_achievement(
    achievement_id: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma conquista"""
    # 🔧 CORRIGIDO: Simplificado (validate_object_id já levanta exceção)
    validate_object_id(achievement_id, "achievement_id")
    obj_id = ObjectId(achievement_id)
    
    result = await db.achievements.delete_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    
    if result.deleted_count == 0:
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    language = getattr(request.state, "language", "pt")
    message = get_message("ACHIEVEMENT_DELETED", language)
    
    logger.info(f"🗑️ Conquista removida: {achievement_id}")
    
    return {"message": message}


@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma conquista específica"""
    validate_object_id(achievement_id, "achievement_id")
    obj_id = ObjectId(achievement_id)
    
    achievement = await db.achievements.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    
    if not achievement:
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    return convert_objectid_to_str(achievement)


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Substituído HTTPException por I18nHTTPException
# ✅ Usa ValidationException para erros de validação
# ✅ Usa NotFoundException para recursos não encontrados
# ✅ Usa ConflictException para conflitos (duplicação)
# ✅ Mensagens de sucesso com get_message()
# ✅ Suporte a i18n via request.state.language
# ✅ Verificação de duplicação antes de criar conquista
# ✅ Sync com year + month (int) em vez de month (string)
# ✅ 🔧 Usa convert_objectid_to_str em vez de format_mongo_doc
# ✅ 🔧 Query de duplicação com condições para year/month None
# ✅ 🔧 Mensagens de sync com pluralização
# ✅ 🔧 Delete simplificado (sem try/except redundante)
# ✅ 🔧 Get simplificado (sem try/except redundante)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO