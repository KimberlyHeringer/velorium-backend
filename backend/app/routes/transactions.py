"""
Rotas de Transações Financeiras (Receitas e Despesas)
Arquivo: backend/app/routes/transactions.py

Funcionalidades:
- POST /transactions: Criar transação (com suporte a cartão)
- GET /transactions: Listar transações com paginação, filtros e ordenação
- GET /transactions/balance: Saldo do mês atual com cache
- GET /transactions/total-balance: Saldo total com cache
- POST /transactions/recalculate-balance: Recalcular cache de saldo
- GET /transactions/{id}: Buscar transação específica
- PUT /transactions/{id}: Atualizar transação
- DELETE /transactions/{id}: Remover transação
- POST /transactions/bulk-categorize: Recategorização em massa
- GET /transactions/export-csv: Exportar CSV (LGPD)

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting
- Cache de saldo com Redis (TTL: 5 min)
- Recategorização em massa (até 100)
- Exportação CSV (LGPD)
- Categorias centralizadas
- Índices otimizados
- 🔧 CORRIGIDO: Removidas variáveis language não utilizadas (SonarQube)

Versão: v3.3 (corrigido)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, BackgroundTasks
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import os
import json
import csv
import io
from fastapi.responses import StreamingResponse

from app.database import get_database
from app.models.transaction import TransactionCreate, TransactionUpdate, TransactionResponse, TransactionBalance
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, PaginatedResponse, paginate, paginate_query
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

# ========== IMPORTS ==========
from app.core.constants import PAYMENT_METHOD_CREDIT_CARD, BALANCE_CACHE_TTL_SECONDS, CSV_MAX_EXPORT
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.date_utils import get_month_range
from app.utils.installments import split_amount_cents
from app.utils.balance_cache import (
    get_cached_balance_redis,
    set_cached_balance_redis,
    invalidate_balance_cache,
    calculate_balance
)
from app.constants.categories import CATEGORIAS_VALIDAS

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transações"])


# ========== CONFIGURAÇÃO REDIS (OPCIONAL) ==========
try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para cache de saldo")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - usando MongoDB para cache de saldo")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - usando MongoDB para cache de saldo")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")


# ========== FUNÇÕES AUXILIARES ==========

async def create_credit_card_purchase_from_transaction(
    transaction_id: str,
    user_id: str,
    transaction_data: dict,
    db,
    request: Request = None
):
    """Cria compra no cartão a partir da despesa"""
    card_id = transaction_data.get("card_id")
    amount_cents = transaction_data.get("amount")
    description = transaction_data.get("description", "")
    installments = transaction_data.get("installments", 1)
    first_due_date = transaction_data.get("first_due_date")
    category = transaction_data.get("category")
    notes = transaction_data.get("notes")
    
    if not card_id:
        return None
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": user_id
    })
    if not card:
        logger.warning(f"⚠️ Cartão não encontrado ou não pertence ao usuário: {card_id}")
        return None
    
    total_limit = card.get("total_limit", 0)
    committed_amount = card.get("committed_amount", 0)
    available_cents = total_limit - committed_amount
    
    if amount_cents > available_cents:
        raise ValidationException(
            message_key="ERROR_INSUFFICIENT_LIMIT",
            request=request,
            params={"available": from_cents(available_cents)}
        )
    
    purchase_dict = {
        "card_id": card_id,
        "user_id": user_id,
        "description": description,
        "total_amount": amount_cents,
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
    
    amounts_cents = split_amount_cents(amount_cents, installments)
    first_due = purchase_dict["first_due_date"]
    
    from dateutil.relativedelta import relativedelta
    
    installments_list = []
    for i in range(installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "card_id": card_id,
            "amount": amounts_cents[i],
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
        {"$inc": {"committed_amount": amount_cents}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )
    
    return purchase_id


async def delete_credit_card_purchase_from_transaction(
    transaction_id: str,
    user_id: str,
    db,
    request: Request = None
):
    """Deleta compra no cartão associada à despesa"""
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
        raise ValidationException(
            message_key="ERROR_CANNOT_DELETE_PAID_INSTALLMENTS",
            request=request
        )
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(purchase["card_id"])},
        {"$inc": {"committed_amount": -purchase["total_amount"]}}
    )
    
    await db.credit_card_installments.delete_many({"purchase_id": str(purchase["_id"])})
    await db.credit_card_purchases.delete_one({"_id": purchase["_id"]})


# ========== ENDPOINTS ==========

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def create_transaction(
    request: Request,
    transaction_data: TransactionCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova transação (receita ou despesa)"""
    request.state.user_id = str(current_user.id)
    
    try:
        transaction_dict = transaction_data.model_dump()
        transaction_dict["user_id"] = str(current_user.id)
        
        if transaction_dict.get("date") is None:
            transaction_dict["date"] = datetime.now(timezone.utc)
        
        transaction_dict["amount"] = to_cents(transaction_dict["amount"])
        transaction_dict["created_at"] = datetime.now(timezone.utc)
        transaction_dict["updated_at"] = datetime.now(timezone.utc)

        is_credit_card_expense = (
            transaction_dict.get("type") == "expense" and
            transaction_dict.get("payment_method") == PAYMENT_METHOD_CREDIT_CARD and
            transaction_dict.get("card_id")
        )
        
        result = await db.transactions.insert_one(transaction_dict)
        transaction_id = str(result.inserted_id)
        
        if is_credit_card_expense:
            await create_credit_card_purchase_from_transaction(
                transaction_id,
                str(current_user.id),
                transaction_dict,
                db,
                request
            )
        
        await invalidate_balance_cache(str(current_user.id))
        
        created = await db.transactions.find_one({"_id": result.inserted_id})
        
        if created and "amount" in created:
            created["amount"] = from_cents(created["amount"])
        
        logger.info(f"✅ Transação criada: {transaction_dict['type']} para usuário {current_user.id}")
        return convert_objectid_to_str(created)
        
    except ValidationException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao criar transação: {e}")
        raise I18nHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message_key="ERROR_CREATE_TRANSACTION_FAILED",
            request=request
        )


