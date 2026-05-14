"""
Rotas de Metas Financeiras (Goals)
Arquivo: backend/app/routes/goals.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.goal import Goal, GoalCreate, GoalUpdate, GoalResponse
from app.database import get_database

router = APIRouter(prefix="/goals", tags=["Metas"])


# ========== FUNÇÃO AUXILIAR PARA FORMATAÇÃO ==========

def format_goal_doc(goal: dict) -> dict:
    """Converte _id para id e padroniza resposta"""
    if goal and "_id" in goal:
        goal["id"] = str(goal["_id"])
        goal["_id"] = goal["id"]  # mantém _id também (compatibilidade)
    return goal


# ========== ENDPOINTS ==========

@router.get("/", response_model=List[GoalResponse])
async def list_goals(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista todas as metas do usuário"""
    goals = await db.goals.find({"user_id": current_user.id}).sort("created_at", -1).to_list(100)
    return [format_goal_doc(g) for g in goals]


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    goal: GoalCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova meta"""
    # Arredondar valores
    target = round(goal.target, 2)
    current = round(goal.current, 2)
    
    goal_dict = {
        "user_id": current_user.id,
        "name": goal.name,
        "target": target,
        "current": current,
        "category": goal.category,
        "unit": goal.unit,
        "completed": current >= target,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.goals.insert_one(goal_dict)
    goal_dict["_id"] = str(result.inserted_id)
    return format_goal_doc(goal_dict)


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma meta específica"""
    if not ObjectId.is_valid(goal_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    
    goal = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": current_user.id
    })
    if not goal:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    
    return format_goal_doc(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str,
    updates: GoalUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma meta existente"""
    if not ObjectId.is_valid(goal_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    
    # Verificar se a meta pertence ao usuário
    existing = await db.goals.find_one({
        "_id": ObjectId(goal_id),
        "user_id": current_user.id
    })
    if not existing:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    
    # Preparar dados para atualização
    update_data = {k: v for k, v in updates.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    # Arredondar valores monetários
    if "target" in update_data:
        update_data["target"] = round(update_data["target"], 2)
    if "current" in update_data:
        update_data["current"] = round(update_data["current"], 2)
    
    # Atualizar timestamp
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    # Recalcular completed baseado nos valores (atuais + novos)
    new_target = update_data.get("target", existing["target"])
    new_current = update_data.get("current", existing["current"])
    update_data["completed"] = new_current >= new_target
    
    await db.goals.update_one(
        {"_id": ObjectId(goal_id)},
        {"$set": update_data}
    )
    
    updated = await db.goals.find_one({"_id": ObjectId(goal_id)})
    return format_goal_doc(updated)


@router.delete("/{goal_id}", response_model=dict)
async def delete_goal(
    goal_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma meta"""
    if not ObjectId.is_valid(goal_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    
    result = await db.goals.delete_one({
        "_id": ObjectId(goal_id),
        "user_id": current_user.id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    return {"message": "Meta deletada com sucesso"}