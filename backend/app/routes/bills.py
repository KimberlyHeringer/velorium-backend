"""
Rotas de Contas a Pagar (Bills)
Arquivo: backend/app/routes/bills.py

🔧 MODIFICADO: Versão simplificada
- Usuário informa APENAS as parcelas RESTANTES
- Todas as parcelas criadas são paid=False
- Remove lógica complexa de 'current' e parcelas já pagas
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from bson import ObjectId

from app.database import get_database
from app.models.bill import BillCreate, BillResponse, BillUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/bills", tags=["Contas a Pagar"])


def parse_installments_dates(installments: dict) -> dict:
    """Converte start_date de string para datetime se necessário."""
    if installments and isinstance(installments, dict):
        start_date = installments.get("start_date")
        if start_date and isinstance(start_date, str):
            installments["start_date"] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    return installments


def split_amount(total: float, parts: int) -> List[float]:
    """Divide um valor total em partes iguais (para parcelas)"""
    base = round(total / parts, 2)
    remainder = round(total - base * parts, 2)
    amounts = [base] * parts
    if remainder != 0:
        amounts[-1] = round(amounts[-1] + remainder, 2)
    return amounts


async def create_bill_installments(bill_id: str, user_id: str, amount: float, installments_data: dict, db):
    """
    Cria as parcelas individuais para uma conta
    🔧 VERSÃO SIMPLIFICADA: Apenas as parcelas RESTANTES, todas pendentes
    """
    total_parcelas = installments_data.get("total", 1)  # Já são apenas as restantes
    start_date = installments_data.get("start_date")
    due_day = installments_data.get("due_day")
    
    if not start_date:
        start_date = datetime.now(timezone.utc)
    
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    
    # Divide o valor total entre as parcelas
    amounts = split_amount(amount, total_parcelas)
    
    installments = []
    for i in range(total_parcelas):
        # Calcula a data de vencimento
        if due_day is not None:
            due_date = start_date + relativedelta(months=i)
            try:
                due_date = due_date.replace(day=due_day)
            except ValueError:
                next_month = due_date + relativedelta(months=1)
                last_day = next_month - timedelta(days=1)
                due_date = last_day
        else:
            due_date = start_date + relativedelta(months=i)
        
        # 🔧 TODAS as parcelas são pendentes (paid = False)
        installment = {
            "bill_id": bill_id,
            "user_id": user_id,
            "number": i + 1,
            "amount": to_cents(amounts[i]),
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)
    
    if installments:
        await db.bill_installments.insert_many(installments)
        logger.info(f"✅ {len(installments)} parcelas criadas para conta {bill_id} (todas pendentes)")


async def update_future_installments(bill_id: str, user_id: str, new_amount: float, new_total_parcelas: int, new_start_date: datetime, db):
    """Atualiza parcelas futuras (não pagas) de uma conta"""
    unpaid_installments = await db.bill_installments.find({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": False
    }).to_list(length=100)
    
    if not unpaid_installments:
        return
    
    await db.bill_installments.delete_many({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": False
    })
    
    amounts = split_amount(new_amount, new_total_parcelas)
    
    paid_count = await db.bill_installments.count_documents({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": True
    })
    
    remaining_start_date = new_start_date + relativedelta(months=paid_count)
    
    new_installments = []
    remaining_parcelas = new_total_parcelas - paid_count
    
    for i in range(remaining_parcelas):
        due_date = remaining_start_date + relativedelta(months=i)
        installment = {
            "bill_id": bill_id,
            "user_id": user_id,
            "number": paid_count + i + 1,
            "amount": to_cents(amounts[paid_count + i]),
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        new_installments.append(installment)
    
    if new_installments:
        await db.bill_installments.insert_many(new_installments)
        logger.info(f"✅ {len(new_installments)} parcelas futuras atualizadas para conta {bill_id}")


# ========== ENDPOINTS ==========

@router.post("/", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    bill_data: BillCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova conta a pagar com parcelas individuais (apenas pendentes)"""
    try:
        bill_dict = bill_data.model_dump()
        bill_dict["user_id"] = str(current_user.id)
        bill_dict["paid"] = False
        bill_dict["paid_date"] = None
        bill_dict["created_at"] = datetime.now(timezone.utc)
        bill_dict["updated_at"] = datetime.now(timezone.utc)

        amount_reais = bill_dict.get("amount", 0)
        installments_info = bill_dict.get("installments", {})
        total_parcelas = installments_info.get("total", 1)

        if "amount" in bill_dict:
            bill_dict["amount"] = to_cents(bill_dict["amount"])

        if "installments" in bill_dict and isinstance(bill_dict["installments"], dict):
            bill_dict["installments"] = parse_installments_dates(bill_dict["installments"])

        result = await db.bills.insert_one(bill_dict)
        bill_id = str(result.inserted_id)
        
        await create_bill_installments(bill_id, str(current_user.id), amount_reais, installments_info, db)
        
        created = await db.bills.find_one({"_id": result.inserted_id})
        
        if created and "amount" in created:
            created["amount"] = from_cents(created["amount"])
        
        logger.info(f"Conta criada: {bill_data.description} - {total_parcelas} parcelas pendentes para usuário {current_user.id}")
        return format_mongo_doc(created)
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar conta: {e}")
        import traceback
        logger.debug(f"Detalhes do erro: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar conta")


@router.get("/", response_model=dict)
async def list_bills(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página (máx 100)"),
    paid: Optional[bool] = Query(None, description="Filtrar por status de pagamento"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista contas do usuário com paginação"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if paid is not None:
        query["paid"] = paid

    items, total = await paginate_query(
        db.bills, query, params, sort=[("created_at", -1)]
    )
    
    for item in items:
        if "amount" in item:
            item["amount"] = from_cents(item["amount"])
    
    formatted_items = format_mongo_docs(items)
    
    logger.debug(f"Listadas {len(formatted_items)} contas para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.get("/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma conta específica"""
    validate_object_id(bill_id, "bill_id")
    
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if not bill:
        logger.warning(f"Conta não encontrada: {bill_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    
    if "amount" in bill:
        bill["amount"] = from_cents(bill["amount"])
    
    return format_mongo_doc(bill)


@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill(
    bill_id: str,
    bill_update: BillUpdate,
    adjust_future_installments: bool = Query(False, description="Se True, ajusta parcelas futuras com os novos valores"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma conta existente"""
    validate_object_id(bill_id, "bill_id")
    
    current_bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if not current_bill:
        logger.warning(f"Conta não encontrada: {bill_id}")
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    
    update_data = {k: v for k, v in bill_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    amount_reais = None
    if "amount" in update_data:
        amount_reais = update_data["amount"]
        update_data["amount"] = to_cents(update_data["amount"])
    
    if update_data.get("paid") is True and update_data.get("paid_date") is None:
        update_data["paid_date"] = datetime.now(timezone.utc)
    
    if "installments" in update_data and isinstance(update_data["installments"], dict):
        update_data["installments"] = parse_installments_dates(update_data["installments"])

    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    if adjust_future_installments and amount_reais is not None:
        new_installments_info = update_data.get("installments", current_bill.get("installments", {}))
        new_total = new_installments_info.get("total", 1)
        new_start_date = new_installments_info.get("start_date", datetime.now(timezone.utc))
        
        await update_future_installments(bill_id, str(current_user.id), amount_reais, new_total, new_start_date, db)

    updated = await db.bills.find_one({"_id": ObjectId(bill_id)})
    
    if updated and "amount" in updated:
        updated["amount"] = from_cents(updated["amount"])
    
    logger.info(f"Conta atualizada: {bill_id} para usuário {current_user.id}")
    return format_mongo_doc(updated)


@router.delete("/{bill_id}", response_model=dict)
async def delete_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma conta e todas as suas parcelas"""
    validate_object_id(bill_id, "bill_id")
    
    result_installments = await db.bill_installments.delete_many({
        "bill_id": bill_id,
        "user_id": str(current_user.id)
    })
    
    result = await db.bills.delete_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    
    if result.deleted_count == 0:
        logger.warning(f"Tentativa de deletar conta inexistente: {bill_id}")
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    
    logger.info(f"Conta deletada: {bill_id} e {result_installments.deleted_count} parcelas para usuário {current_user.id}")
    return {"message": "Conta e parcelas deletadas com sucesso", "success": True}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ 🔧 REGRA 3.3: Ao criar conta, gera parcelas em bill_installments
# ✅ 🔧 REGRA 3.3: Ao deletar conta, deleta parcelas também
# ✅ 🔧 REGRA 3.3: Ao atualizar, pode ajustar parcelas futuras
# ✅ Adicionada função split_amount() para dividir valor
# ✅ Adicionada função create_bill_installments()
# ✅ Adicionada função update_future_installments()
# ✅ Parâmetro adjust_future_installments na rota PUT
# ✅ Conversão de moeda (to_cents/from_cents) em todo lugar
# ✅ Validação de IDs com validate_object_id