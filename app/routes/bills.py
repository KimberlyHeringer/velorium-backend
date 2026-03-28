from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from bson import ObjectId

from app.database import get_database
from app.models.bill import BillCreate, BillResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/bills", tags=["Contas a Pagar"])

@router.post("/", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    bill_data: BillCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Por enquanto, cria um único documento (não gera parcelas)
    bill_dict = bill_data.model_dump()
    bill_dict["user_id"] = str(current_user.id)
    bill_dict["paid"] = False
    bill_dict["created_at"] = datetime.now(timezone.utc)
    bill_dict["updated_at"] = datetime.now(timezone.utc)
    # Converte Decimal para float para MongoDB
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