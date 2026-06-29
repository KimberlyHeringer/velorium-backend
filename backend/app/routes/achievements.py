"""
Rotas de Conquistas do Usuário (sincronização)
Arquivo: backend/app/routes/achievements.py

🔧 CORRIGIDO:
- Substituído HTTPException por I18nHTTPException
- Adicionado suporte a internacionalização
- Usa get_message() para mensagens de sucesso
- Adicionado request: Request nos endpoints
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
from app.utils.validators import format_mongo_doc, validate_object_id
from app.utils.logger import setup_logger

# ========== 🔧 NOVO: Internacionalização ==========
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
    
    formatted_items = [format_mongo_doc(item) for item in items]
    
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
    
    # 🔧 VERIFICA SE JÁ EXISTE (evita duplicação)
    existing = await db.achievements.find_one({
        "user_id": str(current_user.id),
        "type": ach_data.type,
        "year": ach_data.year,
        "month": ach_data.month
    })
    
    if existing:
        raise ConflictException(
            message_key="ACHIEVEMENT_ALREADY_EXISTS",
            request=request
        )
    
    result = await db.achievements.insert_one(ach_dict)
    created = await db.achievements.find_one({"_id": result.inserted_id})
    
    logger.info(f"✅ Conquista criada para usuário {current_user.id}: {ach_data.type}")
    
    return format_mongo_doc(created)


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
        # 🔧 CORRIGIDO: Usa year + month em vez de month string
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
    
    # 🔧 CORRIGIDO: Usa get_message() para mensagem traduzida
    message = get_message(
        "SUCCESS_CREATED", 
        getattr(request.state, "language", "pt")
    )
    
    logger.info(f"✅ {inserted} conquistas sincronizadas para usuário {user_id}")
    
    return {
        "synced": inserted,
        "message": f"{inserted} {get_message('ACHIEVEMENT_CREATED', getattr(request.state, 'language', 'pt'))}"
    }


@router.delete("/{achievement_id}", response_model=dict)
async def delete_achievement(
    achievement_id: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma conquista"""
    # 🔧 REGRA 2.10: validar ID antes de usar
    try:
        validate_object_id(achievement_id, "achievement_id")
        obj_id = ObjectId(achievement_id)
    except Exception:
        raise ValidationException(
            message_key="ERROR_VALIDATION",
            request=request
        )
    
    result = await db.achievements.delete_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    
    if result.deleted_count == 0:
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    # 🔧 CORRIGIDO: Usa get_message() para mensagem traduzida
    message = get_message(
        "ACHIEVEMENT_DELETED", 
        getattr(request.state, "language", "pt")
    )
    
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
    try:
        validate_object_id(achievement_id, "achievement_id")
        obj_id = ObjectId(achievement_id)
    except Exception:
        raise ValidationException(
            message_key="ERROR_VALIDATION",
            request=request
        )
    
    achievement = await db.achievements.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    
    if not achievement:
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    return format_mongo_doc(achievement)


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
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO