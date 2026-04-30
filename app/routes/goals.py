# app/routes/goals.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from bson import ObjectId
from datetime import datetime, timezone  # <-- IMPORT FALTANTE
from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.models.goal import Goal, GoalCreate, GoalUpdate
from app.database import get_database

router = APIRouter(prefix="/goals", tags=["Metas"])

@router.get("/", response_model=List[Goal])
async def list_goals(current_user: UserResponse = Depends(get_current_user)):
    db = get_database()
    goals = await db.goals.find({"user_id": current_user.id}).to_list(100)
    for g in goals:
        g["_id"] = str(g["_id"])
    return goals

@router.post("/", response_model=Goal)
async def create_goal(goal: GoalCreate, current_user: UserResponse = Depends(get_current_user)):
    db = get_database()
    goal_dict = goal.model_dump()
    goal_dict["user_id"] = current_user.id
    goal_dict["completed"] = False
    goal_dict["createdAt"] = datetime.now(timezone.utc)
    goal_dict["updatedAt"] = datetime.now(timezone.utc)
    result = await db.goals.insert_one(goal_dict)
    goal_dict["_id"] = str(result.inserted_id)
    # Remove campos que não estão no modelo de resposta? Opcional, mas por segurança:
    # return Goal(**goal_dict)
    return goal_dict

@router.put("/{goal_id}", response_model=Goal)
async def update_goal(goal_id: str, updates: GoalUpdate, current_user: UserResponse = Depends(get_current_user)):
    db = get_database()
    if not ObjectId.is_valid(goal_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    existing = await db.goals.find_one({"_id": ObjectId(goal_id), "user_id": current_user.id})
    if not existing:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    update_data = {k: v for k, v in updates.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updatedAt"] = datetime.now(timezone.utc)
    # Se o usuário atualizou o current, verifica se completou
    if updates.current is not None and not existing.get("completed"):
        new_current = updates.current
        if new_current >= existing["target"]:
            update_data["completed"] = True
    # Se o target foi alterado, talvez reavaliar completed
    if updates.target is not None and not existing.get("completed"):
        new_target = updates.target
        current_current = updates.current if updates.current is not None else existing["current"]
        if current_current >= new_target:
            update_data["completed"] = True
    await db.goals.update_one({"_id": ObjectId(goal_id)}, {"$set": update_data})
    updated = await db.goals.find_one({"_id": ObjectId(goal_id)})
    updated["_id"] = str(updated["_id"])
    return updated

@router.delete("/{goal_id}")
async def delete_goal(goal_id: str, current_user: UserResponse = Depends(get_current_user)):
    db = get_database()
    if not ObjectId.is_valid(goal_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    result = await db.goals.delete_one({"_id": ObjectId(goal_id), "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Meta não encontrada")
    return {"message": "Meta deletada"}