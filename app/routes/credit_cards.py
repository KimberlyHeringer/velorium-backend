from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.credit_card import CreditCardCreate, CreditCardResponse, CreditCardUpdate
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
        c["id"] = str(c.pop("_id"))  # remove _id e cria id
        c["closing_day"] = int(c["closing_day"])
        c["due_day"] = int(c["due_day"])
    return cards

@router.put("/{card_id}", response_model=CreditCardResponse)
async def update_credit_card(
    card_id: str,
    card_data: CreditCardUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar se o cartão pertence ao usuário
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    update_data = {k: v for k, v in card_data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$set": update_data}
    )
    
    updated = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    updated["id"] = str(updated.pop("_id"))
    updated["closing_day"] = int(updated["closing_day"])
    updated["due_day"] = int(updated["due_day"])
    return updated

@router.delete("/{card_id}", response_model=dict)
async def delete_credit_card(
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    result = await db.credit_cards.delete_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    return {"message": "Cartão excluído com sucesso"}