"""
Rotas de Cartões de Crédito
Arquivo: backend/app/routes/credit_cards.py

🔧 CORRIGIDO (v3 - FINAL):
- Alinhada nomenclatura com o model corrigido (total_limit, used_limit, available_limit)
- Removido campo duplicado 'limit'
- Adicionado campo 'available_limit' calculado
- Corrigida validação de redução de limite (considera used_limit + committed_amount)
- Adicionado campo 'available_limit' na resposta

🆕 MELHORIAS ADICIONADAS (v3):
- 🔧 Substituído format_mongo_doc por convert_objectid_to_str (padronização)
- 🆕 I18n completo com I18nHTTPException e get_message()
- 🆕 Adicionado request: Request em todos os endpoints
- 🆕 Adicionado campo updated_by (auditoria de quem alterou)
- 🆕 Adicionado logs de auditoria (history) para cartões
- 🆕 Adicionado rate limiting (create: 30/min, update: 20/min, delete: 10/min)
- 🆕 Adicionado campo is_active (permitir desativar sem deletar)
- 🆕 Adicionado filtro por status (is_active) no GET
- 🆕 Adicionado ordenação personalizada (sort_by, sort_order)
- 🆕 Adicionada rota /recalculate/{card_id} para recalcular limites
- 🆕 Adicionado histórico específico de alterações de limite

🔧 CORREÇÕES DO DESENVOLVEDOR (v3.1):
- 🔧 add_available_limit: Agora cria uma cópia do dicionário (sem efeitos colaterais)
- 🔧 add_available_limit: Adicionado log warning para available_limit negativo
- 🔧 create_credit_card: Validação robusta para to_cents com None
- 🔧 update_credit_card: Validação robusta para to_cents com None
- 🔧 update_credit_card: Validação de closing_day e due_day
- 🔧 get_card_history: Garante que history seja uma lista antes de ordenar

📋 DECISÕES DOCUMENTADAS:
- ✅ Implementado rota para recalcular limites (corrigir inconsistências)
- ✅ Implementado histórico de alterações de limite
- ✅ Implementado logs de auditoria com histórico completo
- ✅ Mantido padrão de i18n em todas as mensagens
- ✅ Usa convert_objectid_to_str em vez de format_mongo_doc
- ✅ Histórico limitado a 1000 entradas por documento (evita 16MB)
- ❌ SEM TTL para histórico de cartões (dados mantidos para análise de longo prazo)
- ❌ Webhook de limite próximo NÃO implementado (app do banco já faz)

📋 LIMITAÇÕES CONHECIDAS:
- Transações MongoDB: O Atlas Free Tier não suporta transações multi-documento.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import os

from app.database import get_database
from app.models.credit_card import CreditCardCreate, CreditCardResponse, CreditCardUpdate
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

router = APIRouter(prefix="/credit-cards", tags=["Cartões de Crédito"])

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

def add_available_limit(card: dict) -> dict:
    """
    🔧 CORRIGIDO: Adiciona o campo available_limit calculado ao cartão.
    Retorna uma cópia do dicionário para evitar efeitos colaterais.
    """
    if not card:
        return card
    
    result = card.copy()
    
    total_limit = result.get("total_limit", 0)
    used_limit = result.get("used_limit", 0)
    committed_amount = result.get("committed_amount", 0)
    
    available = total_limit - used_limit - committed_amount
    
    # 🆕 Log warning se available for negativo
    if available < 0:
        logger.warning(f"⚠️ available_limit negativo: {available} para cartão {result.get('_id', 'desconhecido')}")
    
    result["available_limit"] = max(available, 0)
    
    return result


async def add_card_audit_history(db, card_id: str, action: str, user_id: str, details: dict):
    """
    🆕 Adiciona entrada no histórico de auditoria do cartão.
    
    🔧 Validações completas:
    - Verifica se db é válido
    - Verifica se card_id é um ObjectId válido
    - Limita o histórico a MAX_HISTORY_ENTRIES (evita 16MB)
    - 🔧 SEM TTL: Dados mantidos para análise de longo prazo
    """
    if db is None:
        logger.error("❌ db não pode ser None em add_card_audit_history")
        return
    
    if not card_id:
        logger.error("❌ card_id não pode ser vazio em add_card_audit_history")
        return
    
    try:
        ObjectId(card_id)
    except Exception as e:
        logger.error(f"❌ card_id inválido em add_card_audit_history: {card_id} - {e}")
        return
    
    if not details:
        details = {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    try:
        # 🔧 SEM TTL: Mantém dados para sempre
        # O campo expires_at é mantido para compatibilidade, mas NÃO tem índice TTL
        expires_at = datetime.now(timezone.utc) + timedelta(days=HISTORY_TTL_DAYS)
        
        history_entry = {
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "expires_at": expires_at,  # ← Campo existe mas NÃO tem índice TTL
            "details": details
        }
        
        await db.credit_cards.update_one(
            {"_id": ObjectId(card_id)},
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


async def add_limit_history(db, card_id: str, user_id: str, old_limit: int, new_limit: int, reason: str = None):
    """
    🆕 Adiciona entrada específica no histórico de alterações de limite.
    """
    details = {
        "old_limit": old_limit,
        "new_limit": new_limit,
        "reason": reason or "Atualização manual"
    }
    
    await add_card_audit_history(db, card_id, "limit_change", user_id, details)
    
    logger.info(f"📊 Histórico de limite: {card_id} - {old_limit} → {new_limit}")


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
    
    🆕 v3: Adicionados:
    - Filtro por status (is_active)
    - Ordenação personalizada (sort_by, sort_order)
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

    items, total = await paginate_query(
        db.credit_cards, query, params, sort=[(sort_field, sort_direction)]
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
    """Cria um novo cartão de crédito"""
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
    
    await add_card_audit_history(
        db,
        card_id,
        "create",
        str(current_user.id),
        {
            "name": card_data.name,
            "total_limit": total_limit_cents,
            "closing_day": card_data.closing_day,
            "due_day": card_data.due_day
        }
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
    """Atualiza um cartão existente"""
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
    
    # 🆕 Validação de closing_day
    if "closing_day" in update_data:
        closing_day = update_data["closing_day"]
        if closing_day < 1 or closing_day > 31:
            raise ValidationException(
                message_key="CARD_INVALID_CLOSING_DAY",
                request=request
            )
    
    # 🆕 Validação de due_day
    if "due_day" in update_data:
        due_day = update_data["due_day"]
        if due_day < 1 or due_day > 31:
            raise ValidationException(
                message_key="CARD_INVALID_DUE_DAY",
                request=request
            )
    
    old_limit = card.get("total_limit", 0)
    limit_changed = False
    new_limit = old_limit
    
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
    
    if limit_changed:
        await add_limit_history(
            db,
            card_id,
            str(current_user.id),
            old_limit,
            new_limit,
            "Atualização via PUT"
        )
    
    await add_card_audit_history(
        db,
        card_id,
        "update",
        str(current_user.id),
        {
            "changes": update_data,
            "limit_changed": limit_changed
        }
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
    """Remove um cartão de crédito"""
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
    
    purchases = await db.credit_card_purchases.find_one({"card_id": card_id})
    if purchases:
        logger.warning(f"⚠️ Tentativa de deletar cartão com compras associadas: {card_id}")
        raise ValidationException(
            message_key="ERROR_CARD_HAS_PURCHASES",
            request=request
        )
    
    await add_card_audit_history(
        db,
        card_id,
        "delete",
        str(current_user.id),
        {
            "name": card.get("name"),
            "total_limit": card.get("total_limit")
        }
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
    🆕 Recalcula os limites do cartão baseado nas parcelas.
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
    
    await add_card_audit_history(
        db,
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
        }
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
    🆕 Retorna o histórico de alterações do cartão.
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


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. 🔧 Substituído format_mongo_doc por convert_objectid_to_str
2. 🆕 I18n completo com I18nHTTPException e get_message()
3. 🆕 Adicionado request: Request em todos os endpoints
4. 🆕 Adicionado campo updated_by (auditoria de quem alterou)
5. 🆕 Adicionado logs de auditoria (history) para cartões
6. 🆕 Adicionado rate limiting (create: 30/min, update: 20/min, delete: 10/min)
7. 🆕 Adicionado campo is_active (permitir desativar sem deletar)
8. 🆕 Adicionado filtro por status (is_active) no GET
9. 🆕 Adicionado ordenação personalizada (sort_by, sort_order)
10. 🆕 Adicionada rota /recalculate/{card_id} para recalcular limites
11. 🆕 Adicionado histórico específico de alterações de limite
12. 🆕 Adicionada rota /{card_id}/history para consultar histórico
13. 🔧 add_available_limit: Agora cria uma cópia do dicionário (sem efeitos colaterais)
14. 🔧 add_available_limit: Adicionado log warning para available_limit negativo
15. 🔧 create_credit_card: Validação robusta para to_cents com None
16. 🔧 update_credit_card: Validação robusta para to_cents com None
17. 🔧 update_credit_card: Validação de closing_day e due_day
18. 🔧 get_card_history: Garante que history seja uma lista antes de ordenar
19. 🔧 SEM TTL: Dados de histórico mantidos para análise de longo prazo

📌 CHAVES I18N UTILIZADAS:
   - ERROR_CARD_NOT_FOUND → "Cartão não encontrado"
   - ERROR_CARD_HAS_PURCHASES → "Cartão possui compras associadas..."
   - SUCCESS_CARD_DELETED → "Cartão removido com sucesso"
   - ERROR_CANNOT_REDUCE_LIMIT → "Não é possível reduzir o limite..."
   - SUCCESS_LIMITS_RECALCULATED → "Limites recalculados com sucesso"
   - CARD_INVALID_CLOSING_DAY → "Dia de fechamento inválido"
   - CARD_INVALID_DUE_DAY → "Dia de vencimento inválido"

✅ STATUS: PRONTO PARA PRODUÇÃO
================================================================================
"""