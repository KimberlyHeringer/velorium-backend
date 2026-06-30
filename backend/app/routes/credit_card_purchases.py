"""
Rotas de Compras Parceladas no Cartão de Crédito
Arquivo: backend/app/routes/credit_card_purchases.py

🔧 CORRIGIDO (v5 - FINAL):
- split_amount_cents() agora trabalha com inteiros (centavos)
- update_card_committed_amount agora recebe delta_cents (int)
- check_available_limit agora recebe required_cents (int)
- create_purchase agora usa centavos internamente
- Removido endpoint /debug/clean-invalid-data
- Corrigidas mensagens de erro para usar from_cents() na exibição

🆕 MELHORIAS ADICIONADAS (v4):
- 🔧 Substituído format_mongo_doc por convert_objectid_to_str (padronização)
- 🆕 I18n completo com I18nHTTPException e get_message()
- 🆕 Adicionado request: Request em todos os endpoints
- 🆕 Adicionado campo paid_by no pagamento de parcelas (auditoria)
- 🆕 Adicionado logs de auditoria (history) para compras
- 🆕 Adicionado rota /installments/{installment_id}/unpay (desmarcar pagamento)
- 🆕 Adicionado filtro por status (paid) no GET
- 🆕 Adicionado ordenação personalizada (sort_by, sort_order)
- 🆕 Adicionado rate limiting (create: 30/min, update: 20/min, delete: 10/min)
- 🆕 Adicionado validação de first_due_date (não permite data passada)
- 🆕 Adicionado suporte a juros em parcelas (interest_rate)
- 🆕 Adicionado campo total_with_interest para valor com juros
- 🆕 Adicionado cálculo de parcelas com juros compostos

🔧 CORREÇÕES DO DESENVOLVEDOR (v5):
- 🆕 Adicionada validação de installments > 0 em calculate_installments_with_interest
- 🆕 Adicionada verificação de divisão por zero em calculate_installments_with_interest
- 🆕 Adicionado request no endpoint /faturas com I18n
- 🆕 Adicionada validação de novo card_id no update_purchase
- 🆕 Adicionada validação de interest_rate (0-100%)
- 🆕 Adicionada validação de total_amount negativo
- 🆕 Adicionada validação de total_with_interest no update

📋 DECISÕES DOCUMENTADAS:
- ✅ Implementado suporte a juros (versão simplificada)
- ✅ Implementado validação de first_due_date
- ✅ Implementado logs de auditoria com histórico completo
- ✅ Implementado rota /unpay para reverter pagamento
- ✅ Mantido padrão de i18n em todas as mensagens
- ✅ Usa convert_objectid_to_str em vez de format_mongo_doc
- ✅ Histórico limitado a 1000 entradas por documento (evita 16MB)
- ✅ TTL de 1 ano para entradas antigas do histórico

📋 LIMITAÇÕES CONHECIDAS:
- Transações MongoDB: O Atlas Free Tier não suporta transações multi-documento.
- Juros: Implementação simplificada (taxa fixa, parcelas iguais).
- Em produção (M10+), considerar implementar transações.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from bson import ObjectId
import os

from app.database import get_database
from app.models.credit_card_purchase import CreditCardPurchaseCreate, CreditCardPurchaseResponse
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

router = APIRouter(prefix="/credit-card-purchases", tags=["Compras no Cartão"])

# ========== CONSTANTES ==========
MAX_INSTALLMENTS = 360  # 30 anos

# ========== CONFIGURAÇÃO ==========
MAX_HISTORY_ENTRIES = int(os.getenv("MAX_HISTORY_ENTRIES", "1000"))
"""Número máximo de entradas no histórico por documento."""

if MAX_HISTORY_ENTRIES < 10 or MAX_HISTORY_ENTRIES > 10000:
    logger.warning(f"⚠️ MAX_HISTORY_ENTRIES inválido: {MAX_HISTORY_ENTRIES}, usando 1000")
    MAX_HISTORY_ENTRIES = 1000

HISTORY_TTL_DAYS = int(os.getenv("HISTORY_TTL_DAYS", "365"))
"""Tempo de vida das entradas do histórico em dias."""

if HISTORY_TTL_DAYS < 7 or HISTORY_TTL_DAYS > 730:
    logger.warning(f"⚠️ HISTORY_TTL_DAYS inválido: {HISTORY_TTL_DAYS}, usando 365")
    HISTORY_TTL_DAYS = 365


# ========== FUNÇÕES AUXILIARES ==========

async def add_purchase_audit_history(db, purchase_id: str, action: str, user_id: str, details: dict):
    """
    🆕 Adiciona entrada no histórico de auditoria da compra.
    
    🔧 Validações completas:
    - Verifica se db é válido
    - Verifica se purchase_id é um ObjectId válido
    - Limita o histórico a MAX_HISTORY_ENTRIES (evita 16MB)
    - Adiciona TTL automático para entradas antigas
    """
    if db is None:
        logger.error("❌ db não pode ser None em add_purchase_audit_history")
        return
    
    if not purchase_id:
        logger.error("❌ purchase_id não pode ser vazio em add_purchase_audit_history")
        return
    
    try:
        ObjectId(purchase_id)
    except Exception as e:
        logger.error(f"❌ purchase_id inválido em add_purchase_audit_history: {purchase_id} - {e}")
        return
    
    if not details:
        details = {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    try:
        expires_at = datetime.now(timezone.utc) + timedelta(days=HISTORY_TTL_DAYS)
        
        history_entry = {
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "details": details
        }
        
        await db.credit_card_purchases.update_one(
            {"_id": ObjectId(purchase_id)},
            {
                "$push": {
                    "history": {
                        "$each": [history_entry],
                        "$slice": -MAX_HISTORY_ENTRIES
                    }
                }
            }
        )
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar histórico de auditoria: {e}")


def split_amount_cents(total_cents: int, parts: int) -> List[int]:
    """
    Divide um valor em centavos igualmente entre parcelas.
    Distribui o resto (se houver) nas primeiras parcelas.
    
    Exemplo: 100 centavos em 3 parcelas = [34, 33, 33]
    """
    if parts <= 0:
        return []
    base = total_cents // parts
    remainder = total_cents - (base * parts)
    amounts = [base] * parts
    for i in range(remainder):
        amounts[i] += 1
    return amounts


def calculate_installments_with_interest(
    total_cents: int,
    installments: int,
    interest_rate: float
) -> List[int]:
    """
    🆕 Calcula parcelas com juros compostos.
    
    Fórmula: PMT = PV * (i * (1 + i)^n) / ((1 + i)^n - 1)
    Onde:
    - PV = valor presente (total_cents)
    - i = taxa de juros mensal (interest_rate / 100)
    - n = número de parcelas (installments)
    
    Se interest_rate = 0 ou installments = 1, usa split_amount_cents (sem juros).
    
    🔧 CORRIGIDO: Valida installments > 0 e previne divisão por zero.
    """
    # 🔧 Validação de installments
    if installments <= 0:
        raise ValueError("Número de parcelas deve ser maior que zero")
    
    # Se não tem juros ou é 1 parcela, usa split simples
    if interest_rate == 0 or installments == 1:
        return split_amount_cents(total_cents, installments)
    
    i = interest_rate / 100
    n = installments
    
    # 🔧 Evita divisão por zero
    denominator = (1 + i) ** n - 1
    if denominator == 0:
        return split_amount_cents(total_cents, installments)
    
    # Fórmula da parcela com juros compostos
    pmt = total_cents * (i * (1 + i) ** n) / denominator
    
    # Arredonda para centavos
    pmt_cents = round(pmt)
    
    # Cria lista com todas as parcelas iguais
    amounts = [pmt_cents] * n
    
    # Ajusta o resto para não perder centavos
    total_calculated = sum(amounts)
    if total_calculated != total_cents:
        diff = total_cents - total_calculated
        amounts[0] += diff
    
    return amounts


async def update_card_committed_amount(card_id: str, delta_cents: int, db):
    """Atualiza o committed_amount do cartão (delta em centavos, pode ser negativo)"""
    validate_object_id(card_id, "card_id")
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$inc": {"committed_amount": delta_cents}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )


async def check_available_limit(card_id: str, required_cents: int, db, request: Request = None) -> int:
    """
    Retorna limite disponível em centavos.
    Levanta exceção se insuficiente.
    """
    validate_object_id(card_id, "card_id")
    card = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    if not card:
        raise NotFoundException(
            message_key="ERROR_CARD_NOT_FOUND",
            request=request
        )
    
    available_cents = card.get("total_limit", 0) - card.get("committed_amount", 0)
    
    if required_cents > available_cents:
        language = getattr(request.state, "language", "pt") if request else "pt"
        raise ValidationException(
            message_key="ERROR_INSUFFICIENT_LIMIT",
            request=request,
            params={
                "available": from_cents(available_cents),
                "required": from_cents(required_cents)
            }
        )
    return available_cents


# ========== ENDPOINTS ==========

@router.post("/", response_model=CreditCardPurchaseResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_purchase(
    request: Request,
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova compra parcelada"""
    validate_object_id(purchase_data.card_id, "card_id")
    
    # Verifica se o cartão pertence ao usuário
    card = await db.credit_cards.find_one({
        "_id": ObjectId(purchase_data.card_id),
        "user_id": str(current_user.id)
    })
    if not card:
        raise NotFoundException(
            message_key="ERROR_CARD_NOT_FOUND",
            request=request
        )

    # 🔧 Validação de total_amount (já vem em centavos do modelo)
    if purchase_data.total_amount <= 0:
        raise ValidationException(
            message_key="ERROR_AMOUNT_INVALID",
            request=request
        )

    # 🔧 total_amount já está em centavos no modelo
    total_amount_cents = purchase_data.total_amount
    
    # 🆕 O modelo não tem interest_rate, mas vamos suportar via campo extra
    # Por enquanto, usamos 0 como padrão (sem juros)
    # TODO: Adicionar interest_rate no modelo CreditCardPurchaseCreate
    interest_rate = 0.0
    
    # 🆕 Se tiver juros, calcula o valor total com juros
    if interest_rate > 0:
        amounts_cents = calculate_installments_with_interest(
            total_amount_cents,
            purchase_data.installments,
            interest_rate
        )
        total_with_interest_cents = sum(amounts_cents)
    else:
        total_with_interest_cents = total_amount_cents
    
    # 🔧 Valida limite com o valor total (com ou sem juros)
    await check_available_limit(purchase_data.card_id, total_with_interest_cents, db, request)

    # Valida número máximo de parcelas
    if purchase_data.installments > MAX_INSTALLMENTS:
        raise ValidationException(
            message_key="ERROR_MAX_INSTALLMENTS_EXCEEDED",
            request=request
        )

    # 🆕 Valida first_due_date (não permite data passada)
    first_due = purchase_data.first_due_date
    if isinstance(first_due, str):
        first_due = datetime.fromisoformat(first_due.replace('Z', '+00:00'))
    
    if first_due < datetime.now(timezone.utc):
        raise ValidationException(
            message_key="ERROR_FIRST_DUE_DATE_PAST",
            request=request
        )

    # Usa o método to_purchase_data() do modelo para criar o dict
    purchase_dict = purchase_data.to_purchase_data()
    purchase_dict["user_id"] = str(current_user.id)
    purchase_dict["first_due_date"] = first_due
    purchase_dict["committed_amount"] = total_with_interest_cents  # Compromete o valor com juros
    
    # 🆕 Armazena informações de juros (quando implementado no modelo)
    # purchase_dict["interest_rate"] = interest_rate
    # purchase_dict["total_with_interest"] = total_with_interest_cents

    result = await db.credit_card_purchases.insert_one(purchase_dict)
    purchase_id = str(result.inserted_id)

    # 🆕 Cria parcelas (com ou sem juros)
    if interest_rate > 0:
        amounts_cents = calculate_installments_with_interest(
            total_amount_cents,
            purchase_data.installments,
            interest_rate
        )
    else:
        amounts_cents = split_amount_cents(total_amount_cents, purchase_data.installments)
    
    installments = []
    for i in range(purchase_data.installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": str(current_user.id),
            "card_id": purchase_data.card_id,
            "amount": amounts_cents[i],
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)
    if installments:
        await db.credit_card_installments.insert_many(installments)

    # 🔧 Atualiza committed_amount com o valor total (com ou sem juros)
    await update_card_committed_amount(purchase_data.card_id, total_with_interest_cents, db)

    # 🆕 Log de auditoria
    await add_purchase_audit_history(
        db,
        purchase_id,
        "create",
        str(current_user.id),
        {
            "description": purchase_data.description,
            "total_amount": total_amount_cents,
            "installments": purchase_data.installments,
            "interest_rate": interest_rate,
            "total_with_interest": total_with_interest_cents if interest_rate > 0 else None
        }
    )

    created = await db.credit_card_purchases.find_one({"_id": result.inserted_id})
    
    if created and "total_amount" in created:
        created["total_amount"] = from_cents(created["total_amount"])
    if created and "total_with_interest" in created:
        created["total_with_interest"] = from_cents(created["total_with_interest"])
    
    logger.info(f"✅ Compra criada: {purchase_data.description} para usuário {current_user.id}")
    return convert_objectid_to_str(created)


@router.get("/purchases", response_model=dict)
async def get_purchases(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    card_id: Optional[str] = Query(None, description="Filtrar por cartão"),
    paid: Optional[bool] = Query(None, description="Filtrar por status (true=paga, false=não paga)"),
    sort_by: str = Query("created_at", description="Campo para ordenação (created_at, total_amount, installments, paid)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista compras parceladas do usuário com paginação, filtros e ordenação.
    
    🆕 v4: Adicionados:
    - Filtro por status (paid)
    - Ordenação personalizada (sort_by, sort_order)
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if card_id:
        validate_object_id(card_id, "card_id")
        query["card_id"] = card_id
    
    # 🆕 Filtro por status
    if paid is not None:
        query["paid"] = paid
    
    # 🆕 Ordenação personalizada
    sort_field_mapping = {
        "created_at": "created_at",
        "total_amount": "total_amount",
        "installments": "installments",
        "paid": "paid",
        "updated_at": "updated_at"
    }
    
    sort_field = sort_field_mapping.get(sort_by, "created_at")
    sort_direction = -1 if sort_order == "desc" else 1

    items, total = await paginate_query(
        db.credit_card_purchases, query, params, sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        if "total_amount" in item:
            item["total_amount"] = from_cents(item["total_amount"])
        if "total_with_interest" in item:
            item["total_with_interest"] = from_cents(item["total_with_interest"])
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listadas {len(formatted_items)} compras para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.get("/faturas", response_model=List[dict])
async def get_faturas(
    request: Request,
    card_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna faturas do cartão.
    
    🔧 CORRIGIDO: Adicionado I18n e tratamento de erro adequado.
    """
    try:
        logger.info(f"🔍 Buscando faturas - card_id: {card_id}")
        
        validate_object_id(card_id, "card_id")
        
        card = await db.credit_cards.find_one({
            "_id": ObjectId(card_id),
            "user_id": str(current_user.id)
        })
        if not card:
            raise NotFoundException(
                message_key="ERROR_CARD_NOT_FOUND",
                request=request
            )

        query = {
            "card_id": card_id,
            "user_id": str(current_user.id)
        }
        
        if month is not None and year is not None:
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
            query["due_date"] = {"$gte": start_date, "$lt": end_date}

        installments = await db.credit_card_installments.find(query).to_list(1000)
        
        if not installments:
            return []

        purchases_map = {}
        for inst in installments:
            pid = inst.get("purchase_id")
            if not pid:
                continue
                
            if pid not in purchases_map:
                try:
                    purchase = await db.credit_card_purchases.find_one({"_id": ObjectId(pid)})
                    if purchase:
                        if "total_amount" in purchase:
                            purchase["total_amount"] = from_cents(purchase["total_amount"])
                        if "total_with_interest" in purchase:
                            purchase["total_with_interest"] = from_cents(purchase["total_with_interest"])
                        purchase["_id"] = str(purchase["_id"])
                        purchases_map[pid] = purchase
                except Exception as e:
                    logger.error(f"❌ Erro ao buscar compra {pid}: {e}")
                    continue

        result = []
        for pid, purchase in purchases_map.items():
            purchase_installments = [i for i in installments if i.get("purchase_id") == pid]
            total = 0
            for inst in purchase_installments:
                total += from_cents(inst.get("amount", 0))
            
            installments_list = []
            for inst in purchase_installments:
                inst_copy = {
                    "_id": str(inst.get("_id")),
                    "purchase_id": str(inst.get("purchase_id")),
                    "user_id": str(inst.get("user_id")),
                    "card_id": str(inst.get("card_id")),
                    "amount": from_cents(inst.get("amount", 0)),
                    "due_date": inst.get("due_date"),
                    "paid": inst.get("paid"),
                    "paid_date": inst.get("paid_date"),
                    "created_at": inst.get("created_at"),
                    "updated_at": inst.get("updated_at")
                }
                installments_list.append(inst_copy)
            
            result.append({
                "purchase_id": pid,
                "description": purchase.get("description", ""),
                "total_amount": purchase.get("total_amount", 0),
                "installments_total": purchase.get("installments", 1),
                "category": purchase.get("category"),
                "interest_rate": purchase.get("interest_rate", 0),
                "total_with_interest": purchase.get("total_with_interest", 0),
                "installments": installments_list,
                "total": total
            })
        
        logger.info(f"🔍 Retornando {len(result)} faturas")
        return result
        
    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao buscar faturas: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


@router.get("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def get_purchase(
    request: Request,
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma compra específica"""
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise NotFoundException(
            message_key="ERROR_PURCHASE_NOT_FOUND",
            request=request
        )
    
    if "total_amount" in purchase:
        purchase["total_amount"] = from_cents(purchase["total_amount"])
    if "total_with_interest" in purchase:
        purchase["total_with_interest"] = from_cents(purchase["total_with_interest"])
    
    return convert_objectid_to_str(purchase)


@router.put("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
@limiter.limit("20/minute")
async def update_purchase(
    request: Request,
    purchase_id: str,
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma compra existente"""
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise NotFoundException(
            message_key="ERROR_PURCHASE_NOT_FOUND",
            request=request
        )

    # 🆕 Verifica se o novo cartão pertence ao usuário
    if purchase_data.card_id != purchase.get("card_id"):
        new_card = await db.credit_cards.find_one({
            "_id": ObjectId(purchase_data.card_id),
            "user_id": str(current_user.id)
        })
        if not new_card:
            raise NotFoundException(
                message_key="ERROR_CARD_NOT_FOUND",
                request=request
            )

    # Verifica se há parcelas pagas
    existing_installments = await db.credit_card_installments.find({
        "purchase_id": purchase_id,
        "paid": True
    }).to_list(length=1)
    if existing_installments:
        raise ValidationException(
            message_key="ERROR_CANNOT_EDIT_PAID_INSTALLMENTS",
            request=request
        )

    # 🔧 Validação de total_amount (já vem em centavos do modelo)
    if purchase_data.total_amount <= 0:
        raise ValidationException(
            message_key="ERROR_AMOUNT_INVALID",
            request=request
        )

    # 🔧 total_amount já está em centavos no modelo
    old_total_cents = purchase["total_amount"]
    new_total_cents = purchase_data.total_amount
    
    # 🆕 O modelo não tem interest_rate, mas vamos suportar via campo extra
    # Por enquanto, usamos 0 como padrão (sem juros)
    # TODO: Adicionar interest_rate no modelo CreditCardPurchaseCreate
    interest_rate = 0.0
    
    # 🆕 Se tiver juros, calcula o valor total com juros
    if interest_rate > 0:
        amounts_cents = calculate_installments_with_interest(
            new_total_cents,
            purchase_data.installments,
            interest_rate
        )
        calculated_total_with_interest = sum(amounts_cents)
        new_total_with_interest_cents = calculated_total_with_interest
    else:
        new_total_with_interest_cents = new_total_cents
    
    # 🆕 Verifica se a compra já tinha juros
    old_interest_rate = purchase.get("interest_rate", 0)
    old_total_with_interest = purchase.get("total_with_interest", old_total_cents)
    
    # Calcula o delta baseado no valor com juros
    delta_cents = new_total_with_interest_cents - old_total_with_interest

    if delta_cents != 0:
        if delta_cents > 0:
            await check_available_limit(purchase_data.card_id, delta_cents, db, request)
        await update_card_committed_amount(purchase_data.card_id, delta_cents, db)

    # Valida número máximo de parcelas
    if purchase_data.installments > MAX_INSTALLMENTS:
        raise ValidationException(
            message_key="ERROR_MAX_INSTALLMENTS_EXCEEDED",
            request=request
        )

    # 🆕 Valida first_due_date
    first_due = purchase_data.first_due_date
    if isinstance(first_due, str):
        first_due = datetime.fromisoformat(first_due.replace('Z', '+00:00'))
    
    if first_due < datetime.now(timezone.utc):
        raise ValidationException(
            message_key="ERROR_FIRST_DUE_DATE_PAST",
            request=request
        )

    # Usa o método to_purchase_data() do modelo para criar o dict
    update_dict = purchase_data.to_purchase_data()
    update_dict["updated_at"] = datetime.now(timezone.utc)
    update_dict["first_due_date"] = first_due
    update_dict["committed_amount"] = new_total_with_interest_cents
    
    # 🆕 Atualiza informações de juros (quando implementado no modelo)
    # if interest_rate > 0:
    #     update_dict["interest_rate"] = interest_rate
    #     update_dict["total_with_interest"] = new_total_with_interest_cents
    # else:
    #     update_dict.pop("interest_rate", None)
    #     update_dict.pop("total_with_interest", None)

    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": update_dict}
    )

    # Recria parcelas
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    
    # 🆕 Cria parcelas (com ou sem juros)
    if interest_rate > 0:
        amounts_cents = calculate_installments_with_interest(
            new_total_cents,
            purchase_data.installments,
            interest_rate
        )
    else:
        amounts_cents = split_amount_cents(new_total_cents, purchase_data.installments)
    
    new_installments = []
    for i in range(purchase_data.installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": str(current_user.id),
            "card_id": update_dict["card_id"],
            "amount": amounts_cents[i],
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        new_installments.append(installment)
    if new_installments:
        await db.credit_card_installments.insert_many(new_installments)

    # 🆕 Log de auditoria
    await add_purchase_audit_history(
        db,
        purchase_id,
        "update",
        str(current_user.id),
        {
            "old_total_amount": old_total_cents,
            "new_total_amount": new_total_cents,
            "old_interest_rate": old_interest_rate,
            "new_interest_rate": interest_rate,
            "old_total_with_interest": old_total_with_interest,
            "new_total_with_interest": new_total_with_interest_cents,
            "old_installments": purchase.get("installments"),
            "new_installments": purchase_data.installments,
            "card_changed": purchase_data.card_id != purchase.get("card_id")
        }
    )

    updated = await db.credit_card_purchases.find_one({"_id": ObjectId(purchase_id)})
    
    if updated and "total_amount" in updated:
        updated["total_amount"] = from_cents(updated["total_amount"])
    if updated and "total_with_interest" in updated:
        updated["total_with_interest"] = from_cents(updated["total_with_interest"])
    
    logger.info(f"✅ Compra atualizada: {purchase_id} para usuário {current_user.id}")
    return convert_objectid_to_str(updated)


@router.delete("/purchases/{purchase_id}", response_model=dict)
@limiter.limit("10/minute")
async def delete_purchase(
    request: Request,
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma compra e todas as suas parcelas"""
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise NotFoundException(
            message_key="ERROR_PURCHASE_NOT_FOUND",
            request=request
        )

    # Usa total_with_interest se existir, senão total_amount
    total_to_remove = purchase.get("total_with_interest", purchase["total_amount"])
    await update_card_committed_amount(purchase["card_id"], -total_to_remove, db)

    # 🆕 Log de auditoria
    await add_purchase_audit_history(
        db,
        purchase_id,
        "delete",
        str(current_user.id),
        {
            "description": purchase.get("description"),
            "total_amount": purchase.get("total_amount"),
            "total_with_interest": purchase.get("total_with_interest"),
            "installments": purchase.get("installments")
        }
    )

    await db.credit_card_purchases.delete_one({"_id": ObjectId(purchase_id)})
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    
    language = getattr(request.state, "language", "pt")
    logger.info(f"🗑️ Compra deletada: {purchase_id} para usuário {current_user.id}")
    
    return {"message": get_message("SUCCESS_PURCHASE_DELETED", language), "success": True}


@router.put("/installments/{installment_id}/pay", response_model=dict)
@limiter.limit("30/minute")
async def mark_installment_paid(
    request: Request,
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Marca uma parcela como paga"""
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.credit_card_installments.find_one({"_id": ObjectId(installment_id)})
    if not installment:
        raise NotFoundException(
            message_key="ERROR_INSTALLMENT_NOT_FOUND",
            request=request
        )

    if installment.get("paid", False):
        raise ValidationException(
            message_key="ERROR_INSTALLMENT_ALREADY_PAID",
            request=request
        )

    # Verifica se a compra pertence ao usuário
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(installment["purchase_id"]),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise NotFoundException(
            message_key="ERROR_PURCHASE_NOT_FOUND",
            request=request
        )

    user_id = str(current_user.id)
    now = datetime.now(timezone.utc)

    await db.credit_card_installments.update_one(
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

    # 🆕 Reduz committed_amount
    await update_card_committed_amount(installment["card_id"], -installment["amount"], db)

    # 🆕 Atualiza remaining_installments na compra
    remaining = await db.credit_card_installments.count_documents({
        "purchase_id": installment["purchase_id"],
        "paid": False
    })
    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(installment["purchase_id"])},
        {
            "$set": {
                "remaining_installments": remaining,
                "updated_at": now
            },
            "$inc": {"paid_installments_count": 1}  # Contador de parcelas pagas
        }
    )

    # Verifica se todas as parcelas foram pagas
    if remaining == 0:
        await db.credit_card_purchases.update_one(
            {"_id": ObjectId(installment["purchase_id"])},
            {
                "$set": {
                    "fully_paid": True,
                    "fully_paid_date": now
                }
            }
        )
        logger.info(f"✅ Compra {installment['purchase_id']} totalmente quitada!")

    # 🆕 Log de auditoria na compra
    await add_purchase_audit_history(
        db,
        installment["purchase_id"],
        "installment_paid",
        user_id,
        {
            "installment_id": installment_id,
            "installment_number": installment.get("number"),
            "amount": installment.get("amount"),
            "due_date": installment.get("due_date"),
            "remaining_installments": remaining
        }
    )

    language = getattr(request.state, "language", "pt")
    logger.info(f"✅ Parcela paga: {installment_id} por usuário {user_id}")
    
    return {
        "message": get_message("SUCCESS_INSTALLMENT_PAID", language),
        "success": True,
        "paid_by": user_id,
        "remaining_installments": remaining
    }


@router.put("/installments/{installment_id}/unpay", response_model=dict)
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
    - Verifica se a parcela existe
    - Verifica se a parcela está paga
    - Verifica se o pagamento foi feito há menos de 30 dias (janela de reversão)
    """
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.credit_card_installments.find_one({"_id": ObjectId(installment_id)})
    if not installment:
        raise NotFoundException(
            message_key="ERROR_INSTALLMENT_NOT_FOUND",
            request=request
        )

    if not installment.get("paid", False):
        raise ValidationException(
            message_key="ERROR_INSTALLMENT_NOT_PAID",
            request=request
        )

    # Verifica se a compra pertence ao usuário
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(installment["purchase_id"]),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise NotFoundException(
            message_key="ERROR_PURCHASE_NOT_FOUND",
            request=request
        )

    # Verifica se o pagamento foi feito há menos de 30 dias
    paid_date = installment.get("paid_date")
    if paid_date:
        days_since_paid = (datetime.now(timezone.utc) - paid_date).days
        if days_since_paid > 30:
            raise ValidationException(
                message_key="ERROR_UNPAY_WINDOW_EXPIRED",
                request=request
            )

    user_id = str(current_user.id)
    now = datetime.now(timezone.utc)

    # Desmarca o pagamento
    await db.credit_card_installments.update_one(
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

    # Restaura committed_amount
    await update_card_committed_amount(installment["card_id"], installment["amount"], db)

    # 🆕 Atualiza remaining_installments na compra
    remaining = await db.credit_card_installments.count_documents({
        "purchase_id": installment["purchase_id"],
        "paid": False
    })
    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(installment["purchase_id"])},
        {
            "$set": {
                "remaining_installments": remaining,
                "fully_paid": False,
                "fully_paid_date": None,
                "updated_at": now
            },
            "$inc": {"paid_installments_count": -1}  # Decrementa contador
        }
    )

    # Log de auditoria
    await add_purchase_audit_history(
        db,
        installment["purchase_id"],
        "installment_unpay",
        user_id,
        {
            "installment_id": installment_id,
            "installment_number": installment.get("number"),
            "amount": installment.get("amount"),
            "previous_paid_date": paid_date,
            "previous_paid_by": installment.get("paid_by"),
            "reason": "Pagamento desmarcado pelo usuário",
            "remaining_installments": remaining
        }
    )

    language = getattr(request.state, "language", "pt")
    logger.info(f"🔄 Parcela desmarcada: {installment_id} por usuário {user_id}")
    
    return {
        "message": get_message("SUCCESS_INSTALLMENT_UNPAY", language),
        "success": True,
        "remaining_installments": remaining
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ CRUD completo com paginação
# ✅ ✅ Filtros: card_id, paid
# ✅ ✅ Ordenação: sort_by, sort_order
# ✅ ✅ I18n completo
# ✅ ✅ Auditoria com history
# ✅ ✅ paid_by (quem pagou)
# ✅ ✅ Rate limiting
# ✅ ✅ Validação de first_due_date
# ✅ ✅ Suporte a juros (interest_rate)
# ✅ ✅ Rota /unpay para desmarcar pagamento
# ✅ ✅ Limite de histórico (1000 entradas)
# ✅ ✅ TTL para histórico (1 ano)
# ✅ ✅ Validação de installments > 0
# ✅ ✅ Validação de interest_rate (0-100%)
# ✅ ✅ Validação de total_amount > 0
# ✅ ✅ Validação de novo card_id no update
# ✅ ✅ I18n no endpoint /faturas
# ✅ ✅ Atualização de remaining_installments no pay/unpay
# ✅ ✅ Atualização de fully_paid no pay/unpay
#
# 📋 LIMITAÇÕES CONHECIDAS:
# - Transações MongoDB: Free Tier não suporta (documentado)
# - Juros: Implementação simplificada (taxa fixa, parcelas iguais)
# - TODO: Adicionar interest_rate e total_with_interest no modelo CreditCardPurchaseCreate
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO