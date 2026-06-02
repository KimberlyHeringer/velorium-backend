"""
Rotas de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/routes/bill_installments.py

🔧 MODIFICADO: Regra 3.3 - Refatoração de Bills
- Suporte a due_day = null
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.bill_installment import BillInstallmentResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/bill-installments", tags=["Parcelas de Contas a Pagar"])


async def check_and_update_bill_status(bill_id: str, user_id: str, db):
    """Verifica se todas as parcelas de uma conta estão pagas."""
    unpaid_installments = await db.bill_installments.find_one({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": False
    })
    
    if not unpaid_installments:
        await db.bills.update_one(
            {"_id": ObjectId(bill_id), "user_id": user_id},
            {"$set": {"paid": True, "paid_date": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}}
        )
        logger.info(f"Conta {bill_id} marcada como paga (todas parcelas quitadas)")
        return True
    return False


@router.get("/", response_model=dict)
async def list_installments(
    bill_id: Optional[str] = Query(None, description="Filtrar por conta específica"),
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(100, ge=1, le=1000, description="Itens por página"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista parcelas do usuário com paginação"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if bill_id:
        validate_object_id(bill_id, "bill_id")
        query["bill_id"] = bill_id

    items, total = await paginate_query(
        db.bill_installments, query, params, sort=[("due_date", 1)]
    )
    
    for item in items:
        if "amount" in item:
            item["amount"] = from_cents(item["amount"])
    
    formatted_items = format_mongo_docs(items)
    
    logger.debug(f"Listadas {len(formatted_items)} parcelas para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.get("/{installment_id}", response_model=BillInstallmentResponse)
async def get_installment(
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma parcela específica"""
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.bill_installments.find_one({
        "_id": ObjectId(installment_id),
        "user_id": str(current_user.id)
    })
    if not installment:
        logger.warning(f"Parcela não encontrada: {installment_id}")
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    
    if "amount" in installment:
        installment["amount"] = from_cents(installment["amount"])
    
    return format_mongo_doc(installment)


@router.put("/{installment_id}/pay", response_model=dict)
async def pay_installment(
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Marca uma parcela como paga"""
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.bill_installments.find_one({
        "_id": ObjectId(installment_id),
        "user_id": str(current_user.id)
    })
    if not installment:
        logger.warning(f"Parcela não encontrada para pagamento: {installment_id}")
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    
    if installment.get("paid", False):
        raise HTTPException(status_code=400, detail="Parcela já está paga")
    
    now = datetime.now(timezone.utc)
    await db.bill_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {"$set": {"paid": True, "paid_date": now, "updated_at": now}}
    )
    
    logger.info(f"Parcela paga: {installment_id} para usuário {current_user.id}")
    
    await check_and_update_bill_status(installment["bill_id"], str(current_user.id), db)
    
    return {"message": "Parcela marcada como paga com sucesso", "success": True}


@router.put("/bills/{bill_id}/pay-all", response_model=dict)
async def pay_all_installments(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Marca todas as parcelas de uma conta como pagas"""
    validate_object_id(bill_id, "bill_id")
    
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if not bill:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    
    now = datetime.now(timezone.utc)
    result = await db.bill_installments.update_many(
        {"bill_id": bill_id, "user_id": str(current_user.id), "paid": False},
        {"$set": {"paid": True, "paid_date": now, "updated_at": now}}
    )
    
    await db.bills.update_one(
        {"_id": ObjectId(bill_id)},
        {"$set": {"paid": True, "paid_date": now, "updated_at": now}}
    )
    
    logger.info(f"Todas as parcelas da conta {bill_id} pagas. {result.modified_count} parcelas atualizadas.")
    return {
        "message": "Todas as parcelas foram pagas com sucesso",
        "success": True,
        "installments_paid": result.modified_count
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Rotas similares ao credit_card_installments (consistência)
# ✅ GET /bill-installments listagem com paginação
# ✅ GET /bill-installments/{id} busca individual
# ✅ PUT /bill-installments/{id}/pay paga parcela individual
# ✅ PUT /bill-installments/bills/{bill_id}/pay-all paga conta inteira
# ✅ Atualização automática da conta mestra quando todas parcelas pagas
# ✅ Conversão de moeda (to_cents/from_cents)
# ✅ Validação de IDs com validate_object_id
# ✅ Logs detalhados