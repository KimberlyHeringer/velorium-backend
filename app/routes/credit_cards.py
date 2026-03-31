# app/routes/credit_cards.py
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
    try:
        card_dict = card_data.model_dump()
        card_dict["user_id"] = str(current_user.id)
        card_dict["created_at"] = datetime.now(timezone.utc)
        card_dict["updated_at"] = datetime.now(timezone.utc)

        result = await db.credit_cards.insert_one(card_dict)
        created = await db.credit_cards.find_one({"_id": result.inserted_id})
        
        # Converte _id para id e remove o campo original
        created["id"] = str(created.pop("_id"))
        # Garante tipos numéricos
        created["closing_day"] = int(created["closing_day"])
        created["due_day"] = int(created["due_day"])
        
        return created
    except Exception as e:
        print(f"❌ Erro ao criar cartão: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[CreditCardResponse])
async def list_credit_cards(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    cursor = db.credit_cards.find({"user_id": str(current_user.id)}).sort("created_at", -1)
    cards = await cursor.to_list(length=100)
    for c in cards:
        c["_id"] = str(c["_id"])
        c["id"] = c["_id"]          # adiciona campo id
    return cards