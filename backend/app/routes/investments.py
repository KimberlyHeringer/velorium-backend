"""
Rotas de Investimentos
Arquivo: backend/app/routes/investments.py

🔧 CORRIGIDO (v3.2 - FINAL):
- Usa schemas Pydantic do model investment.py (InvestmentCreate, InvestmentUpdate, InvestmentResponse)
- Adicionados campos faltantes (broker, purchase_price_per_unit, current_price_per_unit, etc.)
- Trata quantity como inteiro (centésimos)
- Adicionado endpoint /{investment_id}/sell para marcar como vendido
- Adicionado endpoint /{investment_id}/update-price para atualizar preço atual

🆕 MELHORIAS ADICIONADAS (v3):
- 🔧 Substituído format_mongo_doc por convert_objectid_to_str (padronização)
- 🆕 I18n completo com I18nHTTPException e get_message()
- 🆕 Adicionado request: Request em todos os endpoints
- 🆕 Adicionado rate limiting (create: 30/min, update: 20/min, delete: 10/min, sell: 20/min, update-price: 30/min)
- 🆕 Adicionada validação de quantity > 0 no create
- 🆕 Adicionada validação de preços negativos
- 🆕 Adicionada ordenação personalizada (sort_by, sort_order)

🔧 CORREÇÕES DO DESENVOLVEDOR (v3.1):
- 🔧 CORRIGIDO: prepare_investment_for_db trata quantity=None
- 🆕 Adicionada validação de sold_date não futuro em /sell

🔧 CORREÇÕES DO DESENVOLVEDOR (v3.2):
- 🔧 MELHORADO: prepare_investment_for_db usa Decimal para precisão
- 🔧 ADICIONADO: Import Decimal
- 📋 DECISÃO: Webhook automático e dividendos ficam para Pós-MVP

📋 DECISÕES DOCUMENTADAS:
- ✅ Implementado validação de quantidade e preços
- ✅ Implementado ordenação personalizada
- ✅ Implementado validação de sold_date futuro
- ✅ Implementado Decimal para precisão em quantity
- ✅ Mantido padrão de i18n em todas as mensagens
- ✅ Usa convert_objectid_to_str em vez de format_mongo_doc
- ❌ SEM updated_by (modo individual não precisa)
- ❌ SEM history (modo individual não precisa)
- ❌ SEM webhook de preços (Pós-MVP)
- ❌ SEM dividendos (Pós-MVP)

📋 LIMITAÇÕES CONHECIDAS:
- Transações MongoDB: O Atlas Free Tier não suporta transações multi-documento.
- Atualização de preços: Manual via endpoint /update-price (webhook automático em Pós-MVP)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from decimal import Decimal

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

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/investments", tags=["Investimentos"])


# ========== CONSTANTES ==========
VALID_CATEGORIES = ["renda_fixa", "acoes", "fiis", "cripto", "outros"]


# ========== FUNÇÕES AUXILIARES ==========

def prepare_investment_response(investment: dict) -> dict:
    """Prepara o investimento para resposta (converte centavos para reais)"""
    if not investment:
        return investment
    
    # 🔧 Cria uma cópia para não modificar o original
    result = investment.copy()
    
    if "amount" in result:
        result["amount"] = from_cents(result["amount"])
    if "current_value" in result and result["current_value"] is not None:
        result["current_value"] = from_cents(result["current_value"])
    if "purchase_price_per_unit" in result and result["purchase_price_per_unit"] is not None:
        result["purchase_price_per_unit"] = from_cents(result["purchase_price_per_unit"])
    if "current_price_per_unit" in result and result["current_price_per_unit"] is not None:
        result["current_price_per_unit"] = from_cents(result["current_price_per_unit"])
    if "profit_loss" in result and result["profit_loss"] is not None:
        result["profit_loss"] = from_cents(result["profit_loss"])
    if "sold_value" in result and result["sold_value"] is not None:
        result["sold_value"] = from_cents(result["sold_value"])
    if "dividends_received" in result and result["dividends_received"] is not None:
        result["dividends_received"] = from_cents(result["dividends_received"])
    if "fees" in result and result["fees"] is not None:
        result["fees"] = from_cents(result["fees"])
    
    # 🔧 Converte quantity de centésimos para float (ex: 150 → 1.5)
    if "quantity" in result and result["quantity"] is not None:
        result["quantity"] = result["quantity"] / 100
    
    return result


def prepare_investment_for_db(data: dict) -> dict:
    """
    Prepara os dados para salvar no banco (converte reais para centavos)
    🔧 MELHORADO: Usa Decimal para precisão em quantity
    """
    result = {}
    
    for key, value in data.items():
        if value is None:
            result[key] = None
        elif key in ["amount", "current_value", "purchase_price_per_unit", "current_price_per_unit", 
                     "profit_loss", "sold_value", "dividends_received", "fees"]:
            if isinstance(value, (int, float)):
                result[key] = to_cents(float(value))
            else:
                result[key] = value
        elif key == "quantity":
            # 🔧 MELHORADO: Usa Decimal para evitar problemas de precisão com floats
            if value is None:
                result[key] = None
            elif isinstance(value, (int, float)):
                result[key] = int(Decimal(str(value)) * 100)
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


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
    
    # 🆕 Valida categoria
    if investment_data.category not in VALID_CATEGORIES:
        logger.warning(f"⚠️ Tentativa de criar investimento com categoria inválida: {investment_data.category}")
        raise ValidationException(
            message_key="ERROR_INVALID_CATEGORY",
            request=request,
            params={"categories": ", ".join(VALID_CATEGORIES)}
        )
    
    # 🆕 Valida quantidade
    if investment_data.quantity <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_QUANTITY",
            request=request
        )
    
    # 🆕 Valida preços (não podem ser negativos)
    if investment_data.purchase_price_per_unit <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_PRICE",
            request=request
        )
    
    # Prepara dados para o banco
    investment_dict = investment_data.model_dump()
    investment_dict["user_id"] = str(current_user.id)
    investment_dict["created_at"] = datetime.now(timezone.utc)
    investment_dict["updated_at"] = datetime.now(timezone.utc)
    
    # 🔧 Campos que não vêm do frontend (inicializados com valores padrão)
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
    
    # 🔧 Converte valores monetários para centavos
    investment_dict = prepare_investment_for_db(investment_dict)
    
    result = await db.investments.insert_one(investment_dict)
    created = await db.investments.find_one({"_id": result.inserted_id})
    
    # 🔧 Converte para resposta
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
    
    🆕 v3: Adicionados:
    - Ordenação personalizada (sort_by, sort_order)
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if category:
        if category not in VALID_CATEGORIES:
            raise ValidationException(
                message_key="ERROR_INVALID_CATEGORY",
                request=request,
                params={"categories": ", ".join(VALID_CATEGORIES)}
            )
        query["category"] = category
    
    if sold is not None:
        query["sold"] = sold
    
    # 🆕 Ordenação personalizada
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
    
    # 🔧 Converte valores para resposta
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
    
    # Prepara dados para atualização (remove None)
    update_data = {k: v for k, v in investment_data.model_dump(exclude_unset=True).items() if v is not None}
    
    if not update_data:
        raise ValidationException(
            message_key="ERROR_NO_DATA_TO_UPDATE",
            request=request
        )
    
    # 🆕 Valida quantidade se presente
    if "quantity" in update_data and update_data["quantity"] <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_QUANTITY",
            request=request
        )
    
    # 🆕 Valida preços se presentes
    if "purchase_price_per_unit" in update_data and update_data["purchase_price_per_unit"] <= 0:
        raise ValidationException(
            message_key="ERROR_INVALID_PRICE",
            request=request
        )
    
    # 🔧 Se estiver marcando como vendido, valida os campos obrigatórios
    if update_data.get("sold") is True:
        if not update_data.get("sold_date"):
            update_data["sold_date"] = datetime.now(timezone.utc)
        if not update_data.get("sold_value") and not existing.get("sold_value"):
            raise ValidationException(
                message_key="ERROR_SOLD_VALUE_REQUIRED",
                request=request
            )
    
    # 🔧 Se estiver desmarcando como vendido, limpa os campos
    if update_data.get("sold") is False:
        update_data["sold_date"] = None
        update_data["sold_value"] = None
        update_data["profit_loss"] = None
        update_data["return_percentage"] = None
    
    # 🔧 Converte valores monetários para centavos
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
    
    # 🆕 Valida se sold_date não é futuro
    if sold_date and sold_date > datetime.now(timezone.utc):
        raise ValidationException(
            message_key="ERROR_SOLD_DATE_FUTURE",
            request=request
        )
    
    # 🔧 Calcula lucro/prejuízo
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
    """Atualiza o preço atual de um investimento e recalcula valor atual"""
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
    
    # 🔧 Converte para centavos
    current_price_cents = to_cents(current_price)
    current_value_cents = int(round((quantity * current_price_cents) / 100))
    
    # 🔧 Calcula lucro/prejuízo atual
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


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO (v3.2):
================================================================================
1. 🔧 Substituído format_mongo_doc por convert_objectid_to_str
2. 🆕 I18n completo com I18nHTTPException e get_message()
3. 🆕 Adicionado request: Request em todos os endpoints
4. 🆕 Adicionado rate limiting (create: 30/min, update: 20/min, delete: 10/min, sell: 20/min, update-price: 30/min)
5. 🆕 Adicionada validação de quantity > 0 no create e update
6. 🆕 Adicionada validação de preços negativos
7. 🆕 Adicionada ordenação personalizada (sort_by, sort_order)
8. 🔧 prepare_investment_response agora cria cópia (sem efeitos colaterais)
9. 🔧 CORRIGIDO: prepare_investment_for_db trata quantity=None
10. 🆕 Adicionada validação de sold_date não futuro em /sell
11. 🔧 MELHORADO: prepare_investment_for_db usa Decimal para precisão

📌 CHAVES I18N UTILIZADAS:
   - ERROR_INVALID_CATEGORY → "Categoria inválida. Use: {categories}"
   - ERROR_INVESTMENT_NOT_FOUND → "Investimento não encontrado"
   - ERROR_NO_DATA_TO_UPDATE → "Nenhum dado para atualizar"
   - ERROR_SOLD_VALUE_REQUIRED → "Valor de venda é obrigatório ao marcar como vendido"
   - ERROR_INVESTMENT_ALREADY_SOLD → "Investimento já foi vendido"
   - ERROR_CANNOT_UPDATE_SOLD_INVESTMENT → "Não é possível atualizar preço de investimento vendido"
   - ERROR_QUANTITY_NOT_DEFINED → "Investimento sem quantidade definida"
   - SUCCESS_INVESTMENT_DELETED → "Investimento removido com sucesso"
   - ERROR_INVALID_QUANTITY → "Quantidade inválida. Deve ser maior que zero"
   - ERROR_INVALID_PRICE → "Preço inválido. Deve ser maior que zero"
   - ERROR_SOLD_DATE_FUTURE → "Data de venda não pode ser no futuro"

📋 DECISÕES DOCUMENTADAS:
   - ❌ SEM updated_by (modo individual não precisa)
   - ❌ SEM history (modo individual não precisa)
   - ❌ SEM webhook de preços (Pós-MVP)
   - ❌ SEM dividendos (Pós-MVP)

✅ STATUS: PRONTO PARA PRODUÇÃO
================================================================================
"""