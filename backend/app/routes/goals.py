"""
Rotas de Metas Financeiras (Goals)
Arquivo: backend/app/routes/goals.py

Funcionalidades:
- GET /goals: Listar metas com paginação, filtros e ordenação
- POST /goals: Criar meta financeira
- GET /goals/{id}: Buscar meta específica
- PUT /goals/{id}: Atualizar meta
- DELETE /goals/{id}: Remover meta
- GET /goals/history: Listar metas arquivadas (histórico)
- GET /goals/sub: Buscar sub-metas de uma meta pai
- POST /goals/{id}/sub: Adicionar sub-meta

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (create: 30/min, update: 20/min, delete: 10/min)
- Campos calculados (progress_percentage, remaining_amount, days_until_deadline, is_overdue)
- Validação current <= target
- 🆕 Validação de profundidade de sub-metas (máx 3 níveis)
- 🆕 Validação de parent_id existente
- 🆕 archive_completed_goal integrado ao update
- Filtros: completed, category, parent_id, recurring, has_deadline, archived
- Ordenação: created_at, target, current, completed, category, deadline, completed_at
- Suporte a metas recorrentes (recurring, recurring_interval)
- Suporte a sub-metas (parent_id)
- Suporte a data limite (deadline)
- Histórico de metas concluídas/arquivadas

Versão: v4.3 (correção paginate_query com collection_name)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.goal import GoalCreate, GoalUpdate, GoalResponse
from app.database import get_database
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter, get_user_rate_limit_key

# ========== NOVOS IMPORTS ==========
from app.utils.validators_extras import add_calculated_fields

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/goals", tags=["Metas"])

# ================================================================
# CONSTANTES
# ================================================================

MAX_SUB_GOAL_DEPTH = 3  # Máximo de 3 níveis de sub-metas


# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================

async def validate_parent_exists(db, parent_id: str, user_id: str, request: Request = None):
    """
    🔧 NOVO: Valida se a meta pai existe e pertence ao usuário.
    
    Args:
        db: Conexão com o banco
        parent_id: ID da meta pai
        user_id: ID do usuário
        request: Objeto Request para i18n
    
    Returns:
        dict: Documento da meta pai
    
    Raises:
        NotFoundException: Se a meta pai não for encontrada
    """
    validate_object_id(parent_id, "parent_id")
    
    parent = await db.goals.find_one({
        "_id": ObjectId(parent_id),
        "user_id": user_id
    })
    
    if not parent:
        raise NotFoundException(
            message_key="ERROR_GOAL_NOT_FOUND",
            request=request
        )
    
    if parent.get("archived", False):
        raise ValidationException(
            message_key="ERROR_CANNOT_ADD_SUBGOAL_TO_ARCHIVED",
            request=request
        )
    
    if parent.get("recurring", False):
        raise ValidationException(
            message_key="ERROR_CANNOT_ADD_SUBGOAL_TO_RECURRING",
            request=request
        )
    
    return parent


async def validate_sub_goal_depth(db, parent_id: str, user_id: str, current_depth: int = 0, request: Request = None):
    """
    🔧 NOVO: Valida a profundidade das sub-metas (máximo MAX_SUB_GOAL_DEPTH níveis).
    
    Args:
        db: Conexão com o banco
        parent_id: ID da meta pai
        user_id: ID do usuário
        current_depth: Profundidade atual (começa em 0)
        request: Objeto Request para i18n
    
    Raises:
        ValidationException: Se a profundidade máxima for excedida
    """
    if current_depth >= MAX_SUB_GOAL_DEPTH:
        raise ValidationException(
            message_key="ERROR_SUBGOAL_MAX_DEPTH",
            request=request,
            params={"max_depth": MAX_SUB_GOAL_DEPTH}
        )
    
    # Busca a meta pai para continuar a verificação
    parent = await db.goals.find_one({
        "_id": ObjectId(parent_id),
        "user_id": user_id
    })
    
    if parent and parent.get("parent_id"):
        await validate_sub_goal_depth(
            db,
            parent["parent_id"],
            user_id,
            current_depth + 1,
            request
        )


async def recalculate_parent_progress(parent_id: str, user_id: str, db):
    """
    Recalcula o progresso da meta pai baseado nas sub-metas.
    Soma os valores atuais de todas as sub-metas e atualiza a meta pai.
    """
    sub_goals = await db.goals.find({
        "parent_id": parent_id,
        "user_id": user_id,
        "archived": False
    }).to_list(100)
    
    if not sub_goals:
        return
    
    total_current = sum(g.get("current", 0) for g in sub_goals)
    total_target = sum(g.get("target", 0) for g in sub_goals)
    
    parent = await db.goals.find_one({
        "_id": ObjectId(parent_id),
        "user_id": user_id
    })
    
    if not parent:
        return
    
    # Atualiza a meta pai com a soma das sub-metas
    update_data = {
        "current": total_current,
        "target": total_target,
        "updated_at": datetime.now(timezone.utc),
        "completed": total_current >= total_target
    }
    
    if update_data["completed"] and parent.get("completed_at") is None:
        update_data["completed_at"] = datetime.now(timezone.utc)
    
    await db.goals.update_one(
        {"_id": ObjectId(parent_id)},
        {"$set": update_data}
    )


async def archive_completed_goal(goal_id: str, user_id: str, db):
    """
    🔧 CORRIGIDO: Arquivar uma meta concluída (move para histórico).
    """
    goal = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": user_id
    })
    
    if not goal:
        return
    
    if goal.get("completed", False) and not goal.get("archived", False):
        await db.goals.update_one(
            {"_id": ObjectId(goal_id)},
            {
                "$set": {
                    "archived": True,
                    "completed_at": goal.get("completed_at") or datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        logger.info(f"📦 Meta arquivada: {goal_id}")


# ================================================================
# ENDPOINTS
# ================================================================

@router.get("/", response_model=dict)
async def list_goals(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    completed: Optional[bool] = Query(None, description="Filtrar por concluídas"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    parent_id: Optional[str] = Query(None, description="Filtrar sub-metas de uma meta pai"),
    recurring: Optional[bool] = Query(None, description="Filtrar metas recorrentes"),
    has_deadline: Optional[bool] = Query(None, description="Filtrar metas com data limite"),
    archived: Optional[bool] = Query(False, description="Filtrar metas arquivadas"),
    search: Optional[str] = Query(None, description="Buscar por nome"),
    sort_by: str = Query("created_at", description="Campo para ordenação (created_at, target, current, completed, category, deadline, completed_at, progress_percentage)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista as metas do usuário com paginação, filtros e ordenação.
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if archived is None:
        query["archived"] = False
    elif archived is not None:
        query["archived"] = archived
    
    if completed is not None:
        query["completed"] = completed
    
    if category:
        query["category"] = category
    
    if parent_id:
        validate_object_id(parent_id, "parent_id")
        query["parent_id"] = parent_id
    
    if recurring is not None:
        query["recurring"] = recurring
    
    if has_deadline is not None:
        if has_deadline:
            query["deadline"] = {"$ne": None}
        else:
            query["deadline"] = None
    
    if search:
        query["$text"] = {"$search": search}
    
    sort_field_mapping = {
        "created_at": "created_at",
        "target": "target",
        "current": "current",
        "completed": "completed",
        "category": "category",
        "deadline": "deadline",
        "completed_at": "completed_at",
        "progress_percentage": "progress_percentage",
        "updated_at": "updated_at"
    }
    sort_field = sort_field_mapping.get(sort_by, "created_at")
    sort_direction = -1 if sort_order == "desc" else 1

    # 🔧 CORRIGIDO: Adicionado collection_name e user_id
    items, total = await paginate_query(
        collection=db.goals,
        collection_name="goals",
        query=query,
        params=params,
        user_id=str(current_user.id),
        sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        if "target" in item:
            item["target"] = from_cents(item["target"])
        if "current" in item:
            item["current"] = from_cents(item["current"])
        item = add_calculated_fields(item)
        
        if item.get("deadline"):
            delta = item["deadline"] - datetime.now(timezone.utc)
            item["days_until_deadline"] = max(0, delta.days)
            item["is_overdue"] = datetime.now(timezone.utc) > item["deadline"] and not item.get("completed", False)
    
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
    """Cria uma nova meta com validação de sub-metas."""
    target_cents = to_cents(goal.target)
    current_cents = to_cents(goal.current)
    
    if current_cents > target_cents:
        raise ValidationException(
            message_key="ERROR_GOAL_CURRENT_EXCEEDS_TARGET",
            request=request
        )
    
    # 🔧 NOVO: Valida parent_id existente e profundidade
    if goal.parent_id:
        await validate_parent_exists(db, goal.parent_id, str(current_user.id), request)
        await validate_sub_goal_depth(db, goal.parent_id, str(current_user.id), 0, request)
    
    goal_dict = {
        "user_id": str(current_user.id),
        "name": goal.name,
        "target": target_cents,
        "current": current_cents,
        "category": goal.category,
        "description": goal.description,
        "completed": current_cents >= target_cents,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "recurring": goal.recurring,
        "recurring_interval": goal.recurring_interval,
        "deadline": goal.deadline,
        "parent_id": goal.parent_id,
        "completed_at": datetime.now(timezone.utc) if current_cents >= target_cents else None,
        "archived": False,
    }
    
    result = await db.goals.insert_one(goal_dict)
    created = await db.goals.find_one({"_id": result.inserted_id})
    
    if goal.parent_id:
        await recalculate_parent_progress(goal.parent_id, str(current_user.id), db)
    
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
    
    if not goal.get("parent_id"):
        sub_goals = await db.goals.find({
            "parent_id": goal_id,
            "user_id": str(current_user.id),
            "archived": False
        }).to_list(100)
        goal["children"] = [convert_objectid_to_str(add_calculated_fields(sg)) for sg in sub_goals]
    
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
    """Atualiza uma meta existente com validação de sub-metas."""
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
    
    # 🔧 NOVO: Valida parent_id existente e profundidade se estiver sendo alterado
    new_parent_id = update_data.get("parent_id")
    if new_parent_id:
        await validate_parent_exists(db, new_parent_id, str(current_user.id), request)
        await validate_sub_goal_depth(db, new_parent_id, str(current_user.id), 0, request)
    
    # Atualiza completed e completed_at
    was_completed = existing.get("completed", False)
    new_completed = new_current >= new_target
    
    update_data["completed"] = new_completed
    if new_completed and not was_completed:
        update_data["completed_at"] = datetime.now(timezone.utc)
        # 🔧 CORRIGIDO: Chama archive_completed_goal quando completa
        await archive_completed_goal(goal_id, str(current_user.id), db)
    elif not new_completed:
        update_data["completed_at"] = None
    
    if update_data.get("archived") and not update_data.get("completed_at"):
        update_data["completed_at"] = datetime.now(timezone.utc)
    
    if update_data.get("archived") is False and not new_completed:
        update_data["completed_at"] = None
    
    old_parent_id = existing.get("parent_id")
    
    await db.goals.update_one(
        {"_id": ObjectId(goal_id)},
        {"$set": update_data}
    )
    
    if old_parent_id and old_parent_id != new_parent_id:
        await recalculate_parent_progress(old_parent_id, str(current_user.id), db)
    if new_parent_id and new_parent_id != old_parent_id:
        await recalculate_parent_progress(new_parent_id, str(current_user.id), db)
    
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
    """Remove uma meta (ou arquiva se tiver sub-metas)"""
    validate_object_id(goal_id, "goal_id")
    
    existing = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if not existing:
        logger.warning(f"⚠️ Meta não encontrada para deleção: {goal_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_GOAL_NOT_FOUND",
            request=request
        )
    
    sub_goals = await db.goals.find({
        "parent_id": goal_id,
        "user_id": str(current_user.id)
    }).to_list(1)
    
    if sub_goals:
        await db.goals.update_one(
            {"_id": ObjectId(goal_id)},
            {
                "$set": {
                    "archived": True,
                    "completed": True,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        language = getattr(request.state, "language", "pt")
        return {
            "message": get_message("SUCCESS_GOAL_ARCHIVED", language),
            "success": True,
            "archived": True
        }
    
    result = await db.goals.delete_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise NotFoundException(
            message_key="ERROR_GOAL_NOT_FOUND",
            request=request
        )
    
    language = getattr(request.state, "language", "pt")
    logger.info(f"🗑️ Meta deletada: {goal_id} para usuário {current_user.id}")
    
    return {"message": get_message("SUCCESS_GOAL_DELETED", language), "success": True}


# ================================================================
# ENDPOINT: HISTÓRICO
# ================================================================

@router.get("/history", response_model=dict)
async def get_goal_history(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    sort_by: str = Query("completed_at", description="Campo para ordenação (completed_at, target, category)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista metas arquivadas (histórico de metas concluídas).
    """
    params = PaginationParams(page=page, limit=limit)
    query = {
        "user_id": str(current_user.id),
        "archived": True
    }
    
    if category:
        query["category"] = category
    
    sort_field_mapping = {
        "completed_at": "completed_at",
        "target": "target",
        "category": "category",
        "created_at": "created_at"
    }
    sort_field = sort_field_mapping.get(sort_by, "completed_at")
    sort_direction = -1 if sort_order == "desc" else 1

    # 🔧 CORRIGIDO: Adicionado collection_name e user_id
    items, total = await paginate_query(
        collection=db.goals,
        collection_name="goals_history",
        query=query,
        params=params,
        user_id=str(current_user.id),
        sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        if "target" in item:
            item["target"] = from_cents(item["target"])
        if "current" in item:
            item["current"] = from_cents(item["current"])
        item = add_calculated_fields(item)
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listadas {len(formatted_items)} metas no histórico para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


# ================================================================
# ENDPOINT: SUB-METAS
# ================================================================

@router.get("/sub", response_model=dict)
async def get_sub_goals(
    request: Request,
    parent_id: str = Query(..., description="ID da meta pai"),
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    completed: Optional[bool] = Query(None, description="Filtrar por concluídas"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista sub-metas de uma meta pai.
    """
    validate_object_id(parent_id, "parent_id")
    
    params = PaginationParams(page=page, limit=limit)
    query = {
        "user_id": str(current_user.id),
        "parent_id": parent_id,
        "archived": False
    }
    
    if completed is not None:
        query["completed"] = completed
    
    # 🔧 CORRIGIDO: Adicionado collection_name e user_id
    items, total = await paginate_query(
        collection=db.goals,
        collection_name="goals_sub",
        query=query,
        params=params,
        user_id=str(current_user.id),
        sort=[("created_at", 1)]
    )
    
    for item in items:
        if "target" in item:
            item["target"] = from_cents(item["target"])
        if "current" in item:
            item["current"] = from_cents(item["current"])
        item = add_calculated_fields(item)
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listadas {len(formatted_items)} sub-metas para meta pai {parent_id}")
    return paginate(formatted_items, total, params).model_dump()


# ================================================================
# ENDPOINT: ADICIONAR SUB-META
# ================================================================

@router.post("/{goal_id}/sub", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def add_sub_goal(
    request: Request,
    goal_id: str,
    sub_goal: GoalCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Adiciona uma sub-meta a uma meta pai com validação de profundidade.
    """
    validate_object_id(goal_id, "goal_id")
    
    # 🔧 NOVO: Valida meta pai existente e profundidade
    await validate_parent_exists(db, goal_id, str(current_user.id), request)
    await validate_sub_goal_depth(db, goal_id, str(current_user.id), 0, request)
    
    target_cents = to_cents(sub_goal.target)
    current_cents = to_cents(sub_goal.current)
    
    if current_cents > target_cents:
        raise ValidationException(
            message_key="ERROR_GOAL_CURRENT_EXCEEDS_TARGET",
            request=request
        )
    
    sub_goal_dict = {
        "user_id": str(current_user.id),
        "name": sub_goal.name,
        "target": target_cents,
        "current": current_cents,
        "category": sub_goal.category,
        "description": sub_goal.description,
        "parent_id": goal_id,
        "completed": current_cents >= target_cents,
        "recurring": False,
        "recurring_interval": None,
        "deadline": None,
        "completed_at": datetime.now(timezone.utc) if current_cents >= target_cents else None,
        "archived": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.goals.insert_one(sub_goal_dict)
    created = await db.goals.find_one({"_id": result.inserted_id})
    
    await recalculate_parent_progress(goal_id, str(current_user.id), db)
    
    if created:
        if "target" in created:
            created["target"] = from_cents(created["target"])
        if "current" in created:
            created["current"] = from_cents(created["current"])
        created = add_calculated_fields(created)
    
    logger.info(f"✅ Sub-meta criada: '{sub_goal.name}' para meta pai {goal_id}")
    return convert_objectid_to_str(created)


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================

"""
📋 CHANGELOG - 18/07/2026
──────────────────────────────────────────────────────────────

🆕 ADICIONADO:
   1. validate_parent_exists() - Valida se meta pai existe
   2. validate_sub_goal_depth() - Valida profundidade de sub-metas (máx 3 níveis)
   3. MAX_SUB_GOAL_DEPTH = 3
   4. archive_completed_goal() agora é chamada no update quando completada
   5. Validação de parent_id no create_goal
   6. Validação de parent_id no update_goal
   7. Validação de profundidade no add_sub_goal

✅ CORRIGIDO:
   8. archive_completed_goal agora é utilizada
   9. Validação de parent_id existente em todos os endpoints
   10. 🔧 CORRIGIDO: Chamada do paginate_query com collection_name (obrigatório)
   11. 🔧 CORRIGIDO: Adicionado user_id em todas as chamadas do paginate_query
   12. 🔧 CORRIGIDO: collection_name="goals", "goals_history", "goals_sub"

📋 PENDÊNCIAS (PÓS-MVP):
   - Migração para adicionar campo description nas metas existentes

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 18/07/2026
"""