"""
Rotas de Transações Financeiras (Receitas e Despesas)
Arquivo: backend/app/routes/transactions.py

🔧 CORREÇÃO: Substituído format_transaction_doc por format_mongo_doc (Seção 2.2)
🔧 MODIFICADO: Regra 2.8 - Usa setup_logger em vez de logging diretamente
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
from app.utils.validators import format_mongo_doc, format_mongo_docs
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transações"])


# ========== ENDPOINTS ==========

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova transação (receita ou despesa)"""
    try:
        transaction_dict = transaction_data.model_dump()
        transaction_dict["user_id"] = str(current_user.id)
        
        if transaction_dict.get("date") is None:
            transaction_dict["date"] = datetime.now(timezone.utc)
        
        # Arredondar amount
        transaction_dict["amount"] = round(float(transaction_dict["amount"]), 2)
        transaction_dict["created_at"] = datetime.now(timezone.utc)
        transaction_dict["updated_at"] = datetime.now(timezone.utc)

        result = await db.transactions.insert_one(transaction_dict)
        
        # Buscar o documento inserido para retornar os dados completos
        created = await db.transactions.find_one({"_id": result.inserted_id})
        
        logger.info(f"Transação criada: {transaction_dict['type']} - R$ {transaction_dict['amount']} para usuário {current_user.id}")
        return format_mongo_doc(created)
        
    except Exception as e:
        logger.error(f"Erro ao criar transação para usuário {current_user.id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao criar transação. Tente novamente mais tarde."
        )


@router.get("/", response_model=PaginatedResponse)
async def get_transactions(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página (máx 100)"),
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista transações do usuário com paginação e filtros opcionais"""
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
    
    formatted_items = format_mongo_docs(items)
    
    logger.debug(f"Listadas {len(formatted_items)} transações para usuário {current_user.id}")
    return paginate(formatted_items, total, params)


@router.get("/balance", response_model=TransactionBalance)
async def get_balance(
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna o saldo (receitas - despesas) do usuário"""
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
        income = float(result[0]["total_income"])
        expense = float(result[0]["total_expense"])
        logger.debug(f"Saldo calculado para usuário {current_user.id}: R$ {income - expense:.2f}")
        return TransactionBalance(
            income=income,
            expense=expense,
            balance=income - expense,
            context=context
        )
    
    return TransactionBalance(
        income=0.0,
        expense=0.0,
        balance=0.0,
        context=context
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna uma transação específica"""
    try:
        obj_id = ObjectId(transaction_id)
    except Exception:
        logger.warning(f"ID de transação inválido: {transaction_id} para usuário {current_user.id}")
        raise HTTPException(status_code=400, detail="ID de transação inválido")
    
    transaction = await db.transactions.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if not transaction:
        logger.warning(f"Transação não encontrada: {transaction_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    logger.debug(f"Transação recuperada: {transaction_id} para usuário {current_user.id}")
    return format_mongo_doc(transaction)


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str,
    transaction_update: TransactionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma transação existente"""
    try:
        obj_id = ObjectId(transaction_id)
    except Exception:
        logger.warning(f"ID de transação inválido para atualização: {transaction_id}")
        raise HTTPException(status_code=400, detail="ID de transação inválido")
    
    # Remover campos None
    update_data = {k: v for k, v in transaction_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    # Conversão de amount se presente (garante que seja float)
    if "amount" in update_data:
        update_data["amount"] = round(float(update_data["amount"]), 2)
    
    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.transactions.update_one(
        {"_id": obj_id, "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        logger.warning(f"Transação não encontrada para atualização: {transaction_id}")
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    # Buscar documento atualizado e retornar
    updated = await db.transactions.find_one({"_id": obj_id})
    
    logger.info(f"Transação atualizada: {transaction_id} para usuário {current_user.id}")
    return format_mongo_doc(updated)


@router.delete("/{transaction_id}", response_model=dict)
async def delete_transaction(
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma transação"""
    try:
        obj_id = ObjectId(transaction_id)
    except Exception:
        logger.warning(f"ID de transação inválido para deleção: {transaction_id}")
        raise HTTPException(status_code=400, detail="ID de transação inválido")
    
    result = await db.transactions.delete_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        logger.warning(f"Transação não encontrada para deleção: {transaction_id}")
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    logger.info(f"Transação deletada: {transaction_id} para usuário {current_user.id}")
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