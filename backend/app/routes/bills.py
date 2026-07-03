"""
Rotas de Contas a Pagar (Bills)
Arquivo: backend/app/routes/bills.py

Funcionalidades:
- POST /bills: Criar conta com parcelas
- GET /bills: Listar contas com paginação, filtros e ordenação
- GET /bills/{id}: Buscar conta específica
- PUT /bills/{id}: Atualizar conta (com ajuste de parcelas futuras)
- DELETE /bills/{id}: Remover conta e parcelas

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (create: 30/min, update: 20/min, delete: 10/min)
- Auditoria completa (history + paid_by)
- Filtros por status (paid) e categoria
- Ordenação personalizada (sort_by, sort_order)
- Validação de due_day, start_date e amount
- Cálculo automático de parcela atual

Versão: v5.1 (refatorado)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from bson import ObjectId
from calendar import monthrange

from app.database import get_database
from app.models.bill import BillCreate, BillResponse, BillUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter, get_user_rate_limit_key

# ========== NOVOS IMPORTS ==========
from app.core.constants import MAX_INSTALLMENTS, MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS
from app.utils.audit import add_audit_history
from app.utils.installments import split_amount_cents
from app.utils.date_utils import parse_installments_dates
from app.utils.validators_extras import validate_amount

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message, get_language_from_request

logger = setup_logger(__name__)

router = APIRouter(prefix="/bills", tags=["Contas a Pagar"])


# ========== FUNÇÕES AUXILIARES ==========

async def get_current_installment(bill_id: str, user_id: str, db) -> int:
    """
    Calcula a parcela atual com base nas parcelas pagas.
    Substitui o campo 'current' removido do modelo.
    """
    paid_count = await db.bill_installments.count_documents({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": True
    })
    return paid_count + 1


async def create_bill_installments(
    bill_id: str, 
    user_id: str, 
    amount_cents: int, 
    installments_data: dict, 
    db,
    request: Request = None
):
    """
    Cria as parcelas individuais para uma conta.
    Apenas as parcelas RESTANTES, todas pendentes.
    """
    total_parcelas = installments_data.get("total", 1)
    start_date = installments_data.get("start_date")
    due_day = installments_data.get("due_day")
    
    if total_parcelas > MAX_INSTALLMENTS:
        raise ValidationException(
            message_key="ERROR_MAX_INSTALLMENTS_EXCEEDED",
            request=request
        )
    
    if total_parcelas <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_INSTALLMENTS",
            request=request
        )
    
    if due_day:
        if not start_date:
            start_date = datetime.now(timezone.utc)
        elif isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        
        if isinstance(start_date, datetime):
            _, last_day = monthrange(start_date.year, start_date.month)
            if due_day > last_day:
                raise ValidationException(
                    message_key="ERROR_INVALID_DUE_DAY",
                    request=request
                )
    
    if not start_date:
        start_date = datetime.now(timezone.utc)
    
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    
    amounts_cents = split_amount_cents(amount_cents, total_parcelas)
    
    installments = []
    for i in range(total_parcelas):
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
        
        installment = {
            "bill_id": bill_id,
            "user_id": user_id,
            "number": i + 1,
            "amount": amounts_cents[i],
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)
    
    if installments:
        await db.bill_installments.insert_many(installments)
        logger.info(f"✅ {len(installments)} parcelas criadas para conta {bill_id}")


async def update_future_installments(
    bill_id: str, 
    user_id: str, 
    new_amount_cents: int, 
    new_total_parcelas: int, 
    new_start_date: datetime, 
    db,
    request: Request = None
):
    """Atualiza parcelas futuras (não pagas) de uma conta"""
    
    if new_amount_cents <= 0:
        raise ValidationException(
            message_key="ERROR_AMOUNT_INVALID",
            request=request
        )
    
    if new_total_parcelas <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_INSTALLMENTS",
            request=request
        )
    
    if new_total_parcelas > MAX_INSTALLMENTS:
        raise ValidationException(
            message_key="ERROR_MAX_INSTALLMENTS_EXCEEDED",
            request=request
        )
    
    paid_count = await db.bill_installments.count_documents({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": True
    })
    
    if new_total_parcelas < paid_count:
        raise ValidationException(
            message_key="ERROR_TOTAL_LESS_THAN_PAID",
            request=request
        )
    
    await db.bill_installments.delete_many({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": False
    })
    
    amounts_cents = split_amount_cents(new_amount_cents, new_total_parcelas)
    remaining_parcelas = new_total_parcelas - paid_count
    
    if remaining_parcelas <= 0:
        logger.info(f"ℹ️ Nenhuma parcela restante para criar (paid_count={paid_count}, new_total={new_total_parcelas})")
        return
    
    remaining_start_date = new_start_date + relativedelta(months=paid_count)
    
    new_installments = []
    for i in range(remaining_parcelas):
        due_date = remaining_start_date + relativedelta(months=i)
        installment = {
            "bill_id": bill_id,
            "user_id": user_id,
            "number": paid_count + i + 1,
            "amount": amounts_cents[paid_count + i],
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        new_installments.append(installment)
    
    if new_installments:
        await db.bill_installments.insert_many(new_installments)
        logger.info(f"✅ {len(new_installments)} parcelas futuras atualizadas")


# ========== ENDPOINTS ==========

@router.post("/", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_bill(
    request: Request,
    bill_data: BillCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova conta a pagar com parcelas individuais."""
    try:
        bill_dict = bill_data.model_dump()
        bill_dict["user_id"] = str(current_user.id)
        bill_dict["paid"] = False
        bill_dict["paid_date"] = None
        bill_dict["created_at"] = datetime.now(timezone.utc)
        bill_dict["updated_at"] = datetime.now(timezone.utc)

        amount_cents = bill_dict.get("amount", 0)
        installments_info = bill_dict.get("installments", {})

        if "installments" in bill_dict and isinstance(bill_dict["installments"], dict):
            bill_dict["installments"] = parse_installments_dates(bill_dict["installments"], request)

        result = await db.bills.insert_one(bill_dict)
        bill_id = str(result.inserted_id)
        
        await create_bill_installments(bill_id, str(current_user.id), amount_cents, installments_info, db, request)
        
        created = await db.bills.find_one({"_id": result.inserted_id})
        
        if created and "amount" in created:
            created["amount"] = from_cents(created["amount"])
        
        if created:
            created["current"] = await get_current_installment(bill_id, str(current_user.id), db)
        
        await add_audit_history(
            db.bills,
            bill_id,
            "create",
            str(current_user.id),
            {
                "description": bill_data.description,
                "amount": amount_cents,
                "total_installments": installments_info.get("total", 1)
            }
        )
        
        logger.info(f"✅ Conta criada: {bill_data.description} para usuário {current_user.id}")
        return convert_objectid_to_str(created)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao criar conta: {e}")
        import traceback
        logger.debug(f"Detalhes do erro: {traceback.format_exc()}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


@router.get("/", response_model=dict)
async def list_bills(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página (máx 100)"),
    paid: Optional[bool] = Query(None, description="Filtrar por status de pagamento"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    sort_by: str = Query("created_at", description="Campo para ordenação (created_at, due_date, amount, paid, updated_at)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista contas do usuário com paginação, filtros e ordenação.
    
    🔧 CORRIGIDO: Mapeamento de campos para ordenação
    - due_date → installments.start_date (campo correto)
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if paid is not None:
        query["paid"] = paid
    
    if category:
        query["category"] = category
    
    sort_field_mapping = {
        "created_at": "created_at",
        "due_date": "installments.start_date",
        "amount": "amount",
        "paid": "paid",
        "updated_at": "updated_at"
    }
    
    sort_field = sort_field_mapping.get(sort_by, "created_at")
    sort_direction = -1 if sort_order == "desc" else 1

    items, total = await paginate_query(
        db.bills, query, params, sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        if "amount" in item:
            item["amount"] = from_cents(item["amount"])
        item["current"] = await get_current_installment(str(item["_id"]), str(current_user.id), db)
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listadas {len(formatted_items)} contas para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.get("/{bill_id}", response_model=BillResponse)
async def get_bill(
    request: Request,
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
        logger.warning(f"⚠️ Conta não encontrada: {bill_id}")
        raise NotFoundException(
            message_key="BILL_NOT_FOUND",
            request=request
        )
    
    if "amount" in bill:
        bill["amount"] = from_cents(bill["amount"])
    
    bill["current"] = await get_current_installment(bill_id, str(current_user.id), db)
    
    return convert_objectid_to_str(bill)


@router.put("/{bill_id}", response_model=BillResponse)
@limiter.limit("20/minute")
async def update_bill(
    request: Request,
    bill_id: str,
    bill_update: BillUpdate,
    adjust_future_installments: bool = Query(
        True,
        description="Se True, ajusta parcelas futuras com os novos valores"
    ),
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
        logger.warning(f"⚠️ Conta não encontrada: {bill_id}")
        raise NotFoundException(
            message_key="BILL_NOT_FOUND",
            request=request
        )
    
    update_data = {k: v for k, v in bill_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise ValidationException(
            message_key="BILL_NO_DATA_TO_UPDATE",
            request=request
        )
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    amount_cents = None
    if "amount" in update_data:
        amount_cents = update_data["amount"]
        if isinstance(amount_cents, float):
            amount_cents = int(amount_cents)
        if amount_cents <= 0:
            raise ValidationException(
                message_key="ERROR_AMOUNT_INVALID",
                request=request
            )
        update_data["amount"] = amount_cents
    
    # Quando marcar como paga, registra quem está realizando a ação
    if update_data.get("paid") is True and update_data.get("paid_date") is None:
        update_data["paid_date"] = datetime.now(timezone.utc)
        update_data["paid_by"] = str(current_user.id)
    
    if "installments" in update_data:
        new_installments = update_data["installments"]
        new_total = new_installments.get("total", 1)
        new_due_day = new_installments.get("due_day")
        new_start_date = new_installments.get("start_date")
        
        if new_total > MAX_INSTALLMENTS:
            raise ValidationException(
                message_key="ERROR_MAX_INSTALLMENTS_EXCEEDED",
                request=request
            )
        if new_total <= 0:
            raise ValidationException(
                message_key="ERROR_INVALID_INSTALLMENTS",
                request=request
            )
        
        if new_start_date:
            if isinstance(new_start_date, str):
                try:
                    new_start_date = datetime.fromisoformat(new_start_date.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
            
            if isinstance(new_start_date, datetime) and new_start_date < datetime.now(timezone.utc):
                raise ValidationException(
                    message_key="ERROR_START_DATE_PAST",
                    request=request
                )
        
        if new_due_day and new_start_date:
            if isinstance(new_start_date, str):
                try:
                    new_start_date = datetime.fromisoformat(new_start_date.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
            
            if isinstance(new_start_date, datetime):
                _, last_day = monthrange(new_start_date.year, new_start_date.month)
                if new_due_day > last_day:
                    raise ValidationException(
                        message_key="ERROR_INVALID_DUE_DAY",
                        request=request
                    )
        
        update_data["installments"] = parse_installments_dates(update_data["installments"], request)

    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise NotFoundException(
            message_key="BILL_NOT_FOUND",
            request=request
        )

    if adjust_future_installments and amount_cents is not None:
        new_installments_info = update_data.get("installments", current_bill.get("installments", {}))
        new_total = new_installments_info.get("total", 1)
        new_start_date = new_installments_info.get("start_date", datetime.now(timezone.utc))
        
        await update_future_installments(
            bill_id, 
            str(current_user.id), 
            amount_cents, 
            new_total, 
            new_start_date, 
            db,
            request
        )

    await add_audit_history(
        db.bills,
        bill_id,
        "update",
        str(current_user.id),
        {
            "changes": update_data,
            "adjust_future_installments": adjust_future_installments
        }
    )

    updated = await db.bills.find_one({"_id": ObjectId(bill_id)})
    
    if updated and "amount" in updated:
        updated["amount"] = from_cents(updated["amount"])
    
    if updated:
        updated["current"] = await get_current_installment(bill_id, str(current_user.id), db)
    
    logger.info(f"✅ Conta atualizada: {bill_id} para usuário {current_user.id}")
    return convert_objectid_to_str(updated)


@router.delete("/{bill_id}", response_model=dict)
@limiter.limit("10/minute")
async def delete_bill(
    request: Request,
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma conta e todas as suas parcelas"""
    validate_object_id(bill_id, "bill_id")
    
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    
    result_installments = await db.bill_installments.delete_many({
        "bill_id": bill_id,
        "user_id": str(current_user.id)
    })
    
    result = await db.bills.delete_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    
    if result.deleted_count == 0:
        logger.warning(f"⚠️ Tentativa de deletar conta inexistente: {bill_id}")
        raise NotFoundException(
            message_key="BILL_NOT_FOUND",
            request=request
        )
    
    if bill:
        await add_audit_history(
            db.bills,
            bill_id,
            "delete",
            str(current_user.id),
            {
                "description": bill.get("description"),
                "amount": bill.get("amount"),
                "installments_deleted": result_installments.deleted_count
            }
        )
    
    logger.info(f"🗑️ Conta deletada: {bill_id} e {result_installments.deleted_count} parcelas para usuário {current_user.id}")
    
    language = getattr(request.state, "language", "pt")
    return {"message": get_message("BILL_DELETED", language), "success": True}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (create: 30/min, update: 20/min, delete: 10/min)
#   - Auditoria completa (history + paid_by)
#   - Filtros por status (paid) e categoria
#   - Ordenação personalizada (sort_by, sort_order)
#   - Validação de due_day, start_date e amount
#   - Cálculo automático de parcela atual
#   - Mapeamento de sort_by: due_date → installments.start_date
#
# ❌ Não implementado (Pós-MVP):
#   - Transações MongoDB: Free Tier não suporta (M10+ necessário)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Auditoria, filtros, ordenação (30/06/2026)
#   - v4: Rate limiting, validações (01/07/2026)
#   - v5: Refatoração - constantes, audit, installments, date_utils (02/07/2026)
#   - v5.1: Documentação atualizada para novo padrão
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO