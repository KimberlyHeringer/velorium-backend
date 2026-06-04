"""
Rotas de Transações Financeiras (Receitas e Despesas)
Arquivo: backend/app/routes/transactions.py

🔧 MODIFICADO: Regra 2.11 - Conversão de moeda para centavos (to_cents/from_cents)
🔧 MODIFICADO: Regra 2.12 - Integração com cartão de crédito
🔧 CORRIGIDO: Ordem das operações (primeiro valida cartão, depois cria transação)
🔧 CORRIGIDO: Log detalhado do erro de validação
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.transaction import TransactionCreate, TransactionUpdate, TransactionResponse, TransactionBalance
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, PaginatedResponse, paginate, paginate_query
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transações"])


# ========== FUNÇÕES AUXILIARES PARA CARTÃO ==========

async def validate_and_create_credit_card_purchase(
    user_id: str,
    transaction_data: dict,
    db
):
    """Valida e cria uma compra no cartão de crédito."""
    from app.routes.credit_card_purchases import split_amount
    
    card_id = transaction_data.get("card_id")
    amount = transaction_data.get("amount")
    description = transaction_data.get("description", "")
    installments = transaction_data.get("installments", 1)
    first_due_date = transaction_data.get("first_due_date")
    category = transaction_data.get("category")
    notes = transaction_data.get("notes")
    
    if not card_id:
        raise HTTPException(status_code=400, detail="Cartão de crédito não selecionado")
    
    try:
        card = await db.credit_cards.find_one({
            "_id": ObjectId(card_id),
            "user_id": user_id
        })
    except Exception as e:
        logger.error(f"Erro ao buscar cartão {card_id}: {e}")
        raise HTTPException(status_code=400, detail=f"ID do cartão inválido: {card_id}")
    
    if not card:
        raise HTTPException(status_code=404, detail=f"Cartão não encontrado para o ID: {card_id}")
    
    # Log dos dados do cartão para debug
    logger.info(f"Cartão encontrado: limit_total={card.get('limit_total')}, committed_amount={card.get('committed_amount')}")
    
    limit_total = card.get("limit_total", 0)
    committed_amount = card.get("committed_amount", 0)
    available = limit_total - committed_amount
    
    if amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Limite insuficiente. Disponível: R$ {from_cents(available):.2f}, Necessário: R$ {from_cents(amount):.2f}. Limite total: R$ {from_cents(limit_total):.2f}, Comprometido: R$ {from_cents(committed_amount):.2f}"
        )
    
    purchase_dict = {
        "card_id": card_id,
        "user_id": user_id,
        "description": description,
        "total_amount": amount,
        "installments": installments,
        "first_due_date": first_due_date or datetime.now(timezone.utc),
        "category": category,
        "notes": notes,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.credit_card_purchases.insert_one(purchase_dict)
    purchase_id = str(result.inserted_id)
    
    total_amount_reais = from_cents(amount)
    amounts = split_amount(total_amount_reais, installments)
    first_due = purchase_dict["first_due_date"]
    
    from dateutil.relativedelta import relativedelta
    
    installments_list = []
    for i in range(installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "card_id": card_id,
            "amount": to_cents(amounts[i]),
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments_list.append(installment)
    
    if installments_list:
        await db.credit_card_installments.insert_many(installments_list)
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$inc": {"committed_amount": amount}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )
    
    logger.info(f"Compra no cartão criada: {purchase_id}")
    return purchase_id


async def create_credit_card_purchase_from_transaction(
    transaction_id: str,
    user_id: str,
    transaction_data: dict,
    db
):
    """Cria compra no cartão após transação criada."""
    from app.routes.credit_card_purchases import split_amount
    
    card_id = transaction_data.get("card_id")
    amount = transaction_data.get("amount")
    description = transaction_data.get("description", "")
    installments = transaction_data.get("installments", 1)
    first_due_date = transaction_data.get("first_due_date")
    category = transaction_data.get("category")
    notes = transaction_data.get("notes")
    
    purchase_dict = {
        "card_id": card_id,
        "user_id": user_id,
        "description": description,
        "total_amount": amount,
        "installments": installments,
        "first_due_date": first_due_date or datetime.now(timezone.utc),
        "category": category,
        "notes": notes,
        "transaction_id": transaction_id,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.credit_card_purchases.insert_one(purchase_dict)
    purchase_id = str(result.inserted_id)
    
    total_amount_reais = from_cents(amount)
    amounts = split_amount(total_amount_reais, installments)
    first_due = purchase_dict["first_due_date"]
    
    from dateutil.relativedelta import relativedelta
    
    installments_list = []
    for i in range(installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "card_id": card_id,
            "amount": to_cents(amounts[i]),
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments_list.append(installment)
    
    if installments_list:
        await db.credit_card_installments.insert_many(installments_list)
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$inc": {"committed_amount": amount}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )
    
    return purchase_id


async def update_credit_card_purchase_from_transaction(
    transaction_id: str,
    user_id: str,
    transaction_data: dict,
    db
):
    """Atualiza compra no cartão associada à despesa."""
    purchase = await db.credit_card_purchases.find_one({
        "transaction_id": transaction_id,
        "user_id": user_id
    })
    
    if not purchase:
        return await create_credit_card_purchase_from_transaction(transaction_id, user_id, transaction_data, db)
    
    paid_installments = await db.credit_card_installments.find_one({
        "purchase_id": purchase["_id"],
        "paid": True
    })
    
    if paid_installments:
        raise HTTPException(
            status_code=400,
            detail="Não é possível editar despesa que já possui parcelas pagas no cartão."
        )
    
    card_id = transaction_data.get("card_id", purchase.get("card_id"))
    new_amount = transaction_data.get("amount")
    old_amount = purchase.get("total_amount", 0)
    
    update_data = {}
    
    if transaction_data.get("description"):
        update_data["description"] = transaction_data["description"]
    if transaction_data.get("category"):
        update_data["category"] = transaction_data["category"]
    if transaction_data.get("notes"):
        update_data["notes"] = transaction_data["notes"]
    if transaction_data.get("installments"):
        update_data["installments"] = transaction_data["installments"]
    if transaction_data.get("first_due_date"):
        update_data["first_due_date"] = transaction_data["first_due_date"]
    if card_id != purchase.get("card_id"):
        update_data["card_id"] = card_id
    
    if new_amount and new_amount != old_amount:
        delta = new_amount - old_amount
        
        if delta > 0:
            card = await db.credit_cards.find_one({
                "_id": ObjectId(card_id),
                "user_id": user_id
            })
            if card:
                available = card.get("limit_total", 0) - card.get("committed_amount", 0)
                if delta > available:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Limite insuficiente. Disponível: R$ {from_cents(available):.2f}"
                    )
        
        update_data["total_amount"] = new_amount
        
        await db.credit_cards.update_one(
            {"_id": ObjectId(card_id)},
            {"$inc": {"committed_amount": delta}}
        )
        
        await db.credit_card_installments.delete_many({"purchase_id": str(purchase["_id"])})
        
        total_amount_reais = from_cents(new_amount)
        installments = transaction_data.get("installments", purchase.get("installments", 1))
        first_due = transaction_data.get("first_due_date", purchase.get("first_due_date"))
        
        from app.routes.credit_card_purchases import split_amount
        from dateutil.relativedelta import relativedelta
        
        amounts = split_amount(total_amount_reais, installments)
        
        new_installments = []
        for i in range(installments):
            due_date = first_due + relativedelta(months=i)
            installment = {
                "purchase_id": str(purchase["_id"]),
                "user_id": user_id,
                "card_id": card_id,
                "amount": to_cents(amounts[i]),
                "due_date": due_date,
                "paid": False,
                "paid_date": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            new_installments.append(installment)
        
        if new_installments:
            await db.credit_card_installments.insert_many(new_installments)
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await db.credit_card_purchases.update_one(
            {"_id": purchase["_id"]},
            {"$set": update_data}
        )
    
    return str(purchase["_id"])


async def delete_credit_card_purchase_from_transaction(
    transaction_id: str,
    user_id: str,
    db
):
    """Deleta compra no cartão associada à despesa."""
    purchase = await db.credit_card_purchases.find_one({
        "transaction_id": transaction_id,
        "user_id": user_id
    })
    
    if not purchase:
        return
    
    paid_installments = await db.credit_card_installments.find_one({
        "purchase_id": str(purchase["_id"]),
        "paid": True
    })
    
    if paid_installments:
        raise HTTPException(
            status_code=400,
            detail="Não é possível deletar despesa que já possui parcelas pagas no cartão."
        )
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(purchase["card_id"])},
        {"$inc": {"committed_amount": -purchase["total_amount"]}}
    )
    
    await db.credit_card_installments.delete_many({"purchase_id": str(purchase["_id"])})
    await db.credit_card_purchases.delete_one({"_id": purchase["_id"]})


# ========== ENDPOINTS ==========

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova transação (receita ou despesa)"""
    try:
        is_credit_card_expense = (
            transaction_data.type == "expense" and
            transaction_data.payment_method == "Cartão de Crédito" and
            transaction_data.card_id
        )
        
        purchase_id = None
        if is_credit_card_expense:
            amount_cents = to_cents(float(transaction_data.amount))
            
            temp_data = {
                "card_id": transaction_data.card_id,
                "amount": amount_cents,
                "description": transaction_data.description or "",
                "installments": transaction_data.installments or 1,
                "first_due_date": transaction_data.first_due_date,
                "category": transaction_data.category,
                "notes": None
            }
            
            # Log para debug
            logger.info(f"Validando compra no cartão para usuário {current_user.id}")
            logger.info(f"Dados: card_id={temp_data['card_id']}, amount={temp_data['amount']}, installments={temp_data['installments']}")
            
            purchase_id = await validate_and_create_credit_card_purchase(
                str(current_user.id),
                temp_data,
                db
            )
        
        transaction_dict = transaction_data.model_dump()
        transaction_dict["user_id"] = str(current_user.id)
        
        if transaction_dict.get("date") is None:
            transaction_dict["date"] = datetime.now(timezone.utc)
        
        amount_float = float(transaction_dict["amount"])
        transaction_dict["amount"] = to_cents(amount_float)
        
        transaction_dict["created_at"] = datetime.now(timezone.utc)
        transaction_dict["updated_at"] = datetime.now(timezone.utc)
        
        if purchase_id:
            transaction_dict["purchase_id"] = purchase_id

        result = await db.transactions.insert_one(transaction_dict)
        transaction_id = str(result.inserted_id)
        
        if purchase_id:
            await db.credit_card_purchases.update_one(
                {"_id": ObjectId(purchase_id)},
                {"$set": {"transaction_id": transaction_id}}
            )
        
        created = await db.transactions.find_one({"_id": result.inserted_id})
        
        if created and "amount" in created:
            created["amount"] = from_cents(created["amount"])
        
        logger.info(f"Transação criada com sucesso: {transaction_id}")
        return format_mongo_doc(created)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar transação: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao criar transação. Tente novamente mais tarde."
        )


@router.get("/", response_model=PaginatedResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if context:
        query["context"] = context
    
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date

    items, total = await paginate_query(
        db.transactions, query, params, sort=[("date", -1)]
    )
    
    for item in items:
        if "amount" in item:
            item["amount"] = from_cents(item["amount"])
    
    formatted_items = format_mongo_docs(items)
    return paginate(formatted_items, total, params)


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
        income = from_cents(float(result[0]["total_income"]))
        expense = from_cents(float(result[0]["total_expense"]))
        return TransactionBalance(
            income=income,
            expense=expense,
            balance=income - expense,
            context=context
        )
    
    return TransactionBalance(income=0.0, expense=0.0, balance=0.0, context=context)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    validate_object_id(transaction_id, "transaction_id")
    obj_id = ObjectId(transaction_id)
    
    transaction = await db.transactions.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    if "amount" in transaction:
        transaction["amount"] = from_cents(transaction["amount"])
    
    return format_mongo_doc(transaction)


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str,
    transaction_update: TransactionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    validate_object_id(transaction_id, "transaction_id")
    obj_id = ObjectId(transaction_id)
    
    original = await db.transactions.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if not original:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    update_data = {k: v for k, v in transaction_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    if "amount" in update_data:
        update_data["amount"] = to_cents(float(update_data["amount"]))
    
    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.transactions.update_one(
        {"_id": obj_id, "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    original_is_credit = (
        original.get("type") == "expense" and
        original.get("payment_method") == "Cartão de Crédito"
    )
    new_is_credit = (
        update_data.get("type", original.get("type")) == "expense" and
        update_data.get("payment_method", original.get("payment_method")) == "Cartão de Crédito"
    )
    
    if original_is_credit or new_is_credit:
        purchase_data = {
            "card_id": update_data.get("card_id", original.get("card_id")),
            "amount": update_data.get("amount", original.get("amount")),
            "description": update_data.get("description", original.get("description")),
            "installments": update_data.get("installments", original.get("installments", 1)),
            "first_due_date": update_data.get("first_due_date", original.get("date")),
            "category": update_data.get("category", original.get("category")),
            "notes": update_data.get("notes", original.get("notes")),
        }
        
        await update_credit_card_purchase_from_transaction(
            transaction_id,
            str(current_user.id),
            purchase_data,
            db
        )
    
    updated = await db.transactions.find_one({"_id": obj_id})
    
    if updated and "amount" in updated:
        updated["amount"] = from_cents(updated["amount"])
    
    return format_mongo_doc(updated)


@router.delete("/{transaction_id}", response_model=dict)
async def delete_transaction(
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    validate_object_id(transaction_id, "transaction_id")
    obj_id = ObjectId(transaction_id)
    
    transaction = await db.transactions.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    is_credit_card_expense = (
        transaction.get("type") == "expense" and
        transaction.get("payment_method") == "Cartão de Crédito"
    )
    
    if is_credit_card_expense:
        await delete_credit_card_purchase_from_transaction(transaction_id, str(current_user.id), db)
    
    result = await db.transactions.delete_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    return {"message": "Transação deletada com sucesso", "success": True}

# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ 🔧 CORREÇÃO: format_transaction_doc cria cópia e remove _id
# ✅ 🔧 CORREÇÃO: Validação de ObjectId nas rotas GET/PUT/DELETE
# ✅ 🔧 CORREÇÃO: Tratamento de erro para ID inválido
# ✅ Adicionada conversão de amount no update_transaction (float + round)
# ✅ Tratamento de erro no create_transaction (mensagem genérica + log)
# ✅ Mudado response_model do PUT para TransactionResponse
# ✅ update_transaction retorna documento atualizado (não apenas mensagem)
# ✅ Paginação padronizada com page/limit (máx 100 itens)
# ✅ Resposta paginada com items, total, pages, has_next, has_prev
#
# 📌 Dívida técnica (pós-MVP):
#    - Índice composto (user_id, context, date) no database.py
#    - Cache de saldo para performance
#    - Migração de float para Decimal128 (se necessário)