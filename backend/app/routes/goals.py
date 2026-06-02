"""
Rotas de Metas Financeiras (Goals)
Arquivo: backend/app/routes/goals.py

🔧 CORREÇÃO: Substituído format_doc por format_mongo_doc (Seção 2.2)
🔧 MODIFICADO: Regra 2.8 - Adicionado logger completo
🔧 MODIFICADO: Regra 2.10 - Usa validate_object_id em vez de validação manual
🔧 MODIFICADO: Regra 2.11 - Conversão de moeda para centavos (to_cents/from_cents)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.goal import GoalCreate, GoalUpdate, GoalResponse
from app.database import get_database
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

router = APIRouter(prefix="/goals", tags=["Metas"])


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def list_goals(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    completed: Optional[bool] = Query(None, description="Filtrar por concluídas"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista as metas do usuário com paginação"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if completed is not None:
        query["completed"] = completed

    items, total = await paginate_query(
        db.goals, query, params, sort=[("created_at", -1)]
    )
    
    # 🔧 REGRA 2.11: converter target e current de centavos para reais (float)
    for item in items:
        if "target" in item:
            item["target"] = from_cents(item["target"])
        if "current" in item:
            item["current"] = from_cents(item["current"])
    
    formatted_items = format_mongo_docs(items)
    
    logger.debug(f"Listadas {len(formatted_items)} metas para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    goal: GoalCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova meta"""
    # 🔧 REGRA 2.11: converter target e current para centavos (int)
    target_cents = to_cents(goal.target)
    current_cents = to_cents(goal.current)
    
    goal_dict = {
        "user_id": str(current_user.id),
        "name": goal.name,
        "target": target_cents,
        "current": current_cents,
        "category": goal.category,
        "unit": goal.unit,
        "completed": current_cents >= target_cents,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.goals.insert_one(goal_dict)
    created = await db.goals.find_one({"_id": result.inserted_id})
    
    # 🔧 REGRA 2.11: converter de volta para reais (float) na resposta
    if created:
        if "target" in created:
            created["target"] = from_cents(created["target"])
        if "current" in created:
            created["current"] = from_cents(created["current"])
    
    logger.info(f"Meta criada: '{goal.name}' ({target_cents} centavos) para usuário {current_user.id}")
    return format_mongo_doc(created)


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma meta específica"""
    # 🔧 REGRA 2.10: usando validate_object_id
    validate_object_id(goal_id, "goal_id")
    
    goal = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if not goal:
        logger.warning(f"Meta não encontrada: {goal_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    
    # 🔧 REGRA 2.11: converter target e current de centavos para reais (float)
    if "target" in goal:
        goal["target"] = from_cents(goal["target"])
    if "current" in goal:
        goal["current"] = from_cents(goal["current"])
    
    logger.debug(f"Meta recuperada: {goal_id} para usuário {current_user.id}")
    return format_mongo_doc(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str,
    updates: GoalUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma meta existente"""
    # 🔧 REGRA 2.10: usando validate_object_id
    validate_object_id(goal_id, "goal_id")
    
    existing = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if not existing:
        logger.warning(f"Meta não encontrada para atualização: {goal_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    
    update_data = {k: v for k, v in updates.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    # 🔧 REGRA 2.11: converter target e current para centavos se presentes
    if "target" in update_data:
        update_data["target"] = to_cents(update_data["target"])
    if "current" in update_data:
        update_data["current"] = to_cents(update_data["current"])
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    new_target = update_data.get("target", existing["target"])
    new_current = update_data.get("current", existing["current"])
    update_data["completed"] = new_current >= new_target
    
    await db.goals.update_one(
        {"_id": ObjectId(goal_id)},
        {"$set": update_data}
    )
    
    updated = await db.goals.find_one({"_id": ObjectId(goal_id)})
    
    # 🔧 REGRA 2.11: converter de volta para reais (float) na resposta
    if updated:
        if "target" in updated:
            updated["target"] = from_cents(updated["target"])
        if "current" in updated:
            updated["current"] = from_cents(updated["current"])
    
    logger.info(f"Meta atualizada: {goal_id} para usuário {current_user.id}")
    return format_mongo_doc(updated)


@router.delete("/{goal_id}", response_model=dict)
async def delete_goal(
    goal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma meta"""
    # 🔧 REGRA 2.10: usando validate_object_id
    validate_object_id(goal_id, "goal_id")
    
    result = await db.goals.delete_one({
        "_id": ObjectId(goal_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        logger.warning(f"Meta não encontrada para deleção: {goal_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    
    logger.info(f"Meta deletada: {goal_id} para usuário {current_user.id}")
    return {"message": "Meta deletada com sucesso", "success": True}