"""
Rotas de Cartões de Crédito
Arquivo: backend/app/routes/credit_cards.py

🔧 CORRIGIDO:
- Alinhada nomenclatura com o model corrigido (total_limit, used_limit, available_limit)
- Removido campo duplicado 'limit'
- Adicionado campo 'available_limit' calculado
- Corrigida validação de redução de limite (considera used_limit + committed_amount)
- Adicionado campo 'available_limit' na resposta
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


# ========== FUNÇÃO AUXILIAR ==========

def add_available_limit(card: dict) -> dict:
    """Adiciona o campo available_limit calculado ao cartão"""
    if card:
        total_limit = card.get("total_limit", 0)
        used_limit = card.get("used_limit", 0)
        committed_amount = card.get("committed_amount", 0)
        card["available_limit"] = total_limit - used_limit - committed_amount
        if card["available_limit"] < 0:
            card["available_limit"] = 0
    return card


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
        # 🔧 CORRIGIDO: nomenclatura alinhada com o model
        if "total_limit" in item:
            item["total_limit"] = from_cents(item["total_limit"])
        if "used_limit" in item:
            item["used_limit"] = from_cents(item["used_limit"])
        if "committed_amount" in item:
            item["committed_amount"] = from_cents(item["committed_amount"])
        # Adiciona available_limit calculado
        item = add_available_limit(item)
    
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
    
    # 🔧 CORRIGIDO: converte total_limit para centavos (int)
    total_limit_cents = to_cents(card_dict.get("total_limit", 0)) if card_dict.get("total_limit") else 0
    card_dict["total_limit"] = total_limit_cents
    
    # 🔧 CORRIGIDO: campos de controle de limite
    card_dict["used_limit"] = 0
    card_dict["committed_amount"] = 0
    card_dict["available_limit"] = total_limit_cents  # inicialmente igual ao total
    
    card_dict["last_statement_closed_at"] = None
    card_dict["next_statement_due_date"] = None
    
    result = await db.credit_cards.insert_one(card_dict)
    created = await db.credit_cards.find_one({"_id": result.inserted_id})
    
    if created:
        if "total_limit" in created:
            created["total_limit"] = from_cents(created["total_limit"])
        if "used_limit" in created:
            created["used_limit"] = from_cents(created["used_limit"])
        if "committed_amount" in created:
            created["committed_amount"] = from_cents(created["committed_amount"])
        created = add_available_limit(created)
    
    logger.info(f"Cartão criado: {card_data.name} (ID: {result.inserted_id}) para usuário {current_user.id} - Limite: R$ {from_cents(total_limit_cents):.2f}")
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
    
    # 🔧 CORRIGIDO: atualização do total_limit
    if "total_limit" in update_data and update_data["total_limit"] is not None:
        new_total_limit_cents = to_cents(update_data["total_limit"])
        update_data["total_limit"] = new_total_limit_cents
        
        # 🔧 CORRIGIDO: verifica se não está reduzindo abaixo do já utilizado
        current_used = card.get("used_limit", 0)
        current_committed = card.get("committed_amount", 0)
        total_used = current_used + current_committed
        
        if new_total_limit_cents < total_used:
            raise HTTPException(
                status_code=400,
                detail=f"Não é possível reduzir o limite abaixo do valor já utilizado (R$ {from_cents(total_used):.2f})"
            )
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$set": update_data}
    )
    
    updated_card = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    
    if updated_card:
        if "total_limit" in updated_card:
            updated_card["total_limit"] = from_cents(updated_card["total_limit"])
        if "used_limit" in updated_card:
            updated_card["used_limit"] = from_cents(updated_card["used_limit"])
        if "committed_amount" in updated_card:
            updated_card["committed_amount"] = from_cents(updated_card["committed_amount"])
        updated_card = add_available_limit(updated_card)
    
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
    
    # Verifica se há compras associadas
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
    
    # 🔧 CORRIGIDO: nomenclatura alinhada
    if "total_limit" in card:
        card["total_limit"] = from_cents(card["total_limit"])
    if "used_limit" in card:
        card["used_limit"] = from_cents(card["used_limit"])
    if "committed_amount" in card:
        card["committed_amount"] = from_cents(card["committed_amount"])
    card = add_available_limit(card)
    
    return format_mongo_doc(card)


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. Alinhada nomenclatura: limit → total_limit, limit_total → used_limit
2. Removido campo duplicado 'limit'
3. Adicionado campo 'available_limit' calculado automaticamente
4. Adicionada função auxiliar add_available_limit()
5. Corrigida validação de redução de limite (considera used_limit + committed_amount)
6. Atualizada criação do cartão com os campos corretos
7. Atualizada listagem e busca com os novos nomes

⚠️ PENDÊNCIAS PARA PÓS-MVP:
================================================================================
1. Internacionalização (i18n) de todas as mensagens de erro
2. Adicionar rota para recalcular limites (caso haja inconsistência)
3. Adicionar suporte a múltiplas faturas (fatura atual, próxima)
4. Adicionar webhook para notificar quando limite estiver próximo do fim

================================================================================
✅ STATUS: CONSISTENTE COM O MODEL CORRIGIDO (credit_card.py)
================================================================================
"""