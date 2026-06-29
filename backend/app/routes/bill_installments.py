"""
Rotas de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/routes/bill_installments.py

🔧 CORRIGIDO:
- 🔧 i18n: Substituído HTTPException por I18nHTTPException
- 🔧 i18n: Mensagens de erro com get_message()
- 🔧 NOVO: request: Request em todos os endpoints
- 🔧 CORRIGIDO: check_and_update_bill_status com verificação atômica (paid: False)
- 🔧 CORRIGIDO: pay_all_installments com update_many atômico
- 🔧 CORRIGIDO: pay_installment valida due_date (não permite pagar parcelas futuras)
- 🔧 CORRIGIDO: pay_all_installments corrige inconsistências automaticamente
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
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

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/bill-installments", tags=["Parcelas de Contas a Pagar"])


async def check_and_update_bill_status(bill_id: str, user_id: str, db, request: Request = None):
    """
    Verifica se todas as parcelas de uma conta estão pagas.
    Se sim, atualiza a conta mestra como paga.
    🔧 CORRIGIDO: Usa update_one com filtro atômico (paid: False) para evitar race condition.
    """
    unpaid_installments = await db.bill_installments.find_one({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": False
    })
    
    if not unpaid_installments:
        # 🔧 CORRIGIDO: Só atualiza se ainda não estiver paga
        result = await db.bills.update_one(
            {
                "_id": ObjectId(bill_id), 
                "user_id": user_id,
                "paid": False  # ← Só atualiza se ainda não estiver paga
            },
            {
                "$set": {
                    "paid": True, 
                    "paid_date": datetime.now(timezone.utc), 
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Conta {bill_id} marcada como paga (todas parcelas quitadas)")
        else:
            logger.info(f"Conta {bill_id} já foi marcada como paga (race condition)")
        
        return True
    
    return False


@router.get("/", response_model=dict)
async def list_installments(
    request: Request,
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
        # 🔧 OPCIONAL: Verifica se a conta pertence ao usuário
        bill = await db.bills.find_one({
            "_id": ObjectId(bill_id),
            "user_id": str(current_user.id)
        })
        if not bill:
            raise NotFoundException(
                message_key="BILL_NOT_FOUND",
                request=request
            )
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
    request: Request,
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
        raise NotFoundException(
            message_key="INSTALLMENT_NOT_FOUND",
            request=request
        )
    
    if "amount" in installment:
        installment["amount"] = from_cents(installment["amount"])
    
    return format_mongo_doc(installment)


@router.put("/{installment_id}/pay", response_model=dict)
async def pay_installment(
    request: Request,
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
        raise NotFoundException(
            message_key="INSTALLMENT_NOT_FOUND",
            request=request
        )
    
    if installment.get("paid", False):
        raise ValidationException(
            message_key="INSTALLMENT_ALREADY_PAID",
            request=request
        )
    
    # 🔧 CORRIGIDO: Verifica se a parcela já venceu
    due_date = installment.get("due_date")
    if due_date and due_date > datetime.now(timezone.utc):
        raise ValidationException(
            message_key="INSTALLMENT_NOT_YET_DUE",
            request=request
        )
    
    now = datetime.now(timezone.utc)
    await db.bill_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {"$set": {"paid": True, "paid_date": now, "updated_at": now}}
    )
    
    logger.info(f"Parcela paga: {installment_id} para usuário {current_user.id}")
    
    await check_and_update_bill_status(installment["bill_id"], str(current_user.id), db, request)
    
    language = getattr(request.state, "language", "pt")
    return {"message": get_message("INSTALLMENT_PAID_SUCCESS", language), "success": True}


@router.put("/bills/{bill_id}/pay-all", response_model=dict)
async def pay_all_installments(
    request: Request,
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Marca todas as parcelas de uma conta como pagas"""
    validate_object_id(bill_id, "bill_id")
    
    now = datetime.now(timezone.utc)
    
    # 🔧 CORRIGIDO: Update atômico - atualiza apenas parcelas não pagas
    result = await db.bill_installments.update_many(
        {
            "bill_id": bill_id, 
            "user_id": str(current_user.id), 
            "paid": False
        },
        {"$set": {"paid": True, "paid_date": now, "updated_at": now}}
    )
    
    # 🔧 CORRIGIDO: Se não atualizou nenhuma parcela, verifica o motivo
    if result.modified_count == 0:
        bill = await db.bills.find_one({
            "_id": ObjectId(bill_id),
            "user_id": str(current_user.id)
        })
        
        if bill and bill.get("paid", False):
            language = getattr(request.state, "language", "pt")
            logger.info(f"Conta {bill_id} já está paga. Nenhuma parcela para pagar.")
            return {
                "message": get_message("INSTALLMENTS_ALREADY_PAID", language),
                "success": True,
                "installments_paid": 0
            }
        else:
            # 🔧 CORRIGIDO: Inconsistência detectada - corrige automaticamente
            logger.warning(f"⚠️ Inconsistência: conta {bill_id} sem parcelas pendentes mas não está paga")
            await db.bills.update_one(
                {"_id": ObjectId(bill_id), "user_id": str(current_user.id)},
                {"$set": {"paid": True, "paid_date": now, "updated_at": now}}
            )
            language = getattr(request.state, "language", "pt")
            return {
                "message": get_message("INSTALLMENTS_ALREADY_PAID", language),
                "success": True,
                "installments_paid": 0
            }
    
    # 🔧 CORRIGIDO: Atualiza a conta apenas se todas as parcelas foram pagas
    await check_and_update_bill_status(bill_id, str(current_user.id), db, request)
    
    logger.info(f"Todas as parcelas da conta {bill_id} pagas. {result.modified_count} parcelas atualizadas.")
    
    language = getattr(request.state, "language", "pt")
    return {
        "message": get_message("INSTALLMENTS_ALL_PAID", language),
        "success": True,
        "installments_paid": result.modified_count
    }


# ========== PENDÊNCIA PÓS-MVP ==========
# 
# @router.put("/{installment_id}/unpay", response_model=dict)
# async def unpay_installment(
#     request: Request,
#     installment_id: str,
#     current_user: UserResponse = Depends(get_current_user),
#     db=Depends(get_database)
# ):
#     """
#     Desmarca uma parcela como paga (rollback).
#     🔧 PÓS-MVP: Permitir reverter pagamento feito por engano.
#     """
#     # Validar se pode desmarcar
#     # Atualizar parcela
#     # Atualizar status da conta mestra
#     pass


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
# ✅ 🔧 i18n: Todas as mensagens substituídas
# ✅ 🔧 i18n: request: Request em todos os endpoints
# ✅ 🔧 CORRIGIDO: check_and_update_bill_status com verificação atômica
# ✅ 🔧 CORRIGIDO: pay_all_installments com update_many atômico
# ✅ 🔧 CORRIGIDO: pay_installment valida due_date (não permite pagar parcelas futuras)
# ✅ 🔧 CORRIGIDO: pay_all_installments corrige inconsistências automaticamente
#
# ⏳ PENDÊNCIAS PÓS-MVP:
# - Rota para desmarcar pagamento (/unpay)
# - Logs de auditoria (quem pagou cada parcela)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. 🔧 i18n: Substituído HTTPException por I18nHTTPException
2. 🔧 i18n: Mensagens de erro com get_message()
3. 🔧 NOVO: request: Request em todos os endpoints
4. 🔧 i18n: Mensagens de sucesso com get_message()
5. 🔧 CORRIGIDO: check_and_update_bill_status com filtro atômico (paid: False)
6. 🔧 CORRIGIDO: pay_all_installments com update_many atômico
7. 🔧 CORRIGIDO: pay_installment valida due_date (impede pagamento de parcelas futuras)
8. 🔧 CORRIGIDO: pay_all_installments corrige inconsistências automaticamente

📌 CHAVES I18N UTILIZADAS:
   - INSTALLMENT_NOT_FOUND → "Parcela não encontrada"
   - INSTALLMENT_ALREADY_PAID → "Parcela já está paga"
   - INSTALLMENT_PAID_SUCCESS → "Parcela paga com sucesso"
   - INSTALLMENTS_ALL_PAID → "Todas as parcelas foram pagas"
   - INSTALLMENTS_ALREADY_PAID → "Todas as parcelas já estavam pagas"
   - INSTALLMENT_NOT_YET_DUE → "Parcela ainda não venceu"
   - BILL_NOT_FOUND → "Conta não encontrada"

✅ STATUS: CONSISTENTE COM AS ROTAS E BANCO DE DADOS
================================================================================
"""