from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.bill import BillCreate, BillResponse, BillUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/bills", tags=["Contas a Pagar"])


@router.post("/", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    bill_data: BillCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    bill_dict = bill_data.model_dump()
    bill_dict["user_id"] = str(current_user.id)
    bill_dict["paid"] = False
    bill_dict["created_at"] = datetime.now(timezone.utc)
    bill_dict["updated_at"] = datetime.now(timezone.utc)
    # Converte Decimal para float (se houver Decimal)
    if "amount" in bill_dict:
        bill_dict["amount"] = float(bill_dict["amount"])

    result = await db.bills.insert_one(bill_dict)
    created = await db.bills.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    return created


@router.get("/", response_model=List[BillResponse])
async def list_bills(
    paid: Optional[bool] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    query = {"user_id": str(current_user.id)}
    if paid is not None:
        query["paid"] = paid

    cursor = db.bills.find(query).sort("created_at", -1)
    bills = await cursor.to_list(length=100)
    for b in bills:
        b["_id"] = str(b["_id"])
    return bills


@router.get("/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if not bill:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    bill["_id"] = str(bill["_id"])
    return bill


@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill(
    bill_id: str,
    bill_update: BillUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    update_data = {k: v for k, v in bill_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    update_data["updated_at"] = datetime.now(timezone.utc)

    # Se amount for fornecido, converter para float
    if "amount" in update_data:
        update_data["amount"] = float(update_data["amount"])

    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    updated = await db.bills.find_one({"_id": ObjectId(bill_id)})
    updated["_id"] = str(updated["_id"])
    return updated


@router.delete("/{bill_id}", response_model=dict)
async def delete_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    result = await db.bills.delete_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return {"message": "Conta deletada com sucesso"}