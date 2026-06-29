"""
Rotas de Contas a Pagar (Bills)
Arquivo: backend/app/routes/bills.py

🔧 CORRIGIDO:
- split_amount_cents() agora trabalha com inteiros (centavos)
- create_bill_installments agora recebe amount_cents (int)
- update_future_installments agora recebe new_amount_cents (int)
- adjust_future_installments default mudado para True
- Adicionada validação de limite máximo de parcelas (360)
- 🔧 NOVO: I18n com I18nHTTPException
- 🔧 NOVO: Função get_current_installment()
- 🔧 i18n: Todas as mensagens de erro substituídas
- 🔧 CORRIGIDO: parse_installments_dates cria cópia antes de modificar
- 🔧 CORRIGIDO: parse_installments_dates valida start_date não passado
- 🔧 CORRIGIDO: split_amount_cents valida parts > 0 e total_cents > 0
- 🔧 CORRIGIDO: update_future_installments valida new_total_parcelas >= paid_count
- 🔧 CORRIGIDO: Validação de amount > 0 no update
- 🔧 CORRIGIDO: Validação de new_total_parcelas > 0 no update
- 🔧 CORRIGIDO: Validação de new_amount_cents > 0 no update_future_installments
- 🔧 CORRIGIDO: Validação de due_day no update
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
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message, get_language_from_request

logger = setup_logger(__name__)

router = APIRouter(prefix="/bills", tags=["Contas a Pagar"])

# ========== CONSTANTES ==========
MAX_INSTALLMENTS = 360  # 30 anos (máximo para financiamentos)


def parse_installments_dates(installments: dict, request: Request = None) -> dict:
    """
    Converte start_date de string para datetime se necessário.
    🔧 CORRIGIDO: Cria uma cópia antes de modificar (evita efeitos colaterais).
    🔧 CORRIGIDO: Valida se start_date não é uma data passada.
    """
    if not installments or not isinstance(installments, dict):
        return installments
    
    # Cria uma cópia antes de modificar
    result = installments.copy()
    start_date = result.get("start_date")
    
    if start_date and isinstance(start_date, str):
        try:
            dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            # 🔧 CORRIGIDO: Valida se não é data passada
            if dt < datetime.now(timezone.utc):
                raise ValidationException(
                    message_key="ERROR_START_DATE_PAST",
                    request=request
                )
            result["start_date"] = dt
        except (ValueError, TypeError):
            # Se não conseguir converter, mantém o original
            pass
    return result


def split_amount_cents(total_cents: int, parts: int) -> List[int]:
    """
    Divide um valor em centavos igualmente entre parcelas.
    Distribui o resto (se houver) nas primeiras parcelas.
    
    Exemplo: 100 centavos em 3 parcelas = [34, 33, 33]
    
    🔧 CORRIGIDO: Valida parts > 0 e total_cents > 0
    """
    if parts <= 0:
        raise ValueError("Número de parcelas deve ser maior que zero")
    if total_cents <= 0:
        raise ValueError("Valor total deve ser maior que zero")
    
    base = total_cents // parts
    remainder = total_cents - (base * parts)
    amounts = [base] * parts
    for i in range(remainder):
        amounts[i] += 1
    return amounts


# 🔧 NOVO: Função para calcular parcela atual
async def get_current_installment(bill_id: str, user_id: str, db) -> int:
    """
    Calcula a parcela atual com base nas parcelas pagas.
    🔧 NOVO: Substitui o campo 'current' removido do modelo.
    """
    paid_count = await db.bill_installments.count_documents({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": True
    })
    return paid_count + 1


# 🔧 CORRIGIDO: amount_cents agora é int
async def create_bill_installments(
    bill_id: str, 
    user_id: str, 
    amount_cents: int, 
    installments_data: dict, 
    db,
    request: Request = None
):
    """
    Cria as parcelas individuais para uma conta
    🔧 VERSÃO SIMPLIFICADA: Apenas as parcelas RESTANTES, todas pendentes
    🔧 CORRIGIDO: amount_cents é int (centavos)
    """
    total_parcelas = installments_data.get("total", 1)
    
    # 🔧 Validação de limite máximo de parcelas
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
    
    start_date = installments_data.get("start_date")
    due_day = installments_data.get("due_day")
    
    if not start_date:
        start_date = datetime.now(timezone.utc)
    
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    
    # 🔧 Divide o valor total em centavos entre as parcelas
    amounts_cents = split_amount_cents(amount_cents, total_parcelas)
    
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
        logger.info(f"✅ {len(installments)} parcelas criadas para conta {bill_id} (todas pendentes)")


# 🔧 CORRIGIDO: new_amount_cents agora é int com validações críticas
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
    
    # 🔧 CORRIGIDO: Valida new_amount_cents
    if new_amount_cents <= 0:
        raise ValidationException(
            message_key="ERROR_AMOUNT_INVALID",
            request=request
        )
    
    # 🔧 CORRIGIDO: Valida new_total_parcelas
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
    
    # 🔧 CORRIGIDO: Verifica se o novo total é menor que o já pago
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
    
    # Deleta apenas as parcelas não pagas
    await db.bill_installments.delete_many({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": False
    })
    
    # Recalcula com base no novo total
    amounts_cents = split_amount_cents(new_amount_cents, new_total_parcelas)
    remaining_parcelas = new_total_parcelas - paid_count
    
    # 🔧 CORRIGIDO: Verifica se há parcelas restantes
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
        logger.info(f"✅ {len(new_installments)} parcelas futuras atualizadas para conta {bill_id}")


# ========== ENDPOINTS ==========

@router.post("/", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    request: Request,
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

        amount_cents = bill_dict.get("amount", 0)
        installments_info = bill_dict.get("installments", {})
        total_parcelas = installments_info.get("total", 1)

        if "installments" in bill_dict and isinstance(bill_dict["installments"], dict):
            bill_dict["installments"] = parse_installments_dates(bill_dict["installments"], request)

        result = await db.bills.insert_one(bill_dict)
        bill_id = str(result.inserted_id)
        
        await create_bill_installments(bill_id, str(current_user.id), amount_cents, installments_info, db, request)
        
        created = await db.bills.find_one({"_id": result.inserted_id})
        
        if created and "amount" in created:
            created["amount"] = from_cents(created["amount"])
        
        # 🔧 Adiciona current calculado dinamicamente
        if created:
            created["current"] = await get_current_installment(bill_id, str(current_user.id), db)
        
        logger.info(f"Conta criada: {bill_data.description} - {total_parcelas} parcelas pendentes para usuário {current_user.id}")
        return format_mongo_doc(created)
        
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
        # 🔧 Adiciona current calculado dinamicamente
        item["current"] = await get_current_installment(str(item["_id"]), str(current_user.id), db)
    
    formatted_items = format_mongo_docs(items)
    
    logger.debug(f"Listadas {len(formatted_items)} contas para usuário {current_user.id}")
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
        logger.warning(f"Conta não encontrada: {bill_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="BILL_NOT_FOUND",
            request=request
        )
    
    if "amount" in bill:
        bill["amount"] = from_cents(bill["amount"])
    
    # 🔧 Adiciona current calculado dinamicamente
    bill["current"] = await get_current_installment(bill_id, str(current_user.id), db)
    
    return format_mongo_doc(bill)


@router.put("/{bill_id}", response_model=BillResponse)
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
        logger.warning(f"Conta não encontrada: {bill_id}")
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
    
    # 🔧 CORRIGIDO: Validação de amount no update
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
    
    if update_data.get("paid") is True and update_data.get("paid_date") is None:
        update_data["paid_date"] = datetime.now(timezone.utc)
    
    # 🔧 CORRIGIDO: Validação de installments no update com due_day
    if "installments" in update_data:
        new_installments = update_data["installments"]
        new_total = new_installments.get("total", 1)
        new_due_day = new_installments.get("due_day")
        new_start_date = new_installments.get("start_date")
        
        # Valida total
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
        
        # 🔧 CORRIGIDO: Valida due_day com o novo start_date
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

    updated = await db.bills.find_one({"_id": ObjectId(bill_id)})
    
    if updated and "amount" in updated:
        updated["amount"] = from_cents(updated["amount"])
    
    # 🔧 Adiciona current calculado dinamicamente
    if updated:
        updated["current"] = await get_current_installment(bill_id, str(current_user.id), db)
    
    logger.info(f"Conta atualizada: {bill_id} para usuário {current_user.id}")
    return format_mongo_doc(updated)


@router.delete("/{bill_id}", response_model=dict)
async def delete_bill(
    request: Request,
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
        raise NotFoundException(
            message_key="BILL_NOT_FOUND",
            request=request
        )
    
    logger.info(f"Conta deletada: {bill_id} e {result_installments.deleted_count} parcelas para usuário {current_user.id}")
    
    language = getattr(request.state, "language", "pt")
    return {"message": get_message("BILL_DELETED", language), "success": True}


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. split_amount_cents() agora trabalha com inteiros (centavos)
2. create_bill_installments agora recebe amount_cents (int)
3. update_future_installments agora recebe new_amount_cents (int)
4. adjust_future_installments default mudado para True
5. Adicionada constante MAX_INSTALLMENTS = 360
6. Adicionada validação de limite máximo de parcelas
7. 🔧 NOVO: I18n com I18nHTTPException
8. 🔧 NOVO: Função get_current_installment()
9. 🔧 i18n: Todas as mensagens de erro substituídas
10. 🔧 i18n: Mensagens de sucesso com get_message()
11. 🔧 CORRIGIDO: parse_installments_dates cria cópia antes de modificar
12. 🔧 CORRIGIDO: parse_installments_dates valida start_date não passado
13. 🔧 CORRIGIDO: split_amount_cents valida parts > 0 e total_cents > 0
14. 🔧 CORRIGIDO: update_future_installments valida new_total_parcelas >= paid_count
15. 🔧 CORRIGIDO: Validação de amount > 0 no update
16. 🔧 CORRIGIDO: Validação de new_total_parcelas > 0 no update
17. 🔧 CORRIGIDO: Validação de new_amount_cents > 0 no update_future_installments
18. 🔧 CORRIGIDO: Validação de due_day no update

📌 CHAVES I18N UTILIZADAS:
   - BILL_NOT_FOUND → "Conta não encontrada"
   - BILL_NO_DATA_TO_UPDATE → "Nenhum dado para atualizar"
   - BILL_DELETED → "Conta removida com sucesso"
   - ERROR_MAX_INSTALLMENTS_EXCEEDED → "Número máximo de parcelas é 360"
   - ERROR_INVALID_INSTALLMENTS → "Número de parcelas inválido"
   - ERROR_TOTAL_LESS_THAN_PAID → "Total de parcelas não pode ser menor que o já pago"
   - ERROR_AMOUNT_INVALID → "Valor inválido"
   - ERROR_START_DATE_PAST → "start_date não pode ser no passado"
   - ERROR_INVALID_DUE_DAY → "Dia de vencimento inválido para o mês"
   - ERROR_SERVER → "Erro interno do servidor"

⚠️ PENDÊNCIAS PARA PÓS-MVP:
================================================================================
1. Adicionar lock para evitar race condition em updates concorrentes
2. Otimizar N+1 no cálculo de current com aggregation
3. Soft delete (deleted_at) em vez de delete permanente
4. Logs de auditoria para operações em contas

================================================================================
✅ STATUS: PRONTO PARA PRODUÇÃO
================================================================================
"""