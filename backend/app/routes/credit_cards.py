"""
Rotas de Cartões de Crédito
Arquivo: backend/app/routes/credit_cards.py
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone

from app.database import get_database
from app.models.credit_card import CreditCardCreate, CreditCardResponse, CreditCardUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate

router = APIRouter(prefix="/credit-cards", tags=["Cartões de Crédito"])


# ========== FUNÇÃO AUXILIAR PADRONIZADA ==========
def format_doc(doc: dict) -> dict:
    """Converte _id para id e padroniza resposta"""
    if doc and "_id" in doc:
        result = dict(doc)
        result["id"] = str(result.pop("_id"))
        return result
    return doc


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def get_credit_cards(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista todos os cartões do usuário com paginação"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}

    items, total = await paginate_query(
        db.credit_cards, query, params, sort=[("created_at", -1)]
    )
    
    formatted_items = [format_doc(item) for item in items]
    
    return paginate(formatted_items, total, params)


@router.post("/", response_model=CreditCardResponse, status_code=status.HTTP_201_CREATED)
async def create_credit_card(
    card_data: CreditCardCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria um novo cartão de crédito"""
    card_dict = card_data.model_dump()
    card_dict["user_id"] = str(current_user.id)
    card_dict["created_at"] = datetime.now(timezone.utc)
    card_dict["updated_at"] = datetime.now(timezone.utc)
    card_dict["limit_total"] = 0.0
    card_dict["committed_amount"] = 0.0
    card_dict["last_statement_closed_at"] = None
    card_dict["next_statement_due_date"] = None
    
    result = await db.credit_cards.insert_one(card_dict)
    card_dict["_id"] = result.inserted_id
    
    return format_doc(card_dict)


@router.put("/{card_id}", response_model=CreditCardResponse)
async def update_credit_card(
    card_id: str,
    card_data: CreditCardUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza um cartão existente"""
    # Verifica se o cartão existe e pertence ao usuário
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    # Prepara os dados para atualização
    update_data = card_data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    # Atualiza o cartão
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$set": update_data}
    )
    
    # Busca o cartão atualizado
    updated_card = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    return format_doc(updated_card)


@router.delete("/{card_id}", response_model=dict)
async def delete_credit_card(
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove um cartão de crédito"""
    # Verifica se o cartão existe e pertence ao usuário
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    # Verifica se há compras associadas
    purchases = await db.credit_card_purchases.find_one({"card_id": card_id})
    if purchases:
        raise HTTPException(
            status_code=400, 
            detail="Cartão possui compras associadas. Remova as compras primeiro."
        )
    
    # Remove o cartão
    await db.credit_cards.delete_one({"_id": ObjectId(card_id)})
    
    return {"message": "Cartão removido com sucesso"}


@router.get("/{card_id}", response_model=CreditCardResponse)
async def get_credit_card(
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca um cartão específico pelo ID"""
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    return format_doc(card)