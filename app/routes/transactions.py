from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from bson import ObjectId

from app.database import get_database
from app.models.transaction import TransactionCreate, TransactionUpdate, TransactionResponse, TransactionBalance
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["Transações"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    transaction_dict = transaction_data.model_dump()
    transaction_dict["user_id"] = str(current_user.id)
    if transaction_dict.get("date") is None:
        transaction_dict["date"] = datetime.now(timezone.utc)
    transaction_dict["created_at"] = datetime.now(timezone.utc)
    transaction_dict["updated_at"] = datetime.now(timezone.utc)

    result = await db.transactions.insert_one(transaction_dict)
    return {"id": str(result.inserted_id), "message": "Transação criada com sucesso"}


@router.get("/", response_model=List[TransactionResponse])
async def get_transactions(
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    query = {"user_id": str(current_user.id)}
    if context:
        query["context"] = context
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date

    cursor = db.transactions.find(query).sort("date", -1).skip(skip).limit(limit)
    transactions = await cursor.to_list(length=limit)
    for t in transactions:
        t["_id"] = str(t["_id"])
    return transactions


@router.get("/balance", response_model=TransactionBalance)
async def get_balance(
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    match = {"user_id": str(current_user.id)}
    if context:
        match["context"] = context

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "total_income": {"$sum": {"$cond": [{"$eq": ["$type", "income"]}, "$amount", 0]}},
            "total_expense": {"$sum": {"$cond": [{"$eq": ["$type", "expense"]}, "$amount", 0]}}
        }}
    ]

    result = await db.transactions.aggregate(pipeline).to_list(1)
    if result:
        income = float(result[0]["total_income"])
        expense = float(result[0]["total_expense"])
        return TransactionBalance(
            income=income,
            expense=expense,
            balance=income - expense,
            context=context
        )
    return TransactionBalance(
        income=0.0,
        expense=0.0,
        balance=0.0,
        context=context
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    transaction = await db.transactions.find_one({
        "_id": ObjectId(transaction_id),
        "user_id": str(current_user.id)
    })
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    transaction["_id"] = str(transaction["_id"])
    return transaction


@router.put("/{transaction_id}", response_model=dict)
async def update_transaction(
    transaction_id: str,
    transaction_update: TransactionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Remover campos None
    update_data = {k: v for k, v in transaction_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.transactions.update_one(
        {"_id": ObjectId(transaction_id), "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    return {"message": "Transação atualizada com sucesso"}


@router.delete("/{transaction_id}", response_model=dict)
async def delete_transaction(
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    result = await db.transactions.delete_one({
        "_id": ObjectId(transaction_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    return {"message": "Transação deletada com sucesso"}