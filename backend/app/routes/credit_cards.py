"""
Rotas de Cartões de Crédito
Arquivo: backend/app/routes/credit_cards.py

🔧 MODIFICADO: Regra 2.2 - Usa format_mongo_doc
🔧 MODIFICADO: Regra 2.8 - Adicionado logger completo
🔧 MODIFICADO: Regra 2.10 - Adicionado validate_object_id
🔧 MODIFICADO: Regra 2.11 - Conversão de moeda para centavos (to_cents/from_cents)
🔧 CORRIGIDO: limit_total agora é igual ao limit (não zero)
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
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/credit-cards", tags=["Cartões de Crédito"])


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
    
    for item in items:
        if "limit" in item:
            item["limit"] = from_cents(item["limit"])
        if "limit_total" in item:
            item["limit_total"] = from_cents(item["limit_total"])
        if "committed_amount" in item:
            item["committed_amount"] = from_cents(item["committed_amount"])
    
    formatted_items = format_mongo_docs(items)
    
    logger.debug(f"Listados {len(formatted_items)} cartões para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


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
    
    # 🔧 REGRA 2.11: converter limit para centavos (int)
    limit_cents = to_cents(card_dict["limit"]) if card_dict.get("limit") else 0
    card_dict["limit"] = limit_cents
    # 🔧 CORREÇÃO: limit_total deve ser igual ao limite do cartão
    card_dict["limit_total"] = limit_cents
    card_dict["committed_amount"] = 0
    card_dict["last_statement_closed_at"] = None
    card_dict["next_statement_due_date"] = None
    
    result = await db.credit_cards.insert_one(card_dict)
    created = await db.credit_cards.find_one({"_id": result.inserted_id})
    
    if created:
        if "limit" in created:
            created["limit"] = from_cents(created["limit"])
        if "limit_total" in created:
            created["limit_total"] = from_cents(created["limit_total"])
        if "committed_amount" in created:
            created["committed_amount"] = from_cents(created["committed_amount"])
    
    logger.info(f"Cartão criado: {card_data.name} (ID: {result.inserted_id}) para usuário {current_user.id} - Limite: R$ {from_cents(limit_cents):.2f}")
    return format_mongo_doc(created)


@router.put("/{card_id}", response_model=CreditCardResponse)
async def update_credit_card(
    card_id: str,
    card_data: CreditCardUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza um cartão existente"""
    validate_object_id(card_id, "card_id")
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        logger.warning(f"Tentativa de atualizar cartão inexistente: {card_id}")
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    update_data = card_data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    if "limit" in update_data and update_data["limit"] is not None:
        new_limit_cents = to_cents(update_data["limit"])
        update_data["limit"] = new_limit_cents
        # 🔧 CORREÇÃO: Ao atualizar o limite, também atualiza limit_total
        # Mas cuidado: não pode reduzir abaixo do que já está comprometido
        current_limit_total = card.get("limit_total", 0)
        new_limit_total = new_limit_cents
        if new_limit_total < card.get("committed_amount", 0):
            raise HTTPException(
                status_code=400,
                detail=f"Não é possível reduzir o limite abaixo do valor já comprometido (R$ {from_cents(card.get('committed_amount', 0)):.2f})"
            )
        update_data["limit_total"] = new_limit_total
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$set": update_data}
    )
    
    updated_card = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    
    if updated_card:
        if "limit" in updated_card:
            updated_card["limit"] = from_cents(updated_card["limit"])
        if "limit_total" in updated_card:
            updated_card["limit_total"] = from_cents(updated_card["limit_total"])
        if "committed_amount" in updated_card:
            updated_card["committed_amount"] = from_cents(updated_card["committed_amount"])
    
    logger.info(f"Cartão atualizado: {card_id} para usuário {current_user.id}")
    return format_mongo_doc(updated_card)


@router.delete("/{card_id}", response_model=dict)
async def delete_credit_card(
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove um cartão de crédito"""
    validate_object_id(card_id, "card_id")
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        logger.warning(f"Tentativa de deletar cartão inexistente: {card_id}")
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    purchases = await db.credit_card_purchases.find_one({"card_id": card_id})
    if purchases:
        logger.warning(f"Tentativa de deletar cartão com compras associadas: {card_id}")
        raise HTTPException(
            status_code=400, 
            detail="Cartão possui compras associadas. Remova as compras primeiro."
        )
    
    await db.credit_cards.delete_one({"_id": ObjectId(card_id)})
    
    logger.info(f"Cartão deletado: {card_id}")
    return {"message": "Cartão removido com sucesso", "success": True}


@router.get("/{card_id}", response_model=CreditCardResponse)
async def get_credit_card(
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca um cartão específico pelo ID"""
    validate_object_id(card_id, "card_id")
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        logger.warning(f"Cartão não encontrado: {card_id}")
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    if "limit" in card:
        card["limit"] = from_cents(card["limit"])
    if "limit_total" in card:
        card["limit_total"] = from_cents(card["limit_total"])
    if "committed_amount" in card:
        card["committed_amount"] = from_cents(card["committed_amount"])
    
    return format_mongo_doc(card)