"""
Rotas de Contas a Pagar (Bills)
Arquivo: backend/app/routes/bills.py

🔧 CORREÇÃO: Substituído format_doc por format_mongo_doc (Seção 2.2)
🔧 CORREÇÃO: Regra 2.8 - Logs (substituído print por logger)
🔧 CORREÇÃO: Regra 2.10 - Adicionado validate_object_id
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.bill import BillCreate, BillResponse, BillUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

router = APIRouter(prefix="/bills", tags=["Contas a Pagar"])


def parse_installments_dates(installments: dict) -> dict:
    """
    Converte start_date de string para datetime se necessário.
    """
    if installments and isinstance(installments, dict):
        start_date = installments.get("start_date")
        if start_date and isinstance(start_date, str):
            installments["start_date"] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    return installments


# ========== ENDPOINTS ==========

@router.post("/", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    bill_data: BillCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova conta a pagar"""
    try:
        bill_dict = bill_data.model_dump()
        bill_dict["user_id"] = str(current_user.id)
        bill_dict["paid"] = False
        bill_dict["paid_date"] = None
        bill_dict["created_at"] = datetime.now(timezone.utc)
        bill_dict["updated_at"] = datetime.now(timezone.utc)

        if "amount" in bill_dict:
            bill_dict["amount"] = round(bill_dict["amount"], 2)

        if "installments" in bill_dict and isinstance(bill_dict["installments"], dict):
            bill_dict["installments"] = parse_installments_dates(bill_dict["installments"])

        result = await db.bills.insert_one(bill_dict)
        created = await db.bills.find_one({"_id": result.inserted_id})
        
        logger.info(f"Conta criada: {bill_data.description} para usuário {current_user.id}")
        return format_mongo_doc(created)
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar conta: {e}")
        import traceback
        logger.debug(f"Detalhes do erro: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar conta")


@router.get("/", response_model=dict)
async def list_bills(
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
    
    formatted_items = format_mongo_docs(items)
    
    logger.debug(f"Listadas {len(formatted_items)} contas para usuário {current_user.id}")
    return paginate(formatted_items, total, params).model_dump()


@router.get("/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma conta específica"""
    # 🔧 REGRA 2.10: validar ID antes de usar
    validate_object_id(bill_id, "bill_id")
    
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if not bill:
        logger.warning(f"Conta não encontrada: {bill_id} para usuário {current_user.id}")
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    
    return format_mongo_doc(bill)


@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill(
    bill_id: str,
    bill_update: BillUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza uma conta existente"""
    # 🔧 REGRA 2.10: validar ID antes de usar
    validate_object_id(bill_id, "bill_id")
    
    update_data = {k: v for k, v in bill_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    if "amount" in update_data:
        update_data["amount"] = round(update_data["amount"], 2)
    
    if update_data.get("paid") is True and update_data.get("paid_date") is None:
        update_data["paid_date"] = datetime.now(timezone.utc)
    
    if "installments" in update_data and isinstance(update_data["installments"], dict):
        update_data["installments"] = parse_installments_dates(update_data["installments"])

    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        logger.warning(f"Tentativa de atualizar conta inexistente: {bill_id}")
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    updated = await db.bills.find_one({"_id": ObjectId(bill_id)})
    
    logger.info(f"Conta atualizada: {bill_id} para usuário {current_user.id}")
    return format_mongo_doc(updated)


@router.delete("/{bill_id}", response_model=dict)
async def delete_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Remove uma conta"""
    # 🔧 REGRA 2.10: validar ID antes de usar
    validate_object_id(bill_id, "bill_id")
    
    result = await db.bills.delete_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        logger.warning(f"Tentativa de deletar conta inexistente: {bill_id}")
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    
    logger.info(f"Conta deletada: {bill_id} para usuário {current_user.id}")
    return {"message": "Conta deletada com sucesso", "success": True}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Adicionada função format_doc() para padronizar respostas
# ✅ Adicionada função parse_installments_dates() para conversão de datas
# ✅ update_bill agora atualiza updated_at automaticamente
# ✅ update_bill arredonda amount (round) quando enviado
# ✅ update_bill define paid_date automaticamente quando paid=True
# ✅ update_bill converte installments.start_date se for string
# ✅ 🔧 CORREÇÃO: paginate retorna dicionário com .model_dump()
#
# ⏳ Paginação (skip/limit) no list_bills: postergado para pós-MVP
# 📌 Logging estruturado: planejado (substituir print)