"""
Rotas de Investimentos
Arquivo: backend/app/routes/investments.py

Funcionalidades:
- POST /investments: Criar investimento
- GET /investments: Listar investimentos com paginação, filtros e ordenação
- GET /investments/{id}: Buscar investimento específico
- PUT /investments/{id}: Atualizar investimento
- PUT /investments/{id}/sell: Marcar investimento como vendido
- PUT /investments/{id}/update-price: Atualizar preço atual
- DELETE /investments/{id}: Remover investimento

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting (create: 30/min, update: 20/min, delete: 10/min, sell: 20/min, update-price: 30/min)
- Validação de quantity > 0 e preços
- Validação de sold_date não futuro
- Decimal para precisão em quantity
- Ordenação personalizada
- SEM history (modo individual)

Versão: v3.2 (refatorado)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.investment import (
    InvestmentCreate, 
    InvestmentUpdate, 
    InvestmentResponse,
    Investment
)
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter

# ========== NOVOS IMPORTS ==========
from app.constants.categories import CATEGORIAS_INVESTIMENTOS
from app.utils.validators_extras import prepare_investment_response, prepare_investment_for_db

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/investments", tags=["Investimentos"])


# ========== ENDPOINTS ==========

@router.post("/", response_model=InvestmentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_investment(
    request: Request,
    investment_data: InvestmentCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria um novo investimento"""
    
    # Valida categoria
    if investment_data.category not in CATEGORIAS_INVESTIMENTOS:
        logger.warning(f"⚠️ Tentativa de criar investimento com categoria inválida: {investment_data.category}")
        raise ValidationException(
            message_key="ERROR_INVALID_CATEGORY",
            request=request,
            params={"categories": ", ".join(CATEGORIAS_INVESTIMENTOS)}
        )
    
    # Valida quantidade
    if investment_data.quantity <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_QUANTITY",
            request=request
        )
    
    # Valida preços
    if investment_data.purchase_price_per_unit <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_PRICE",
            request=request
        )
    
    investment_dict = investment_data.model_dump()
    investment_dict["user_id"] = str(current_user.id)
    investment_dict["created_at"] = datetime.now(timezone.utc)
    investment_dict["updated_at"] = datetime.now(timezone.utc)
    
    investment_dict["current_value"] = None
    investment_dict["current_price_per_unit"] = None
    investment_dict["profit_loss"] = None
    investment_dict["return_percentage"] = None
    investment_dict["dividends_received"] = None
    investment_dict["last_dividend_date"] = None
    investment_dict["sold"] = False
    investment_dict["sold_date"] = None
    investment_dict["sold_value"] = None
    investment_dict["automatic_update"] = investment_data.automatic_update
    
    investment_dict = prepare_investment_for_db(investment_dict)
    
    result = await db.investments.insert_one(investment_dict)
    created = await db.investments.find_one({"_id": result.inserted_id})
    
    created = prepare_investment_response(created)
    
    logger.info(f"✅ Investimento criado: '{investment_data.name}' para usuário {current_user.id}")
    return convert_objectid_to_str(created)


@router.get("/", response_model=dict)
async def list_investments(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    sold: Optional[bool] = Query(None, description="Filtrar por vendidos/não vendidos"),
    sort_by: str = Query("created_at", description="Campo para ordenação (created_at, amount, current_value, return_percentage, name)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista investimentos do usuário com paginação, filtros e ordenação.
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if category:
        if category not in CATEGORIAS_INVESTIMENTOS:
            raise ValidationException(
                message_key="ERROR_INVALID_CATEGORY",
                request=request,
                params={"categories": ", ".join(CATEGORIAS_INVESTIMENTOS)}
            )
        query["category"] = category
    
    if sold is not None:
        query["sold"] = sold
    
    sort_field_mapping = {
        "created_at": "created_at",
        "amount": "amount",
        "current_value": "current_value",
        "return_percentage": "return_percentage",
        "name": "name",
        "updated_at": "updated_at"
    }
    sort_field = sort_field_mapping.get(sort_by, "created_at")
    sort_direction = -1 if sort_order == "desc" else 1

    items, total = await paginate_query(
        db.investments, query, params, sort=[(sort_field, sort_direction)]
    )
    
    for item in items:
        item = prepare_investment_response(item)
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    logger.debug(f"📊 Listados {len(formatted_items)} investimentos para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.get("/{investment_id}", response_model=InvestmentResponse)
async def get_investment(
    request: Request,
    investment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca um investimento específico"""
    validate_object_id(investment_id, "investment_id")
    
    investment = await db.investments.find_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if not investment:
        logger.warning(f"⚠️ Investimento não encontrado: {investment_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_INVESTMENT_NOT_FOUND",
            request=request
        )
    
    investment = prepare_investment_response(investment)
    
    logger.debug(f"📊 Investimento recuperado: {investment_id} para usuário {current_user.id}")
    return convert_objectid_to_str(investment)


@router.put("/{investment_id}", response_model=InvestmentResponse)
@limiter.limit("20/minute")
async def update_investment(
    request: Request,
    investment_id: str,
    investment_data: InvestmentUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza um investimento existente"""
    validate_object_id(investment_id, "investment_id")
    
    existing = await db.investments.find_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if not existing:
        logger.warning(f"⚠️ Investimento não encontrado para atualização: {investment_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_INVESTMENT_NOT_FOUND",
            request=request
        )
    
    update_data = {k: v for k, v in investment_data.model_dump(exclude_unset=True).items() if v is not None}
    
    if not update_data:
        raise ValidationException(
            message_key="ERROR_NO_DATA_TO_UPDATE",
            request=request
        )
    
    if "quantity" in update_data and update_data["quantity"] <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_QUANTITY",
            request=request
        )
    
    if "purchase_price_per_unit" in update_data and update_data["purchase_price_per_unit"] <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_PRICE",
            request=request
        )
    
    if update_data.get("sold") is True:
        if not update_data.get("sold_date"):
            update_data["sold_date"] = datetime.now(timezone.utc)
        if not update_data.get("sold_value") and not existing.get("sold_value"):
            raise ValidationException(
                message_key="ERROR_SOLD_VALUE_REQUIRED",
                request=request
            )
    
    if update_data.get("sold") is False:
        update_data["sold_date"] = None
        update_data["sold_value"] = None
        update_data["profit_loss"] = None
        update_data["return_percentage"] = None
    
    update_data = prepare_investment_for_db(update_data)
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.investments.update_one(
        {"_id": ObjectId(investment_id)},
        {"$set": update_data}
    )
    
    updated = await db.investments.find_one({"_id": ObjectId(investment_id)})
    updated = prepare_investment_response(updated)
    
    logger.info(f"✅ Investimento atualizado: {investment_id} para usuário {current_user.id}")
    return convert_objectid_to_str(updated)


@router.put("/{investment_id}/sell", response_model=InvestmentResponse)
@limiter.limit("20/minute")
async def sell_investment(
    request: Request,
    investment_id: str,
    sold_value: float = Query(..., gt=0, description="Valor da venda em reais"),
    sold_date: Optional[datetime] = Query(None, description="Data da venda"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Marca um investimento como vendido"""
    validate_object_id(investment_id, "investment_id")
    
    existing = await db.investments.find_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if not existing:
        logger.warning(f"⚠️ Investimento não encontrado para venda: {investment_id}")
        raise NotFoundException(
            message_key="ERROR_INVESTMENT_NOT_FOUND",
            request=request
        )
    
    if existing.get("sold", False):
        raise ValidationException(
            message_key="ERROR_INVESTMENT_ALREADY_SOLD",
            request=request
        )
    
    if sold_date and sold_date > datetime.now(timezone.utc):
        raise ValidationException(
            message_key="ERROR_SOLD_DATE_FUTURE",
            request=request
        )
    
    amount_cents = existing.get("amount", 0)
    sold_value_cents = to_cents(sold_value)
    profit_loss_cents = sold_value_cents - amount_cents
    
    update_data = {
        "sold": True,
        "sold_date": sold_date or datetime.now(timezone.utc),
        "sold_value": sold_value_cents,
        "profit_loss": profit_loss_cents,
        "return_percentage": (profit_loss_cents / amount_cents) * 100 if amount_cents > 0 else 0,
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.investments.update_one(
        {"_id": ObjectId(investment_id)},
        {"$set": update_data}
    )
    
    updated = await db.investments.find_one({"_id": ObjectId(investment_id)})
    updated = prepare_investment_response(updated)
    
    logger.info(f"✅ Investimento vendido: {investment_id} por R$ {sold_value:.2f}")
    return convert_objectid_to_str(updated)


@router.put("/{investment_id}/update-price", response_model=InvestmentResponse)
@limiter.limit("30/minute")
async def update_investment_price(
    request: Request,
    investment_id: str,
    current_price: float = Query(..., gt=0, description="Preço atual por unidade em reais"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza o preço atual de um investimento"""
    validate_object_id(investment_id, "investment_id")
    
    existing = await db.investments.find_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if not existing:
        logger.warning(f"⚠️ Investimento não encontrado: {investment_id}")
        raise NotFoundException(
            message_key="ERROR_INVESTMENT_NOT_FOUND",
            request=request
        )
    
    if existing.get("sold", False):
        raise ValidationException(
            message_key="ERROR_CANNOT_UPDATE_SOLD_INVESTMENT",
            request=request
        )
    
    quantity = existing.get("quantity", 0)
    if quantity == 0:
        raise ValidationException(
            message_key="ERROR_QUANTITY_NOT_DEFINED",
            request=request
        )
    
    current_price_cents = to_cents(current_price)
    current_value_cents = int(round((quantity * current_price_cents) / 100))
    
    amount_cents = existing.get("amount", 0)
    profit_loss_cents = current_value_cents - amount_cents
    
    update_data = {
        "current_price_per_unit": current_price_cents,
        "current_value": current_value_cents,
        "profit_loss": profit_loss_cents,
        "return_percentage": (profit_loss_cents / amount_cents) * 100 if amount_cents > 0 else 0,
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.investments.update_one(
        {"_id": ObjectId(investment_id)},
        {"$set": update_data}
    )
    
    updated = await db.investments.find_one({"_id": ObjectId(investment_id)})
    updated = prepare_investment_response(updated)
    
    logger.info(f"✅ Preço atualizado para investimento {investment_id}: R$ {current_price:.2f}")
    return convert_objectid_to_str(updated)


@router.delete("/{investment_id}", response_model=dict)
@limiter.limit("10/minute")
async def delete_investment(
    request: Request,
    investment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove um investimento"""
    validate_object_id(investment_id, "investment_id")
    
    result = await db.investments.delete_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if result.deleted_count == 0:
        logger.warning(f"⚠️ Investimento não encontrado para deleção: {investment_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_INVESTMENT_NOT_FOUND",
            request=request
        )
    
    language = getattr(request.state, "language", "pt")
    logger.info(f"🗑️ Investimento deletado: {investment_id} para usuário {current_user.id}")
    
    return {"message": get_message("SUCCESS_INVESTMENT_DELETED", language), "success": True}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting (create: 30/min, update: 20/min, delete: 10/min, sell: 20/min, update-price: 30/min)
#   - Validação de quantity > 0 e preços
#   - Validação de sold_date não futuro
#   - Decimal para precisão em quantity
#   - Ordenação personalizada
#   - Categorias centralizadas (constants/categories.py)
#   - prepare_investment_response e prepare_investment_for_db centralizados
#   - SEM history (modo individual)
#
# ❌ Não implementado (Pós-MVP):
#   - Webhook automático para preços
#   - Dividendos
#   - Transações MongoDB (Free Tier não suporta)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Rate limiting, validações, ordenação (30/06/2026)
#   - v3.1: Correções de quantity=None, sold_date (01/07/2026)
#   - v3.2: Refatoração - categories, validators_extras (02/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO