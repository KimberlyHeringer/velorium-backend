"""
Rotas de Investimentos
Arquivo: backend/app/routes/investments.py

✅ CRUD completo (criar, listar, buscar, atualizar, deletar)
✅ Validação inline (sem schemas separados)
✅ 🔧 CORREÇÃO: padronização _id
✅ 🔧 MODIFICADO: Regra 2.8 - Adicionado logger completo
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.investment import Investment
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.validators import format_mongo_doc, validate_object_id
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

router = APIRouter(prefix="/investments", tags=["Investimentos"])


# ========== CRIAÇÃO ==========
@router.post("/", response_model=Investment, status_code=status.HTTP_201_CREATED)
async def create_investment(
    investment_data: dict,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria um novo investimento"""
    # Validação inline
    if not investment_data.get("name"):
        logger.warning(f"Tentativa de criar investimento sem nome para usuário {current_user.id}")
        raise HTTPException(status_code=400, detail="Nome é obrigatório")
    
    if not investment_data.get("amount") or investment_data["amount"] <= 0:
        logger.warning(f"Tentativa de criar investimento com valor inválido para usuário {current_user.id}")
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    valid_categories = ["renda_fixa", "acoes", "fiis", "cripto", "outros"]
    if investment_data.get("category") not in valid_categories:
        logger.warning(f"Tentativa de criar investimento com categoria inválida: {investment_data.get('category')}")
        raise HTTPException(status_code=400, detail=f"Categoria inválida. Use: {valid_categories}")
    
    investment_dict = {
        "user_id": str(current_user.id),
        "name": investment_data["name"],
        "amount": round(float(investment_data["amount"]), 2),
        "category": investment_data["category"],
        "purchase_date": investment_data.get("purchase_date", datetime.now(timezone.utc)),
        "quantity": investment_data.get("quantity"),
        "current_value": investment_data.get("current_value"),
        "notes": investment_data.get("notes"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    result = await db.investments.insert_one(investment_dict)
    created = await db.investments.find_one({"_id": result.inserted_id})
    
    logger.info(f"Investimento criado: '{investment_data['name']}' (R$ {investment_data['amount']}) para usuário {current_user.id}")
    return format_mongo_doc(created)


# ========== LISTAGEM (com paginação) ==========
@router.get("/", response_model=dict)
async def list_investments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Lista investimentos do usuário com paginação"""
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    items, total = await paginate_query(
        db.investments, query, params, sort=[("created_at", -1)]
    )
    
    formatted_items = [format_mongo_doc(item) for item in items]
    
    logger.debug(f"Listados {len(formatted_items)} investimentos para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


# ========== BUSCAR POR ID ==========
@router.get("/{investment_id}", response_model=Investment)
async def get_investment(
    investment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca um investimento específico"""
    validate_object_id(investment_id)
    
    investment = await db.investments.find_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if not investment:
        logger.warning(f"Investimento não encontrado: {investment_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    logger.debug(f"Investimento recuperado: {investment_id} para usuário {current_user.id}")
    return format_mongo_doc(investment)


# ========== ATUALIZAR ==========
@router.put("/{investment_id}", response_model=Investment)
async def update_investment(
    investment_id: str,
    investment_data: dict,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza um investimento existente"""
    validate_object_id(investment_id)
    
    # Verifica se existe e pertence ao usuário
    existing = await db.investments.find_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if not existing:
        logger.warning(f"Investimento não encontrado para atualização: {investment_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    # Prepara dados para atualização
    update_data = {}
    
    if "name" in investment_data:
        update_data["name"] = investment_data["name"]
    if "amount" in investment_data:
        if investment_data["amount"] <= 0:
            logger.warning(f"Tentativa de atualizar investimento com valor inválido: {investment_id}")
            raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
        update_data["amount"] = round(float(investment_data["amount"]), 2)
    if "category" in investment_data:
        valid_categories = ["renda_fixa", "acoes", "fiis", "cripto", "outros"]
        if investment_data["category"] not in valid_categories:
            logger.warning(f"Tentativa de atualizar com categoria inválida: {investment_data.get('category')}")
            raise HTTPException(status_code=400, detail="Categoria inválida")
        update_data["category"] = investment_data["category"]
    if "purchase_date" in investment_data:
        update_data["purchase_date"] = investment_data["purchase_date"]
    if "quantity" in investment_data:
        update_data["quantity"] = investment_data["quantity"]
    if "current_value" in investment_data:
        update_data["current_value"] = investment_data["current_value"]
    if "notes" in investment_data:
        update_data["notes"] = investment_data["notes"]
    
    if not update_data:
        logger.warning(f"Tentativa de atualizar investimento sem dados: {investment_id}")
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.investments.update_one(
        {"_id": ObjectId(investment_id)},
        {"$set": update_data}
    )
    
    updated = await db.investments.find_one({"_id": ObjectId(investment_id)})
    
    logger.info(f"Investimento atualizado: {investment_id} para usuário {current_user.id}")
    return format_mongo_doc(updated)


# ========== DELETAR ==========
@router.delete("/{investment_id}", response_model=dict)
async def delete_investment(
    investment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove um investimento"""
    validate_object_id(investment_id)
    
    result = await db.investments.delete_one({
        "_id": ObjectId(investment_id),
        "user_id": str(current_user.id)
    })
    
    if result.deleted_count == 0:
        logger.warning(f"Investimento não encontrado para deleção: {investment_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Investimento não encontrado")
    
    logger.info(f"Investimento deletado: {investment_id} para usuário {current_user.id}")
    return {"message": "Investimento removido com sucesso", "success": True}