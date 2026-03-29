from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.credit_card import CreditCardCreate, CreditCardResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/credit-cards", tags=["Cartões de Crédito"])

@router.post("/", response_model=CreditCardResponse, status_code=status.HTTP_201_CREATED)
async def create_credit_card(
    card_data: CreditCardCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    card_dict = card_data.model_dump()
    card_dict["user_id"] = str(current_user.id)
    card_dict["created_at"] = datetime.now(timezone.utc)
    card_dict["updated_at"] = datetime.now(timezone.utc)

    result = await db.credit_cards.insert_one(card_dict)
    created = await db.credit_cards.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    return created

@router.get("/", response_model=List[CreditCardResponse])
async def list_credit_cards(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    cursor = db.credit_cards.find({"user_id": str(current_user.id)}).sort("created_at", -1)
    cards = await cursor.to_list(length=100)
    for c in cards:
        c["_id"] = str(c["_id"])
    return cards