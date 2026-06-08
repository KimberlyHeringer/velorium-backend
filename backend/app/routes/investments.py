"""
Rotas de Investimentos
Arquivo: backend/app/routes/investments.py

🔧 CORRIGIDO:
- Usa schemas Pydantic do model investment.py (InvestmentCreate, InvestmentUpdate, InvestmentResponse)
- Adicionados campos faltantes (broker, purchase_price_per_unit, current_price_per_unit, etc.)
- Trata quantity como inteiro (centésimos)
- Adicionado endpoint /{investment_id}/sell para marcar como vendido
- Adicionado endpoint /{investment_id}/update-price para atualizar preço atual
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
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
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/investments", tags=["Investimentos"])


# ========== CONSTANTES ==========
VALID_CATEGORIES = ["renda_fixa", "acoes", "fiis", "cripto", "outros"]


# ========== FUNÇÕES AUXILIARES ==========

def prepare_investment_response(investment: dict) -> dict:
    """Prepara o investimento para resposta (converte centavos para reais)"""
    if not investment:
        return investment
    
    if "amount" in investment:
        investment["amount"] = from_cents(investment["amount"])
    if "current_value" in investment and investment["current_value"] is not None:
        investment["current_value"] = from_cents(investment["current_value"])
    if "purchase_price_per_unit" in investment and investment["purchase_price_per_unit"] is not None:
        investment["purchase_price_per_unit"] = from_cents(investment["purchase_price_per_unit"])
    if "current_price_per_unit" in investment and investment["current_price_per_unit"] is not None:
        investment["current_price_per_unit"] = from_cents(investment["current_price_per_unit"])
    if "profit_loss" in investment and investment["profit_loss"] is not None:
        investment["profit_loss"] = from_cents(investment["profit_loss"])
    if "sold_value" in investment and investment["sold_value"] is not None:
        investment["sold_value"] = from_cents(investment["sold_value"])
    if "dividends_received" in investment and investment["dividends_received"] is not None:
        investment["dividends_received"] = from_cents(investment["dividends_received"])
    if "fees" in investment and investment["fees"] is not None:
        investment["fees"] = from_cents(investment["fees"])
    
    # 🔧 Converte quantity de centésimos para float (ex: 150 → 1.5)
    if "quantity" in investment and investment["quantity"] is not None:
        investment["quantity"] = investment["quantity"] / 100
    
    return investment


def prepare_investment_for_db(data: dict) -> dict:
    """Prepara os dados para salvar no banco (converte reais para centavos)"""
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
            # 🔧 Converte quantidade de float para centésimos (ex: 1.5 → 150)
            if isinstance(value, (int, float)):
                result[key] = int(round(value * 100))
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


# ========== ENDPOINTS ==========

@router.post("/", response_model=InvestmentResponse, status_code=status.HTTP_201_CREATED)
async def create_investment(
    investment_data: InvestmentCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria um novo investimento"""
    
    # Valida categoria
    if investment_data.category not in VALID_CATEGORIES:
        logger.warning(f"Tentativa de criar investimento com categoria inválida: {investment_data.category}")
        raise HTTPException(status_code=400, detail=f"Categoria inválida. Use: {VALID_CATEGORIES}")
    
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
    
    logger.info(f"Investimento criado: '{investment_data.name}' para usuário {current_user.id}")
    return format_mongo_doc(created)


@router.get("/", response_model=dict)
async def list_investments(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    sold: Optional[bool] = Query(None, description="Filtrar por vendidos/não vendidos"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista investimentos do usuário com paginação e filtros"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Categoria inválida. Use: {VALID_CATEGORIES}")
        query["category"] = category
    
    if sold is not None:
        query["sold"] = sold

    items, total = await paginate_query(
        db.investments, query, params, sort=[("created_at", -1)]
    )
    
    # 🔧 Converte valores para resposta
    for item in items:
        item = prepare_investment_response(item)
    
    formatted_items = [format_mongo_doc(item) for item in items]
    
    logger.debug(f"Listados {len(formatted_items)} investimentos para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.get("/{investment_id}", response_model=InvestmentResponse)
async def get_investment(
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
        logger.warning(f"Investimento não encontrado: {investment_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    investment = prepare_investment_response(investment)
    
    logger.debug(f"Investimento recuperado: {investment_id} para usuário {current_user.id}")
    return format_mongo_doc(investment)


@router.put("/{investment_id}", response_model=InvestmentResponse)
async def update_investment(
    investment_id: str,
    investment_data: InvestmentUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza um investimento existente"""
    validate_object_id(investment_id, "investment_id")
    
    # Verifica se existe e pertence ao usuário
    existing = await db.investments.find_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if not existing:
        logger.warning(f"Investimento não encontrado para atualização: {investment_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    # Prepara dados para atualização (remove None)
    update_data = {k: v for k, v in investment_data.model_dump(exclude_unset=True).items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    # 🔧 Se estiver marcando como vendido, valida os campos obrigatórios
    if update_data.get("sold") is True:
        if not update_data.get("sold_date"):
            update_data["sold_date"] = datetime.now(timezone.utc)
        if not update_data.get("sold_value") and not existing.get("sold_value"):
            raise HTTPException(status_code=400, detail="Valor de venda é obrigatório ao marcar como vendido")
    
    # 🔧 Se estiver desmarcando como vendido, limpa os campos
    if update_data.get("sold") is False:
        update_data["sold_date"] = None
        update_data["sold_value"] = None
    
    # 🔧 Converte valores monetários para centavos
    update_data = prepare_investment_for_db(update_data)
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.investments.update_one(
        {"_id": ObjectId(investment_id)},
        {"$set": update_data}
    )
    
    updated = await db.investments.find_one({"_id": ObjectId(investment_id)})
    updated = prepare_investment_response(updated)
    
    logger.info(f"Investimento atualizado: {investment_id} para usuário {current_user.id}")
    return format_mongo_doc(updated)


@router.put("/{investment_id}/sell", response_model=InvestmentResponse)
async def sell_investment(
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
        logger.warning(f"Investimento não encontrado para venda: {investment_id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    if existing.get("sold", False):
        raise HTTPException(status_code=400, detail="Investimento já foi vendido")
    
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
    
    logger.info(f"Investimento vendido: {investment_id} por R$ {sold_value:.2f}")
    return format_mongo_doc(updated)


@router.put("/{investment_id}/update-price", response_model=InvestmentResponse)
async def update_investment_price(
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
        logger.warning(f"Investimento não encontrado: {investment_id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    if existing.get("sold", False):
        raise HTTPException(status_code=400, detail="Não é possível atualizar preço de investimento vendido")
    
    quantity = existing.get("quantity", 0)
    if quantity == 0:
        raise HTTPException(status_code=400, detail="Investimento sem quantidade definida")
    
    # 🔧 Converte para centavos
    current_price_cents = to_cents(current_price)
    current_value_cents = (quantity * current_price_cents) // 100
    
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
    
    logger.info(f"Preço atualizado para investimento {investment_id}: R$ {current_price:.2f}")
    return format_mongo_doc(updated)


@router.delete("/{investment_id}", response_model=dict)
async def delete_investment(
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
        logger.warning(f"Investimento não encontrado para deleção: {investment_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    logger.info(f"Investimento deletado: {investment_id} para usuário {current_user.id}")
    return {"message": "Investimento removido com sucesso", "success": True}


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. Usa schemas Pydantic do model investment.py (InvestmentCreate, InvestmentUpdate, InvestmentResponse)
2. Adicionados campos faltantes (broker, purchase_price_per_unit, current_price_per_unit, etc.)
3. Trata quantity como inteiro (centésimos) com conversão automática
4. Adicionado endpoint /{investment_id}/sell para marcar como vendido
5. Adicionado endpoint /{investment_id}/update-price para atualizar preço atual
6. Adicionadas funções auxiliares prepare_investment_response e prepare_investment_for_db
7. Adicionados filtros por categoria e status de venda na listagem

⚠️ PENDÊNCIAS PARA PÓS-MVP:
================================================================================
1. Internacionalização (i18n) de todas as mensagens de erro
2. Adicionar webhook para atualização automática de preços (via API externa)
3. Adicionar campo dividendos recebidos com histórico
4. Adicionar relatório de performance (rentabilidade por período)
5. Adicionar suporte a múltiplas corretoras com importação automática

================================================================================
✅ STATUS: CONSISTENTE COM O MODEL CORRIGIDO (investment.py)
================================================================================
"""