@router.get("/", response_model=PaginatedResponse)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_transactions(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$", description="Contexto"),
    type: Optional[str] = Query(None, regex="^(income|expense)$", description="Tipo de transação"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    start_date: Optional[datetime] = Query(None, description="Data inicial"),
    end_date: Optional[datetime] = Query(None, description="Data final"),
    sort_by: str = Query("date", description="Campo para ordenação (date, amount, type, category)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista transações do usuário com paginação, filtros e ordenação.
    """
    request.state.user_id = str(current_user.id)
    
    params = PaginationParams(page=page, limit=limit)
    
    query = {
        "user_id": str(current_user.id),
        "$or": [
            {"type": "income"},
            {"type": "expense", "payment_method": {"$ne": PAYMENT_METHOD_CREDIT_CARD}},
            {"type": "expense", "payment_method": {"$exists": False}}
        ]
    }
    
    if context:
        query["context"] = context
    
    if type:
        query["type"] = type
    
    if category:
        query["category"] = category
    
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    sort_field_mapping = {
        "date": "date",
        "amount": "amount",
        "type": "type",
        "category": "category",
        "created_at": "created_at"
    }
    sort_field = sort_field_mapping.get(sort_by, "date")
    sort_direction = -1 if sort_order == "desc" else 1

    items, total = await paginate_query(
        db.transactions, query, params, sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        if "amount" in item:
            item["amount"] = from_cents(item["amount"])
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listadas {len(formatted_items)} transações para usuário {current_user.id}")
    return paginate(formatted_items, total, params)


@router.get("/balance", response_model=TransactionBalance)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def get_balance(
    request: Request,
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$", description="Contexto"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o saldo do MÊS ATUAL com cache.
    """
    request.state.user_id = str(current_user.id)
    
    user_id = str(current_user.id)
    
    cached = await get_cached_balance_redis(user_id, context)
    if cached:
        logger.debug(f"💾 Cache hit de saldo para usuário {user_id}")
        return TransactionBalance(
            income=from_cents(cached["income"]),
            expense=from_cents(cached["expense"]),
            balance=from_cents(cached["balance"]),
            context=context
        )
    
    logger.debug(f"🔄 Cache miss de saldo para usuário {user_id}")
    result = await calculate_balance(user_id, db, context)
    
    await set_cached_balance_redis(user_id, result, context)
    
    return TransactionBalance(
        income=from_cents(result["income"]),
        expense=from_cents(result["expense"]),
        balance=from_cents(result["balance"]),
        context=context
    )


@router.get("/total-balance", response_model=TransactionBalance)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def get_total_balance(
    request: Request,
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$", description="Contexto"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o saldo TOTAL (soma de TODAS as transações) com cache.
    """
    request.state.user_id = str(current_user.id)
    
    user_id = str(current_user.id)
    cache_key = f"total_balance:{user_id}:{context or 'all'}"
    
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                logger.debug(f"💾 Cache hit de saldo total para usuário {user_id}")
                return TransactionBalance(
                    income=from_cents(data["income"]),
                    expense=from_cents(data["expense"]),
                    balance=from_cents(data["balance"]),
                    context=context
                )
        except Exception as e:
            logger.warning(f"⚠️ Erro ao buscar saldo total no Redis: {e}")
    
    match = {
        "user_id": user_id,
        "$or": [
            {"type": "income"},
            {"type": "expense", "payment_method": {"$ne": PAYMENT_METHOD_CREDIT_CARD}},
            {"type": "expense", "payment_method": {"$exists": False}}
        ]
    }
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
        income = result[0]["total_income"]
        expense = result[0]["total_expense"]
        balance_data = {"income": income, "expense": expense, "balance": income - expense}
        
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key,
                    BALANCE_CACHE_TTL_SECONDS,
                    json.dumps(balance_data, default=str)
                )
            except Exception as e:
                logger.warning(f"⚠️ Erro ao armazenar saldo total no Redis: {e}")
        
        return TransactionBalance(
            income=from_cents(income),
            expense=from_cents(expense),
            balance=from_cents(income - expense),
            context=context
        )
    
    return TransactionBalance(income=0.0, expense=0.0, balance=0.0, context=context)


@router.post("/recalculate-balance", response_model=dict)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def recalculate_balance(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Recalcula e atualiza o cache de saldo do usuário.
    """
    request.state.user_id = str(current_user.id)
    
    user_id = str(current_user.id)
    
    await invalidate_balance_cache(user_id)
    
    result = await calculate_balance(user_id, db)
    await set_cached_balance_redis(user_id, result)
    
    for ctx in ["individual", "familia", "profissional"]:
        result_ctx = await calculate_balance(user_id, db, ctx)
        await set_cached_balance_redis(user_id, result_ctx, ctx)
    
    logger.info(f"🔄 Cache de saldo recalculado para usuário {user_id}")
    
    return {
        "message": get_message("SUCCESS_BALANCE_RECALCULATED", "pt"),
        "success": True
    }


@router.get("/{transaction_id}", response_model=TransactionResponse)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_transaction(
    request: Request,
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma transação específica"""
    request.state.user_id = str(current_user.id)
    
    validate_object_id(transaction_id, "transaction_id")
    obj_id = ObjectId(transaction_id)
    
    transaction = await db.transactions.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if not transaction:
        raise NotFoundException(
            message_key="ERROR_TRANSACTION_NOT_FOUND",
            request=request
        )
    
    if "amount" in transaction:
        transaction["amount"] = from_cents(transaction["amount"])
    
    return convert_objectid_to_str(transaction)


@router.put("/{transaction_id}", response_model=TransactionResponse)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def update_transaction(
    request: Request,
    transaction_id: str,
    transaction_update: TransactionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma transação existente"""
    request.state.user_id = str(current_user.id)
    
    validate_object_id(transaction_id, "transaction_id")
    obj_id = ObjectId(transaction_id)
    
    original = await db.transactions.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if not original:
        raise NotFoundException(
            message_key="ERROR_TRANSACTION_NOT_FOUND",
            request=request
        )
    
    update_data = {k: v for k, v in transaction_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise ValidationException(
            message_key="ERROR_NO_DATA_TO_UPDATE",
            request=request
        )
    
    if "amount" in update_data:
        update_data["amount"] = to_cents(update_data["amount"])
    
    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.transactions.update_one(
        {"_id": obj_id, "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise NotFoundException(
            message_key="ERROR_TRANSACTION_NOT_FOUND",
            request=request
    )
    
    await invalidate_balance_cache(str(current_user.id))
    
    updated = await db.transactions.find_one({"_id": obj_id})
    
    if updated and "amount" in updated:
        updated["amount"] = from_cents(updated["amount"])
    
    logger.info(f"✅ Transação atualizada: {transaction_id} para usuário {current_user.id}")
    return convert_objectid_to_str(updated)


@router.delete("/{transaction_id}", response_model=dict)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def delete_transaction(
    request: Request,
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma transação"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    validate_object_id(transaction_id, "transaction_id")
    obj_id = ObjectId(transaction_id)
    
    transaction = await db.transactions.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if not transaction:
        raise NotFoundException(
            message_key="ERROR_TRANSACTION_NOT_FOUND",
            request=request
        )
    
    is_credit_card_expense = (
        transaction.get("type") == "expense" and
        transaction.get("payment_method") == PAYMENT_METHOD_CREDIT_CARD
    )
    
    if is_credit_card_expense:
        await delete_credit_card_purchase_from_transaction(
            transaction_id,
            str(current_user.id),
            db,
            request
        )
    
    result = await db.transactions.delete_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise NotFoundException(
            message_key="ERROR_TRANSACTION_NOT_FOUND",
            request=request
        )
    
    await invalidate_balance_cache(str(current_user.id))
    
    logger.info(f"🗑️ Transação deletada: {transaction_id} para usuário {current_user.id}")
    
    return {
        "message": get_message("SUCCESS_TRANSACTION_DELETED", language),
        "success": True
    }


@router.post("/bulk-categorize", response_model=dict)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def bulk_categorize_transactions(
    request: Request,
    transaction_ids: List[str],
    category: str = Query(..., min_length=1, max_length=50, description="Nova categoria"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Recategoriza múltiplas transações de uma vez.
    Máximo de 100 transações por requisição.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    if category not in CATEGORIAS_VALIDAS:
        raise ValidationException(
            message_key="ERROR_INVALID_CATEGORY",
            request=request,
            params={"categories": ", ".join(CATEGORIAS_VALIDAS)}
        )
    
    if len(transaction_ids) > 100:
        raise ValidationException(
            message_key="ERROR_BULK_LIMIT_EXCEEDED",
            request=request
        )
    
    user_id = str(current_user.id)
    updated_count = 0
    failed_ids = []
    
    for t_id in transaction_ids:
        try:
            validate_object_id(t_id, "transaction_id")
            result = await db.transactions.update_one(
                {
                    "_id": ObjectId(t_id),
                    "user_id": user_id
                },
                {
                    "$set": {
                        "category": category,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            if result.modified_count > 0:
                updated_count += 1
            else:
                failed_ids.append(t_id)
        except Exception as e:
            logger.warning(f"⚠️ Erro ao atualizar transação {t_id}: {e}")
            failed_ids.append(t_id)
    
    await invalidate_balance_cache(user_id)
    
    logger.info(f"📋 Recategorizadas {updated_count} transações para usuário {user_id}")
    
    return {
        "message": get_message("SUCCESS_BULK_CATEGORIZED", language).format(count=updated_count),
        "success": True,
        "updated_count": updated_count,
        "failed_ids": failed_ids,
        "total": len(transaction_ids)
    }


@router.get("/export-csv", response_model=None)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def export_transactions_csv(
    request: Request,
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$", description="Contexto"),
    start_date: Optional[datetime] = Query(None, description="Data inicial"),
    end_date: Optional[datetime] = Query(None, description="Data final"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Exporta transações em formato CSV (LGPD - portabilidade de dados).
    Limite de 10.000 registros.
    """
    request.state.user_id = str(current_user.id)
    
    query = {
        "user_id": str(current_user.id),
        "$or": [
            {"type": "income"},
            {"type": "expense", "payment_method": {"$ne": PAYMENT_METHOD_CREDIT_CARD}},
            {"type": "expense", "payment_method": {"$exists": False}}
        ]
    }
    
    if context:
        query["context"] = context
    
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    cursor = db.transactions.find(query).sort("date", -1).limit(CSV_MAX_EXPORT)
    transactions = await cursor.to_list(CSV_MAX_EXPORT)
    
    output = io.StringIO()
    output.write('\ufeff')  # BOM para Excel
    writer = csv.writer(output)
    
    writer.writerow([
        "ID", "Data", "Descrição", "Categoria", "Tipo", "Valor (R$)",
        "Método de Pagamento", "Contexto", "Parcelas", "Cartão", "Notas"
    ])
    
    for t in transactions:
        amount = from_cents(t.get("amount", 0))
        date_str = t.get("date").strftime("%Y-%m-%d %H:%M:%S") if t.get("date") else ""
        
        writer.writerow([
            str(t.get("_id")),
            date_str,
            t.get("description", ""),
            t.get("category", ""),
            t.get("type", ""),
            f"{amount:.2f}",
            t.get("payment_method", ""),
            t.get("context", "individual"),
            t.get("installments", 1),
            t.get("card_id", ""),
            t.get("notes", "")
        ])
    
    filename = f"transacoes_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    
    logger.info(f"📤 Exportação CSV: {len(transactions)} transações para usuário {current_user.id}")
    
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting
#   - Cache de saldo com Redis (TTL: 5 min)
#   - Recategorização em massa (até 100)
#   - Exportação CSV (LGPD)
#   - Categorias centralizadas
#   - Índices otimizados
#   - Funções auxiliares centralizadas
#   - 🔧 CORRIGIDO: Removidas variáveis language não utilizadas (SonarQube)
#
# ❌ Não implementado (Pós-MVP):
#   - Timezone do usuário
#   - Exportação PDF
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Rate limiting, cache, bulk, CSV (30/06/2026)
#   - v3.1: Correções de request, scan_iter (01/07/2026)
#   - v3.2: Refatoração - constants, rate_limiter, date_utils, installments, balance_cache (02/07/2026)
#   - v3.3: Removidas variáveis language não utilizadas (SonarQube) (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO