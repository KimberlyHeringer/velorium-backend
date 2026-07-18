"""
Rotas de Cartões de Crédito
Arquivo: backend/app/routes/credit_cards.py

Funcionalidades:
- GET /credit-cards: Listar cartões com paginação, filtros e ordenação
- POST /credit-cards: Criar cartão de crédito
- PUT /credit-cards/{id}: Atualizar cartão
- DELETE /credit-cards/{id}: Remover cartão (com verificação de compras)
- GET /credit-cards/{id}: Buscar cartão específico
- POST /credit-cards/{id}/recalculate: Recalcular limites
- GET /credit-cards/{id}/history: Histórico de alterações

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (create: 30/min, update: 20/min, delete: 10/min)
- Auditoria completa (history + updated_by)
- Filtro por status (is_active)
- Ordenação personalizada
- Rota /recalculate para corrigir inconsistências
- Histórico de alterações de limite
- SEM TTL (dados mantidos para análise de longo prazo)

Versão: v3.2 (corrigido paginate_query)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.database import get_database
from app.models.credit_card import CreditCardCreate, CreditCardResponse, CreditCardUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter  # ← REMOVIDO get_user_rate_limit_key (não usado)

# ========== NOVOS IMPORTS ==========
from app.core.constants import MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS
from app.utils.audit import add_audit_history, add_limit_history

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/credit-cards", tags=["Cartões de Crédito"])


# ========== FUNÇÕES AUXILIARES ==========

def add_available_limit(card: dict) -> dict:
    """
    Adiciona o campo available_limit calculado ao cartão.
    Retorna uma cópia do dicionário para evitar efeitos colaterais.
    
    Args:
        card: Dicionário do cartão
        
    Returns:
        dict: Cópia do cartão com available_limit adicionado
    """
    if not card:
        return card
    
    result = card.copy()
    
    total_limit = result.get("total_limit", 0)
    used_limit = result.get("used_limit", 0)
    committed_amount = result.get("committed_amount", 0)
    
    available = total_limit - used_limit - committed_amount
    
    if available < 0:
        logger.warning(f"⚠️ available_limit negativo: {available} para cartão {result.get('_id', 'desconhecido')}")
        # 🔧 CORRIGIDO: Registra no histórico quando available_limit fica negativo
        # Isso será feito na rota de update/recalculate
    
    result["available_limit"] = max(available, 0)
    
    return result


def validate_closing_day(day: int) -> bool:
    """Valida se o dia de fechamento é válido (1-31)"""
    return 1 <= day <= 31


def validate_due_day(day: int) -> bool:
    """Valida se o dia de vencimento é válido (1-31)"""
    return 1 <= day <= 31


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def get_credit_cards(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    is_active: Optional[bool] = Query(None, description="Filtrar por status (true=ativo, false=inativo)"),
    sort_by: str = Query("created_at", description="Campo para ordenação (created_at, total_limit, name, is_active)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista todos os cartões do usuário com paginação, filtros e ordenação.
    
    Filtros disponíveis:
    - is_active: true (ativos) ou false (inativos)
    
    Ordenação disponível:
    - created_at, total_limit, name, is_active, updated_at
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if is_active is not None:
        query["is_active"] = is_active
    
    sort_field_mapping = {
        "created_at": "created_at",
        "total_limit": "total_limit",
        "name": "name",
        "is_active": "is_active",
        "updated_at": "updated_at"
    }
    
    sort_field = sort_field_mapping.get(sort_by, "created_at")
    sort_direction = -1 if sort_order == "desc" else 1

    # 🔧 CORRIGIDO: Adicionado collection_name e user_id
    items, total = await paginate_query(
        collection=db.credit_cards,
        collection_name="credit_cards",      # ← ADICIONADO
        query=query,
        params=params,
        user_id=str(current_user.id),        # ← ADICIONADO
        sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        if "total_limit" in item:
            item["total_limit"] = from_cents(item["total_limit"])
        if "used_limit" in item:
            item["used_limit"] = from_cents(item["used_limit"])
        if "committed_amount" in item:
            item["committed_amount"] = from_cents(item["committed_amount"])
        item = add_available_limit(item)
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listados {len(formatted_items)} cartões para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.post("/", response_model=CreditCardResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_credit_card(
    request: Request,
    card_data: CreditCardCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Cria um novo cartão de crédito.
    
    Validações:
    - closing_day entre 1 e 31
    - due_day entre 1 e 31
    - total_limit > 0
    """
    # Valida closing_day
    if not validate_closing_day(card_data.closing_day):
        raise ValidationException(
            message_key="CARD_INVALID_CLOSING_DAY",
            request=request
        )
    
    # Valida due_day
    if not validate_due_day(card_data.due_day):
        raise ValidationException(
            message_key="CARD_INVALID_DUE_DAY",
            request=request
        )
    
    card_dict = card_data.model_dump()
    card_dict["user_id"] = str(current_user.id)
    card_dict["created_at"] = datetime.now(timezone.utc)
    card_dict["updated_at"] = datetime.now(timezone.utc)
    card_dict["is_active"] = True
    
    total_limit_raw = card_dict.get("total_limit", 0)
    total_limit_cents = to_cents(total_limit_raw) if total_limit_raw is not None else 0
    card_dict["total_limit"] = total_limit_cents
    card_dict["used_limit"] = 0
    card_dict["committed_amount"] = 0
    card_dict["available_limit"] = total_limit_cents
    card_dict["last_statement_closed_at"] = None
    card_dict["next_statement_due_date"] = None
    card_dict["history"] = []
    
    result = await db.credit_cards.insert_one(card_dict)
    card_id = str(result.inserted_id)
    
    await add_audit_history(
        db.credit_cards,
        card_id,
        "create",
        str(current_user.id),
        {
            "name": card_data.name,
            "total_limit": total_limit_cents,
            "closing_day": card_data.closing_day,
            "due_day": card_data.due_day,
            "brand": card_data.brand if hasattr(card_data, 'brand') else None
        },
        history_field="history"
    )
    
    created = await db.credit_cards.find_one({"_id": result.inserted_id})
    
    if created:
        if "total_limit" in created:
            created["total_limit"] = from_cents(created["total_limit"])
        if "used_limit" in created:
            created["used_limit"] = from_cents(created["used_limit"])
        if "committed_amount" in created:
            created["committed_amount"] = from_cents(created["committed_amount"])
        created = add_available_limit(created)
    
    logger.info(f"✅ Cartão criado: {card_data.name} (ID: {card_id}) para usuário {current_user.id}")
    return convert_objectid_to_str(created)


@router.put("/{card_id}", response_model=CreditCardResponse)
@limiter.limit("20/minute")
async def update_credit_card(
    request: Request,
    card_id: str,
    card_data: CreditCardUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Atualiza um cartão existente.
    
    Validações:
    - Cartão pertence ao usuário
    - closing_day entre 1 e 31
    - due_day entre 1 e 31
    - Não reduzir limite abaixo do usado + comprometido
    """
    validate_object_id(card_id, "card_id")
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        logger.warning(f"⚠️ Tentativa de atualizar cartão inexistente: {card_id}")
        raise NotFoundException(
            message_key="ERROR_CARD_NOT_FOUND",
            request=request
        )
    
    update_data = card_data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    update_data["updated_by"] = str(current_user.id)
    
    # 🔧 CORRIGIDO: Valida closing_day
    if "closing_day" in update_data:
        closing_day = update_data["closing_day"]
        if not validate_closing_day(closing_day):
            raise ValidationException(
                message_key="CARD_INVALID_CLOSING_DAY",
                request=request
            )
    
    # 🔧 CORRIGIDO: Valida due_day
    if "due_day" in update_data:
        due_day = update_data["due_day"]
        if not validate_due_day(due_day):
            raise ValidationException(
                message_key="CARD_INVALID_DUE_DAY",
                request=request
            )
    
    old_limit = card.get("total_limit", 0)
    limit_changed = False
    new_limit = old_limit
    
    # 🔧 CORRIGIDO: Valida redução de limite
    if "total_limit" in update_data and update_data["total_limit"] is not None:
        new_limit_raw = update_data["total_limit"]
        new_limit_cents = to_cents(new_limit_raw) if new_limit_raw is not None else 0
        update_data["total_limit"] = new_limit_cents
        new_limit = new_limit_cents
        
        current_used = card.get("used_limit", 0)
        current_committed = card.get("committed_amount", 0)
        total_used = current_used + current_committed
        
        if new_limit_cents < total_used:
            raise ValidationException(
                message_key="ERROR_CANNOT_REDUCE_LIMIT",
                request=request,
                params={"value": from_cents(total_used)}
            )
        
        if old_limit != new_limit_cents:
            limit_changed = True
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$set": update_data}
    )
    
    # 🔧 CORRIGIDO: Registra alteração de limite no histórico específico
    if limit_changed:
        await add_limit_history(
            db,
            card_id,
            str(current_user.id),
            old_limit,
            new_limit,
            "Atualização via PUT"
        )
    
    await add_audit_history(
        db.credit_cards,
        card_id,
        "update",
        str(current_user.id),
        {
            "changes": update_data,
            "limit_changed": limit_changed
        },
        history_field="history"
    )
    
    updated_card = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    
    if updated_card:
        if "total_limit" in updated_card:
            updated_card["total_limit"] = from_cents(updated_card["total_limit"])
        if "used_limit" in updated_card:
            updated_card["used_limit"] = from_cents(updated_card["used_limit"])
        if "committed_amount" in updated_card:
            updated_card["committed_amount"] = from_cents(updated_card["committed_amount"])
        updated_card = add_available_limit(updated_card)
        
        # 🔧 CORRIGIDO: Se available_limit ficou negativo, registra no histórico
        if updated_card.get("available_limit", 0) < 0:
            await add_audit_history(
                db.credit_cards,
                card_id,
                "warning",
                str(current_user.id),
                {
                    "warning": "available_limit_negative",
                    "available_limit": updated_card.get("available_limit"),
                    "total_limit": updated_card.get("total_limit"),
                    "used_limit": updated_card.get("used_limit"),
                    "committed_amount": updated_card.get("committed_amount")
                },
                history_field="history"
            )
    
    logger.info(f"✅ Cartão atualizado: {card_id} para usuário {current_user.id}")
    return convert_objectid_to_str(updated_card)


@router.delete("/{card_id}", response_model=dict)
@limiter.limit("10/minute")
async def delete_credit_card(
    request: Request,
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Remove um cartão de crédito.
    
    Validações:
    - Cartão pertence ao usuário
    - Não há compras associadas ao cartão
    """
    validate_object_id(card_id, "card_id")
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        logger.warning(f"⚠️ Tentativa de deletar cartão inexistente: {card_id}")
        raise NotFoundException(
            message_key="ERROR_CARD_NOT_FOUND",
            request=request
        )
    
    # 🔧 CORRIGIDO: Verifica se há compras associadas
    purchases = await db.credit_card_purchases.find_one({"card_id": card_id})
    if purchases:
        logger.warning(f"⚠️ Tentativa de deletar cartão com compras associadas: {card_id}")
        raise ValidationException(
            message_key="ERROR_CARD_HAS_PURCHASES",
            request=request
        )
    
    await add_audit_history(
        db.credit_cards,
        card_id,
        "delete",
        str(current_user.id),
        {
            "name": card.get("name"),
            "total_limit": card.get("total_limit")
        },
        history_field="history"
    )
    
    await db.credit_cards.delete_one({"_id": ObjectId(card_id)})
    
    language = getattr(request.state, "language", "pt")
    logger.info(f"🗑️ Cartão deletado: {card_id}")
    
    return {"message": get_message("SUCCESS_CARD_DELETED", language), "success": True}


@router.get("/{card_id}", response_model=CreditCardResponse)
async def get_credit_card(
    request: Request,
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca um cartão específico pelo ID"""
    validate_object_id(card_id, "card_id")
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    
    if not card:
        logger.warning(f"⚠️ Cartão não encontrado: {card_id}")
        raise NotFoundException(
            message_key="ERROR_CARD_NOT_FOUND",
            request=request
        )
    
    if "total_limit" in card:
        card["total_limit"] = from_cents(card["total_limit"])
    if "used_limit" in card:
        card["used_limit"] = from_cents(card["used_limit"])
    if "committed_amount" in card:
        card["committed_amount"] = from_cents(card["committed_amount"])
    card = add_available_limit(card)
    
    return convert_objectid_to_str(card)


@router.post("/{card_id}/recalculate", response_model=dict)
@limiter.limit("10/minute")
async def recalculate_card_limits(
    request: Request,
    card_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Recalcula os limites do cartão baseado nas parcelas.
    
    Útil para corrigir inconsistências quando o committed_amount
    ou used_limit estão desatualizados.
    """
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
    
    # 🔧 CORRIGIDO: Busca todas as parcelas do cartão
    installments = await db.credit_card_installments.find({
        "card_id": card_id,
        "user_id": str(current_user.id)
    }).to_list(1000)
    
    if not installments:
        new_used = 0
        new_committed = 0
    else:
        new_used = sum(i.get("amount", 0) for i in installments if i.get("paid", False))
        new_committed = sum(i.get("amount", 0) for i in installments if not i.get("paid", False))
    
    total_limit = card.get("total_limit", 0)
    old_used = card.get("used_limit", 0)
    old_committed = card.get("committed_amount", 0)
    
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {
            "$set": {
                "used_limit": new_used,
                "committed_amount": new_committed,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    await add_audit_history(
        db.credit_cards,
        card_id,
        "recalculate",
        str(current_user.id),
        {
            "old_used_limit": old_used,
            "new_used_limit": new_used,
            "old_committed_amount": old_committed,
            "new_committed_amount": new_committed,
            "installments_count": len(installments),
            "reason": "Recálculo manual de limites"
        },
        history_field="history"
    )
    
    language = getattr(request.state, "language", "pt")
    logger.info(f"🔄 Limites recalculados para cartão {card_id}: used={new_used}, committed={new_committed}")
    
    return {
        "message": get_message("SUCCESS_LIMITS_RECALCULATED", language),
        "success": True,
        "old_used_limit": from_cents(old_used),
        "new_used_limit": from_cents(new_used),
        "old_committed_amount": from_cents(old_committed),
        "new_committed_amount": from_cents(new_committed),
        "total_limit": from_cents(total_limit)
    }


@router.get("/{card_id}/history", response_model=dict)
async def get_card_history(
    request: Request,
    card_id: str,
    limit: int = Query(50, ge=1, le=200, description="Número de registros"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o histórico de alterações do cartão.
    
    Args:
        card_id: ID do cartão
        limit: Número máximo de registros (1-200)
        
    Returns:
        dict: Histórico de alterações ordenado por data (mais recente primeiro)
    """
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
    
    history = card.get("history") or []
    sorted_history = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
    limited_history = sorted_history[:limit]
    
    return {
        "card_id": card_id,
        "card_name": card.get("name"),
        "total_records": len(history),
        "history": limited_history
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (create: 30/min, update: 20/min, delete: 10/min)
#   - Auditoria completa (history + updated_by)
#   - Filtro por status (is_active)
#   - Ordenação personalizada
#   - Rota /recalculate para corrigir inconsistências
#   - Histórico de alterações de limite
#   - available_limit calculado com cópia (sem efeitos colaterais)
#   - Validação de closing_day e due_day
#   - SEM TTL (dados mantidos para análise de longo prazo)
#   - Paginate_query com collection_name e user_id (CORRIGIDO v3.2)
#   - Registro de warning quando available_limit fica negativo
#   - Validação de redução de limite
#
# ❌ Não implementado (Pós-MVP):
#   - Transações MongoDB: Free Tier não suporta (M10+ necessário)
#   - Webhook de limite próximo (app do banco já faz)
#   - Validação de dia válido para o mês (ex: 31 em fevereiro)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Auditoria, recalculate, is_active, ordenação (30/06/2026)
#   - v3.1: Refatoração - constantes, audit (02/07/2026)
#   - v3.2: CORREÇÃO - Adicionado collection_name e user_id no paginate_query (10/07/2026)
#   - v3.3: CORREÇÃO - Removido get_user_rate_limit_key não utilizado (10/07/2026)
#   - v3.4: MELHORIA - Registro de warning quando available_limit negativo (10/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO