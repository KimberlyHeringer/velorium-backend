"""
Rotas de Transações Financeiras (Receitas e Despesas)
Arquivo: backend/app/routes/transactions.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
import logging

from app.database import get_database
from app.models.transaction import TransactionCreate, TransactionUpdate, TransactionResponse, TransactionBalance
from app.models.user import UserResponse
from app.utils.auth import get_current_user

# Configuração de logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transações"])


# ========== FUNÇÃO AUXILIAR ==========

def format_transaction_doc(transaction: dict) -> dict:
    """Converte _id para id e padroniza resposta"""
    if transaction and "_id" in transaction:
        transaction["id"] = str(transaction["_id"])
    return transaction


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
        return format_transaction_doc(created)
        
    except Exception as e:
        logger.error(f"Erro ao criar transação para usuário {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao criar transação. Tente novamente mais tarde."
        )


@router.get("/", response_model=List[TransactionResponse])
async def get_transactions(
    context: Optional[str] = Query(None, regex="^(individual|familia|profissional)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista transações do usuário com filtros opcionais"""
    query = {"user_id": str(current_user.id)}
    
    if context:
        query["context"] = context
    
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date

    cursor = db.transactions.find(query).sort("date", -1).skip(skip).limit(limit)
    transactions = await cursor.to_list(length=limit)
    
    return [format_transaction_doc(t) for t in transactions]


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
    transaction = await db.transactions.find_one({
        "_id": ObjectId(transaction_id),
        "user_id": str(current_user.id)
    })
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    return format_transaction_doc(transaction)


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str,
    transaction_update: TransactionUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma transação existente"""
    # Remover campos None
    update_data = {k: v for k, v in transaction_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    # Conversão de amount se presente (garante que seja float)
    if "amount" in update_data:
        update_data["amount"] = round(float(update_data["amount"]), 2)
    
    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.transactions.update_one(
        {"_id": ObjectId(transaction_id), "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    # Buscar documento atualizado e retornar
    updated = await db.transactions.find_one({"_id": ObjectId(transaction_id)})
    return format_transaction_doc(updated)


@router.delete("/{transaction_id}", response_model=dict)
async def delete_transaction(
    transaction_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma transação"""
    result = await db.transactions.delete_one({
        "_id": ObjectId(transaction_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    return {"message": "Transação deletada com sucesso"}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Adicionada conversão de amount no update_transaction (float + round)
# ✅ Tratamento de erro no create_transaction (mensagem genérica + log)
# ✅ Mudado response_model do PUT para TransactionResponse
# ✅ update_transaction retorna documento atualizado (não apenas mensagem)
# ✅ Adicionada função format_transaction_doc()
# ✅ Validação de context via regex nos parâmetros
# ✅ Paginação implementada (skip/limit)
#
# 📌 Dívida técnica (pós-MVP):
#    - Índice composto (user_id, context, date) no database.py
#    - Cache de saldo para performance
#    - Migração de float para Decimal128 (se necessário)