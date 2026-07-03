"""
Rotas de Metas Financeiras (Goals)
Arquivo: backend/app/routes/goals.py

Funcionalidades:
- GET /goals: Listar metas com paginação, filtros e ordenação
- POST /goals: Criar meta financeira
- GET /goals/{id}: Buscar meta específica
- PUT /goals/{id}: Atualizar meta
- DELETE /goals/{id}: Remover meta

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (create: 30/min, update: 20/min, delete: 10/min)
- Campos calculados (progress_percentage, remaining_amount)
- Validação current <= target
- Filtros por status (completed) e categoria
- Ordenação personalizada (sort_by, sort_order)
- SEM history e SEM TTL (modo individual)

Versão: v3.2 (refatorado)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.goal import GoalCreate, GoalUpdate, GoalResponse
from app.database import get_database
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter

# ========== NOVOS IMPORTS ==========
from app.utils.validators_extras import add_calculated_fields

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/goals", tags=["Metas"])


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def list_goals(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    completed: Optional[bool] = Query(None, description="Filtrar por concluídas"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    sort_by: str = Query("created_at", description="Campo para ordenação (created_at, target, current, completed, category)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista as metas do usuário com paginação, filtros e ordenação.
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if completed is not None:
        query["completed"] = completed
    
    if category:
        query["category"] = category
    
    sort_field_mapping = {
        "created_at": "created_at",
        "target": "target",
        "current": "current",
        "completed": "completed",
        "category": "category"
    }
    sort_field = sort_field_mapping.get(sort_by, "created_at")
    sort_direction = -1 if sort_order == "desc" else 1

    items, total = await paginate_query(
        db.goals, query, params, sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        if "target" in item:
            item["target"] = from_cents(item["target"])
        if "current" in item:
            item["current"] = from_cents(item["current"])
        # 🆕 Adiciona campos calculados
        item = add_calculated_fields(item)
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listadas {len(formatted_items)} metas para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_goal(
    request: Request,
    goal: GoalCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova meta"""
    target_cents = to_cents(goal.target)
    current_cents = to_cents(goal.current)
    
    if current_cents > target_cents:
        raise ValidationException(
            message_key="ERROR_GOAL_CURRENT_EXCEEDS_TARGET",
            request=request
        )
    
    goal_dict = {
        "user_id": str(current_user.id),
        "name": goal.name,
        "target": target_cents,
        "current": current_cents,
        "category": goal.category,
        "completed": current_cents >= target_cents,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.goals.insert_one(goal_dict)
    created = await db.goals.find_one({"_id": result.inserted_id})
    
    if created:
        if "target" in created:
            created["target"] = from_cents(created["target"])
        if "current" in created:
            created["current"] = from_cents(created["current"])
        created = add_calculated_fields(created)
    
    logger.info(f"✅ Meta criada: '{goal.name}' para usuário {current_user.id}")
    return convert_objectid_to_str(created)


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    request: Request,
    goal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma meta específica"""
    validate_object_id(goal_id, "goal_id")
    
    goal = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if not goal:
        logger.warning(f"⚠️ Meta não encontrada: {goal_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_GOAL_NOT_FOUND",
            request=request
        )
    
    if "target" in goal:
        goal["target"] = from_cents(goal["target"])
    if "current" in goal:
        goal["current"] = from_cents(goal["current"])
    goal = add_calculated_fields(goal)
    
    logger.debug(f"📊 Meta recuperada: {goal_id} para usuário {current_user.id}")
    return convert_objectid_to_str(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
@limiter.limit("20/minute")
async def update_goal(
    request: Request,
    goal_id: str,
    updates: GoalUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma meta existente"""
    validate_object_id(goal_id, "goal_id")
    
    existing = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if not existing:
        logger.warning(f"⚠️ Meta não encontrada para atualização: {goal_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_GOAL_NOT_FOUND",
            request=request
        )
    
    update_data = {k: v for k, v in updates.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise ValidationException(
            message_key="ERROR_NO_DATA_TO_UPDATE",
            request=request
        )
    
    if "target" in update_data:
        update_data["target"] = to_cents(update_data["target"])
    if "current" in update_data:
        update_data["current"] = to_cents(update_data["current"])
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    new_target = update_data.get("target", existing["target"])
    new_current = update_data.get("current", existing["current"])
    
    if new_current > new_target:
        raise ValidationException(
            message_key="ERROR_GOAL_CURRENT_EXCEEDS_TARGET",
            request=request
        )
    
    update_data["completed"] = new_current >= new_target
    
    await db.goals.update_one(
        {"_id": ObjectId(goal_id)},
        {"$set": update_data}
    )
    
    updated = await db.goals.find_one({"_id": ObjectId(goal_id)})
    
    if updated:
        if "target" in updated:
            updated["target"] = from_cents(updated["target"])
        if "current" in updated:
            updated["current"] = from_cents(updated["current"])
        updated = add_calculated_fields(updated)
    
    logger.info(f"✅ Meta atualizada: {goal_id} para usuário {current_user.id}")
    return convert_objectid_to_str(updated)


@router.delete("/{goal_id}", response_model=dict)
@limiter.limit("10/minute")
async def delete_goal(
    request: Request,
    goal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma meta"""
    validate_object_id(goal_id, "goal_id")
    
    result = await db.goals.delete_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        logger.warning(f"⚠️ Meta não encontrada para deleção: {goal_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_GOAL_NOT_FOUND",
            request=request
        )
    
    language = getattr(request.state, "language", "pt")
    logger.info(f"🗑️ Meta deletada: {goal_id} para usuário {current_user.id}")
    
    return {"message": get_message("SUCCESS_GOAL_DELETED", language), "success": True}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (create: 30/min, update: 20/min, delete: 10/min)
#   - Campos calculados (progress_percentage, remaining_amount)
#   - Validação current <= target
#   - Filtros por status (completed) e categoria
#   - Ordenação personalizada (sort_by, sort_order)
#   - SEM history (modo individual não precisa)
#   - SEM TTL (não temos histórico)
#   - SEM deadline (Pós-MVP)
#
# ❌ Não implementado (Pós-MVP):
#   - Transações MongoDB: Free Tier não suporta (M10+ necessário)
#   - deadline (mudaria o modelo)
#   - updated_by e history (modo individual não precisa)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Rate limiting, filtros, ordenação, campos calculados (30/06/2026)
#   - v3.1: Remoção de unit, sort_by (01/07/2026)
#   - v3.2: Refatoração - add_calculated_fields movido para utils/validators_extras.py (02/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO