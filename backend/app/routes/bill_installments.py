"""
Rotas de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/routes/bill_installments.py

Funcionalidades:
- GET /bill-installments: Listar parcelas com paginação e filtros (paid, start_date, end_date)
- GET /bill-installments/{id}: Buscar parcela específica
- PUT /bill-installments/{id}/pay: Marcar parcela como paga
- PUT /bill-installments/bills/{bill_id}/pay-all: Marcar todas as parcelas como pagas
- PUT /bill-installments/{id}/unpay: Desmarcar pagamento (rollback)

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (pay: 30/min, pay-all: 20/min, unpay: 10/min)
- Auditoria completa (history + paid_by)
- Filtros avançados (paid, start_date, end_date)
- Janela de reversão de 30 dias no /unpay
- Validação de consistência da conta mestra

Versão: v5.1 (refatorado)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.database import get_database
from app.models.bill_installment import BillInstallmentResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter, get_user_rate_limit_key

# ========== NOVOS IMPORTS ==========
from app.core.constants import MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS
from app.utils.audit import add_audit_history
from app.utils.date_utils import validate_date_range

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/bill-installments", tags=["Parcelas de Contas a Pagar"])


# ========== FUNÇÕES AUXILIARES ==========

async def check_and_update_bill_status(bill_id: str, user_id: str, db, request: Request = None):
    """
    Verifica se todas as parcelas de uma conta estão pagas.
    Se sim, atualiza a conta mestra como paga.
    
    🔧 CORRIGIDO v2: Usa update_one com filtro atômico (paid: False) para evitar race condition.
    🆕 v3: Adicionada validação de existência da conta.
    
    📋 LIMITAÇÃO: O MongoDB Atlas Free Tier não suporta transações multi-documento.
    """
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": user_id
    })
    if not bill:
        logger.warning(f"⚠️ Conta não encontrada ao verificar status: {bill_id}")
        return False
    
    unpaid_installments = await db.bill_installments.find_one({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": False
    })
    
    if not unpaid_installments:
        result = await db.bills.update_one(
            {
                "_id": ObjectId(bill_id), 
                "user_id": user_id,
                "paid": False
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
            logger.info(f"✅ Conta {bill_id} marcada como paga (todas parcelas quitadas)")
        else:
            logger.info(f"ℹ️ Conta {bill_id} já foi marcada como paga (race condition)")
        
        return True
    
    return False


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def list_installments(
    request: Request,
    bill_id: Optional[str] = Query(None, description="Filtrar por conta específica"),
    paid: Optional[bool] = Query(None, description="Filtrar por status (true=paga, false=não paga)"),
    start_date: Optional[datetime] = Query(None, description="Data de vencimento inicial"),
    end_date: Optional[datetime] = Query(None, description="Data de vencimento final"),
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(100, ge=1, le=1000, description="Itens por página"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista parcelas do usuário com paginação e filtros.
    
    🆕 v3: Adicionados filtros:
    - paid: Filtrar por status (pagas/não pagas)
    - start_date: Data de vencimento inicial
    - end_date: Data de vencimento final
    """
    # 🔧 CORRIGIDO: Validação de intervalo de datas
    validate_date_range(start_date, end_date, request)
    
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if bill_id:
        validate_object_id(bill_id, "bill_id")
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
    
    if paid is not None:
        query["paid"] = paid
    
    if start_date:
        query["due_date"] = {"$gte": start_date}
    if end_date:
        if "due_date" in query:
            query["due_date"]["$lte"] = end_date
        else:
            query["due_date"] = {"$lte": end_date}

    items, total = await paginate_query(
        db.bill_installments, query, params, sort=[("due_date", 1)]
    )
    
    for item in items:
        if "amount" in item:
            item["amount"] = from_cents(item["amount"])
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listadas {len(formatted_items)} parcelas para usuário {current_user.id}")
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
        logger.warning(f"⚠️ Parcela não encontrada: {installment_id}")
        raise NotFoundException(
            message_key="INSTALLMENT_NOT_FOUND",
            request=request
        )
    
    if "amount" in installment:
        installment["amount"] = from_cents(installment["amount"])
    
    return convert_objectid_to_str(installment)


@router.put("/{installment_id}/pay", response_model=dict)
@limiter.limit("30/minute")
async def pay_installment(
    request: Request,
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Marca uma parcela como paga.
    
    🆕 v3: Adicionado:
    - Campo paid_by (auditoria)
    - Histórico de ações (history)
    - Rate limiting
    """
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.bill_installments.find_one({
        "_id": ObjectId(installment_id),
        "user_id": str(current_user.id)
    })
    if not installment:
        logger.warning(f"⚠️ Parcela não encontrada para pagamento: {installment_id}")
        raise NotFoundException(
            message_key="INSTALLMENT_NOT_FOUND",
            request=request
        )
    
    if installment.get("paid", False):
        raise ValidationException(
            message_key="INSTALLMENT_ALREADY_PAID",
            request=request
        )
    
    due_date = installment.get("due_date")
    if due_date and due_date > datetime.now(timezone.utc):
        raise ValidationException(
            message_key="INSTALLMENT_NOT_YET_DUE",
            request=request
        )
    
    now = datetime.now(timezone.utc)
    user_id = str(current_user.id)
    
    await db.bill_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {
            "$set": {
                "paid": True,
                "paid_date": now,
                "paid_by": user_id,
                "updated_at": now
            }
        }
    )
    
    await add_audit_history(
        db.bill_installments,
        installment_id,
        "pay",
        user_id,
        {
            "bill_id": installment["bill_id"],
            "amount": installment.get("amount"),
            "due_date": installment.get("due_date"),
            "installment_number": installment.get("installment_number")
        }
    )
    
    logger.info(f"✅ Parcela paga: {installment_id} por usuário {user_id}")
    
    await check_and_update_bill_status(installment["bill_id"], user_id, db, request)
    
    language = getattr(request.state, "language", "pt")
    return {
        "message": get_message("INSTALLMENT_PAID_SUCCESS", language),
        "success": True,
        "paid_by": user_id
    }


@router.put("/bills/{bill_id}/pay-all", response_model=dict)
@limiter.limit("20/minute")
async def pay_all_installments(
    request: Request,
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Marca todas as parcelas de uma conta como pagas.
    
    🆕 v5: Adicionado:
    - Histórico de ações em cada parcela
    - Campo paid_by em todas as parcelas
    - Rate limiting
    - Fallback para installment_number (campo 'number')
    """
    validate_object_id(bill_id, "bill_id")
    
    now = datetime.now(timezone.utc)
    user_id = str(current_user.id)
    
    result = await db.bill_installments.update_many(
        {
            "bill_id": bill_id, 
            "user_id": user_id, 
            "paid": False
        },
        {
            "$set": {
                "paid": True,
                "paid_date": now,
                "paid_by": user_id,
                "updated_at": now
            }
        }
    )
    
    if result.modified_count > 0:
        paid_installments = await db.bill_installments.find({
            "bill_id": bill_id,
            "user_id": user_id,
            "paid": True,
            "paid_date": now
        }).to_list(None)
        
        for inst in paid_installments:
            installment_number = inst.get("installment_number")
            if installment_number is None:
                installment_number = inst.get("number", 0)
                logger.warning(f"⚠️ Campo installment_number não encontrado, usando number: {installment_number}")
            
            await add_audit_history(
                db.bill_installments,
                str(inst["_id"]),
                "pay_all",
                user_id,
                {
                    "bill_id": bill_id,
                    "action": "pay_all_installments",
                    "amount": inst.get("amount"),
                    "installment_number": installment_number,
                    "total_installments_paid": result.modified_count
                }
            )
    
    if result.modified_count == 0:
        bill = await db.bills.find_one({
            "_id": ObjectId(bill_id),
            "user_id": user_id
        })
        
        if bill and bill.get("paid", False):
            language = getattr(request.state, "language", "pt")
            logger.info(f"ℹ️ Conta {bill_id} já está paga. Nenhuma parcela para pagar.")
            return {
                "message": get_message("INSTALLMENTS_ALREADY_PAID", language),
                "success": True,
                "installments_paid": 0
            }
        else:
            logger.warning(f"⚠️ Inconsistência: conta {bill_id} sem parcelas pendentes mas não está paga")
            await db.bills.update_one(
                {"_id": ObjectId(bill_id), "user_id": user_id},
                {"$set": {"paid": True, "paid_date": now, "updated_at": now}}
            )
            language = getattr(request.state, "language", "pt")
            return {
                "message": get_message("INSTALLMENTS_ALREADY_PAID", language),
                "success": True,
                "installments_paid": 0
            }
    
    await check_and_update_bill_status(bill_id, user_id, db, request)
    
    logger.info(f"✅ Todas as parcelas da conta {bill_id} pagas. {result.modified_count} parcelas atualizadas por {user_id}.")
    
    language = getattr(request.state, "language", "pt")
    return {
        "message": get_message("INSTALLMENTS_ALL_PAID", language),
        "success": True,
        "installments_paid": result.modified_count
    }


@router.put("/{installment_id}/unpay", response_model=dict)
@limiter.limit("10/minute")
async def unpay_installment(
    request: Request,
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    🆕 Desmarca uma parcela como paga (rollback).
    
    Permite reverter um pagamento feito por engano.
    
    Validações:
    - Verifica se a parcela existe e pertence ao usuário
    - Verifica se a parcela está paga
    - Verifica se o pagamento foi feito há menos de 30 dias (janela de reversão)
    - Verifica consistência com a conta mestra
    """
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.bill_installments.find_one({
        "_id": ObjectId(installment_id),
        "user_id": str(current_user.id)
    })
    if not installment:
        logger.warning(f"⚠️ Parcela não encontrada para desmarcar: {installment_id}")
        raise NotFoundException(
            message_key="INSTALLMENT_NOT_FOUND",
            request=request
        )
    
    if not installment.get("paid", False):
        raise ValidationException(
            message_key="INSTALLMENT_NOT_PAID",
            request=request
        )
    
    paid_date = installment.get("paid_date")
    if paid_date:
        days_since_paid = (datetime.now(timezone.utc) - paid_date).days
        if days_since_paid > 30:
            raise ValidationException(
                message_key="INSTALLMENT_UNPAY_WINDOW_EXPIRED",
                request=request
            )
    
    now = datetime.now(timezone.utc)
    user_id = str(current_user.id)
    bill_id = installment["bill_id"]
    
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": user_id
    })
    
    await db.bill_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {
            "$set": {
                "paid": False,
                "paid_date": None,
                "paid_by": None,
                "updated_at": now
            }
        }
    )
    
    await add_audit_history(
        db.bill_installments,
        installment_id,
        "unpay",
        user_id,
        {
            "bill_id": bill_id,
            "previous_paid_date": installment.get("paid_date"),
            "previous_paid_by": installment.get("paid_by"),
            "reason": "Pagamento desmarcado pelo usuário"
        }
    )
    
    logger.info(f"🔄 Parcela desmarcada como paga: {installment_id} por usuário {user_id}")
    
    if bill and bill.get("paid", False):
        logger.warning(f"⚠️ Conta {bill_id} está paga, mas parcela {installment_id} foi desmarcada")
        language = getattr(request.state, "language", "pt")
        return {
            "message": get_message("INSTALLMENT_UNPAY_SUCCESS_BUT_BILL_PAID", language),
            "success": True,
            "warning": "A conta mestra permanece como paga. Verifique a consistência."
        }
    
    paid_installments = await db.bill_installments.find_one({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": True
    })
    
    if not paid_installments:
        await db.bills.update_one(
            {
                "_id": ObjectId(bill_id),
                "user_id": user_id
            },
            {
                "$set": {
                    "paid": False,
                    "paid_date": None,
                    "updated_at": now
                }
            }
        )
        logger.info(f"🔄 Conta {bill_id} desmarcada como paga (nenhuma parcela paga)")
    else:
        await check_and_update_bill_status(bill_id, user_id, db, request)
    
    language = getattr(request.state, "language", "pt")
    return {
        "message": get_message("INSTALLMENT_UNPAY_SUCCESS", language),
        "success": True
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (pay: 30/min, pay-all: 20/min, unpay: 10/min)
#   - Auditoria completa (history + paid_by)
#   - Filtros avançados (paid, start_date, end_date)
#   - Rota /unpay com janela de reversão de 30 dias
#   - Validação de consistência da conta mestra
#   - Validação de intervalo de datas
#   - Fallback para installment_number
#
# ❌ Não implementado (Pós-MVP):
#   - Transações MongoDB: Free Tier não suporta (M10+ necessário)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Auditoria, /unpay, filtros (30/06/2026)
#   - v4: Rate limiting, validações (01/07/2026)
#   - v5: Refatoração - MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS, add_audit_history, validate_date_range movidos (02/07/2026)
#   - v5.1: Documentação atualizada para novo padrão
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO