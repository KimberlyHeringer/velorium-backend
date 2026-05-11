"""
Rotas de Cartões de Crédito
Arquivo: backend/app/routes/credit_cards.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.credit_card import CreditCardCreate, CreditCardResponse, CreditCardUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/credit-cards", tags=["Cartões de Crédito"])


# ========== FUNÇÃO AUXILIAR PARA FORMATAÇÃO ==========

def format_card_doc(card: dict) -> dict:
    """
    Converte _id para id e garante tipos numéricos.
    Usado para padronizar respostas da API.
    """
    if card and "_id" in card:
        card["id"] = str(card.pop("_id"))
        card["closing_day"] = int(card["closing_day"])
        card["due_day"] = int(card["due_day"])
    return card


# ========== ENDPOINTS ==========

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
        
        return format_card_doc(created)
        
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
    return [format_card_doc(c) for c in cards]


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
    
    # Preparar dados para atualização
    update_data = {k: v for k, v in card_data.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    # Arredondar valores monetários se presentes
    if "limit_total" in update_data:
        update_data["limit_total"] = round(update_data["limit_total"], 2)
    if "committed_amount" in update_data:
        update_data["committed_amount"] = round(update_data["committed_amount"], 2)
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$set": update_data}
    )
    
    updated = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    return format_card_doc(updated)


@router.delete("/{card_id}", response_model=dict)
async def delete_credit_card(
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # ========== VERIFICAR SE EXISTEM COMPRAS ASSOCIADAS ==========
    # Evita deletar cartão que já tem compras vinculadas (dados órfãos)
    purchase = await db.credit_card_purchases.find_one({
        "card_id": card_id,
        "user_id": str(current_user.id)
    })
    if purchase:
        raise HTTPException(
            status_code=400,
            detail="Não é possível excluir o cartão porque existem compras vinculadas. Exclua as compras primeiro."
        )
    
    result = await db.credit_cards.delete_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    return {"message": "Cartão excluído com sucesso"}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Adicionada função format_card_doc() para padronizar respostas
# ✅ Adicionada verificação de compras associadas antes de deletar cartão
# ✅ Arredondamento de limit_total e committed_amount no update
# ✅ Todas as rotas usam format_card_doc() agora
#
# 📌 Pendente (futuro):
#    - Paginação no list_credit_cards (pós-MVP)
#    - Logging estruturado (substituir print)
#
# 🔍 Verificação necessária:
#    - Modelo CreditCard deve ter validador closing_day != due_day
#      (adicionar se não existir)