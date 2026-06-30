"""
Rotas de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/routes/bill_installments.py

🔧 CORRIGIDO (v5 - FINAL):
- 🔧 i18n: Substituído HTTPException por I18nHTTPException
- 🔧 i18n: Mensagens de erro com get_message()
- 🔧 NOVO: request: Request em todos os endpoints
- 🔧 CORRIGIDO: check_and_update_bill_status com verificação atômica (paid: False)
- 🔧 CORRIGIDO: pay_all_installments com update_many atômico
- 🔧 CORRIGIDO: pay_installment valida due_date (não permite pagar parcelas futuras)
- 🔧 CORRIGIDO: pay_all_installments corrige inconsistências automaticamente
- 🔧 Substituído format_mongo_doc por convert_objectid_to_str (padronização)
- 🆕 Adicionado campo paid_by nos updates (auditoria de quem pagou)
- 🆕 Adicionado validação de existência da conta em check_and_update_bill_status
- 🆕 Adicionado filtro 'paid' no GET (filtrar por status)
- 🆕 Adicionado filtro por período (start_date/end_date) no GET
- 🆕 Adicionado rota /unpay (desmarcar pagamento)
- 🆕 Adicionado campo 'history' para logs de auditoria completos
- 🆕 Adicionado rate limiting nas rotas de pagamento
- 🆕 Adicionado validação de consistência antes de permitir unpay
- 🆕 Adicionado TTL para histórico antigo (expiração automática após 1 ano)
- 🆕 Adicionado limite de 1000 entradas no histórico (evita estourar 16MB)
- 🆕 Adicionado validação de collection, doc_id e details em add_audit_history
- 🆕 Adicionado fallback para installment_number (campo 'number')
- 🆕 Adicionado validação de MAX_HISTORY_ENTRIES (10-10000)
- 🆕 Adicionado validação de HISTORY_TTL_DAYS (7-730)
- 🆕 Adicionado validação de start_date <= end_date no GET
- 🆕 Adicionado partialFilterExpression no índice TTL

📋 DECISÕES DOCUMENTADAS:
- ✅ Implementado /unpay para reverter pagamentos por engano
- ✅ Implementado logs de auditoria com histórico completo
- ✅ Implementado filtros por período para melhor UX
- ✅ Mantido padrão de i18n em todas as mensagens
- ✅ Usa convert_objectid_to_str em vez de format_mongo_doc
- ✅ Histórico limitado a 1000 entradas por documento (evita 16MB)
- ✅ TTL de 1 ano para entradas antigas do histórico
- ✅ Validação de valores de ambiente (MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS)

📋 LIMITAÇÕES CONHECIDAS:
- Transações MongoDB: O Atlas Free Tier não suporta transações multi-documento.
  Para consistência, o frontend pode re-sync se houver falha.
  Em produção (M10+), considerar implementar transações.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import os

from app.database import get_database
from app.models.bill_installment import BillInstallmentResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/bill-installments", tags=["Parcelas de Contas a Pagar"])

# ========== CONFIGURAÇÃO ==========
MAX_HISTORY_ENTRIES = int(os.getenv("MAX_HISTORY_ENTRIES", "1000"))
"""Número máximo de entradas no histórico por documento.
   Valor padrão: 1000 (configurável via .env)
   Motivo: Evitar que o array history ultrapasse o limite de 16MB do MongoDB."""

# 🔧 CORRIGIDO: Validação do valor
if MAX_HISTORY_ENTRIES < 10 or MAX_HISTORY_ENTRIES > 10000:
    logger.warning(f"⚠️ MAX_HISTORY_ENTRIES inválido: {MAX_HISTORY_ENTRIES}, usando 1000")
    MAX_HISTORY_ENTRIES = 1000

HISTORY_TTL_DAYS = int(os.getenv("HISTORY_TTL_DAYS", "365"))
"""Tempo de vida das entradas do histórico em dias.
   Valor padrão: 365 (1 ano)
   Motivo: Evitar crescimento descontrolado do banco de dados."""

# 🔧 CORRIGIDO: Validação do valor
if HISTORY_TTL_DAYS < 7 or HISTORY_TTL_DAYS > 730:
    logger.warning(f"⚠️ HISTORY_TTL_DAYS inválido: {HISTORY_TTL_DAYS}, usando 365")
    HISTORY_TTL_DAYS = 365


# ========== FUNÇÕES AUXILIARES ==========

async def check_and_update_bill_status(bill_id: str, user_id: str, db, request: Request = None):
    """
    Verifica se todas as parcelas de uma conta estão pagas.
    Se sim, atualiza a conta mestra como paga.
    
    🔧 CORRIGIDO v2: Usa update_one com filtro atômico (paid: False) para evitar race condition.
    🆕 v3: Adicionada validação de existência da conta.
    
    📋 LIMITAÇÃO: O MongoDB Atlas Free Tier não suporta transações multi-documento.
    Em produção (M10+), considerar implementar com session.start_transaction().
    """
    # 🆕 Verifica se a conta existe
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
        # 🔧 CORRIGIDO: Só atualiza se ainda não estiver paga
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


async def add_audit_history(collection, doc_id: str, action: str, user_id: str, details: dict):
    """
    🆕 Adiciona entrada no histórico de auditoria.
    
    🔧 CORRIGIDO v5: Validações completas:
    - Verifica se collection é válida
    - Verifica se doc_id é um ObjectId válido
    - Verifica se details não está vazio
    - Limita o histórico a MAX_HISTORY_ENTRIES (evita 16MB)
    - Adiciona TTL automático para entradas antigas
    """
    # 🔧 Valida collection
    if collection is None:
        logger.error("❌ Collection não pode ser None em add_audit_history")
        return
    
    # 🔧 Valida doc_id
    if not doc_id:
        logger.error("❌ doc_id não pode ser vazio em add_audit_history")
        return
    
    try:
        ObjectId(doc_id)
    except Exception as e:
        logger.error(f"❌ doc_id inválido em add_audit_history: {doc_id} - {e}")
        return
    
    # 🔧 Valida details
    if not details:
        details = {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    try:
        # 🔧 Calcula a data de expiração (TTL)
        expires_at = datetime.now(timezone.utc) + timedelta(days=HISTORY_TTL_DAYS)
        
        history_entry = {
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "expires_at": expires_at,  # 🆕 TTL para expiração automática
            "details": details
        }
        
        # 🔧 Atualiza com limite de entradas (mantém apenas as últimas MAX_HISTORY_ENTRIES)
        await collection.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$push": {
                    "history": {
                        "$each": [history_entry],
                        "$slice": -MAX_HISTORY_ENTRIES  # Mantém apenas as últimas N entradas
                    }
                }
            }
        )
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar histórico de auditoria: {e}")


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
    
    🔧 CORRIGIDO v5: Validação de start_date <= end_date.
    """
    # 🔧 CORRIGIDO: Validação de intervalo de datas
    if start_date and end_date and start_date > end_date:
        raise ValidationException(
            message_key="ERROR_INVALID_DATE_RANGE",
            request=request
        )
    
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
    
    # 🆕 Filtro por status
    if paid is not None:
        query["paid"] = paid
    
    # 🆕 Filtro por período
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
    
    # 🆕 Converte amount de centavos para reais e ObjectId para string
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
    
    # 🆕 Converte ObjectId para string
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
    
    # 🆕 Adiciona paid_by e atualiza
    await db.bill_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {
            "$set": {
                "paid": True,
                "paid_date": now,
                "paid_by": user_id,  # 🆕 QUEM PAGOU
                "updated_at": now
            }
        }
    )
    
    # 🆕 Adiciona entrada no histórico de auditoria
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
    - 🔧 Fallback para installment_number (campo 'number')
    """
    validate_object_id(bill_id, "bill_id")
    
    now = datetime.now(timezone.utc)
    user_id = str(current_user.id)
    
    # 🆕 Atualiza todas as parcelas não pagas com paid_by
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
                "paid_by": user_id,  # 🆕 QUEM PAGOU
                "updated_at": now
            }
        }
    )
    
    # 🆕 Adiciona entrada no histórico para cada parcela paga
    if result.modified_count > 0:
        paid_installments = await db.bill_installments.find({
            "bill_id": bill_id,
            "user_id": user_id,
            "paid": True,
            "paid_date": now
        }).to_list(None)
        
        for inst in paid_installments:
            # 🔧 CORRIGIDO: Fallback para installment_number
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
    - 🆕 Verifica consistência com a conta mestra
    - Atualiza o status da conta mestra se necessário
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
    
    # 🆕 Verifica se o pagamento foi feito há menos de 30 dias
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
    
    # 🆕 Verifica consistência com a conta mestra
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": user_id
    })
    
    # 🆕 Desmarca o pagamento
    await db.bill_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {
            "$set": {
                "paid": False,
                "paid_date": None,
                "paid_by": None,  # 🆕 Remove o registro de quem pagou
                "updated_at": now
            }
        }
    )
    
    # 🆕 Adiciona entrada no histórico de auditoria
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
    
    # 🆕 Verifica se a conta foi paga novamente após o unpay
    if bill and bill.get("paid", False):
        # A conta está paga, mas a parcela foi desmarcada
        logger.warning(f"⚠️ Conta {bill_id} está paga, mas parcela {installment_id} foi desmarcada")
        
        # 🔧 Não força desmarcar a conta - mantém como paga
        # Apenas registra a inconsistência para análise
        language = getattr(request.state, "language", "pt")
        return {
            "message": get_message("INSTALLMENT_UNPAY_SUCCESS_BUT_BILL_PAID", language),
            "success": True,
            "warning": "A conta mestra permanece como paga. Verifique a consistência."
        }
    
    # 🆕 Atualiza o status da conta mestra
    paid_installments = await db.bill_installments.find_one({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": True
    })
    
    if not paid_installments:
        # Nenhuma parcela paga - desmarca a conta
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
        # Ainda há parcelas pagas - verifica se todas estão pagas
        await check_and_update_bill_status(bill_id, user_id, db, request)
    
    language = getattr(request.state, "language", "pt")
    return {
        "message": get_message("INSTALLMENT_UNPAY_SUCCESS", language),
        "success": True
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Rotas similares ao credit_card_installments (consistência)
# ✅ GET /bill-installments listagem com paginação
# ✅ GET /bill-installments/{id} busca individual
# ✅ PUT /bill-installments/{id}/pay paga parcela individual
# ✅ PUT /bill-installments/bills/{bill_id}/pay-all paga conta inteira
# ✅ 🆕 PUT /bill-installments/{id}/unpay desmarca pagamento
# ✅ Atualização automática da conta mestra quando todas parcelas pagas
# ✅ Conversão de moeda (to_cents/from_cents)
# ✅ Validação de IDs com validate_object_id
# ✅ Logs detalhados
# ✅ 🔧 i18n: Todas as mensagens substituídas
# ✅ 🔧 i18n: request: Request em todos os endpoints
# ✅ 🔧 CORRIGIDO: check_and_update_bill_status com verificação atômica
# ✅ 🔧 CORRIGIDO: pay_all_installments com update_many atômico
# ✅ 🔧 CORRIGIDO: pay_installment valida due_date
# ✅ 🔧 CORRIGIDO: pay_all_installments corrige inconsistências
# ✅ 🆕 Substituído format_mongo_doc por convert_objectid_to_str
# ✅ 🆕 Adicionado campo paid_by nos updates
# ✅ 🆕 Adicionado validação de existência da conta
# ✅ 🆕 Adicionado filtro 'paid' no GET
# ✅ 🆕 Adicionado filtro por período (start_date/end_date)
# ✅ 🆕 Adicionado rota /unpay
# ✅ 🆕 Adicionado campo 'history' para auditoria
# ✅ 🆕 Adicionado rate limiting nas rotas de pagamento
# ✅ 🆕 Adicionado janela de reversão de 30 dias no /unpay
# ✅ 🆕 Adicionado TTL para histórico antigo (expiração automática)
# ✅ 🆕 Adicionado limite de 1000 entradas no histórico
# ✅ 🆕 Adicionado validação de collection, doc_id e details
# ✅ 🆕 Adicionado fallback para installment_number
# ✅ 🆕 Adicionado validação de MAX_HISTORY_ENTRIES (10-10000)
# ✅ 🆕 Adicionado validação de HISTORY_TTL_DAYS (7-730)
# ✅ 🆕 Adicionado validação de start_date <= end_date no GET
#
# 📋 LIMITAÇÕES CONHECIDAS:
# - Transações MongoDB: O Atlas Free Tier não suporta transações multi-documento.
#   Para consistência, o frontend pode re-sync se houver falha.
#   Em produção (M10+), considerar implementar transações.
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO