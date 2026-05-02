"""
Rotas de Contas a Pagar (Bills)
Arquivo: backend/app/routes/bills.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.bill import BillCreate, BillResponse, BillUpdate
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/bills", tags=["Contas a Pagar"])


# ========== FUNÇÃO AUXILIAR PARA FORMATAÇÃO ==========

def format_doc(doc: dict) -> dict:
    """
    Converte _id para id e string em documentos do MongoDB.
    Útil para padronizar respostas da API.
    """
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
        doc["id"] = doc["_id"]
    return doc


# ========== FUNÇÃO AUXILIAR PARA CONVERSÃO DE DATAS ==========

def parse_installments_dates(installments: dict) -> dict:
    """
    Converte start_date de string para datetime se necessário.
    Usado na criação e atualização de contas.
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
    try:
        bill_dict = bill_data.model_dump()
        bill_dict["user_id"] = str(current_user.id)
        bill_dict["paid"] = False
        bill_dict["paid_date"] = None
        bill_dict["created_at"] = datetime.now(timezone.utc)
        bill_dict["updated_at"] = datetime.now(timezone.utc)

        # Arredonda amount
        if "amount" in bill_dict:
            bill_dict["amount"] = round(bill_dict["amount"], 2)

        # Converte data de string para datetime se necessário
        if "installments" in bill_dict and isinstance(bill_dict["installments"], dict):
            bill_dict["installments"] = parse_installments_dates(bill_dict["installments"])

        result = await db.bills.insert_one(bill_dict)
        created = await db.bills.find_one({"_id": result.inserted_id})
        return format_doc(created)
        
    except Exception as e:
        print(f"❌ Erro ao criar conta: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[BillResponse])
async def list_bills(
    paid: Optional[bool] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    query = {"user_id": str(current_user.id)}
    if paid is not None:
        query["paid"] = paid

    cursor = db.bills.find(query).sort("created_at", -1)
    bills = await cursor.to_list(length=100)
    return [format_doc(b) for b in bills]


@router.get("/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    bill = await db.bills.find_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if not bill:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return format_doc(bill)


@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill(
    bill_id: str,
    bill_update: BillUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Remove campos None do update
    update_data = {k: v for k, v in bill_update.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    # ========== ATUALIZA updated_at (obrigatório) ==========
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    # ========== Se amount foi enviado, arredonda ==========
    if "amount" in update_data:
        update_data["amount"] = round(update_data["amount"], 2)
    
    # ========== Se paid for alterado para True e paid_date não foi enviado ==========
    if update_data.get("paid") is True and update_data.get("paid_date") is None:
        update_data["paid_date"] = datetime.now(timezone.utc)
    
    # ========== Se installments foi enviado com start_date como string ==========
    if "installments" in update_data and isinstance(update_data["installments"], dict):
        update_data["installments"] = parse_installments_dates(update_data["installments"])

    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "user_id": str(current_user.id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    updated = await db.bills.find_one({"_id": ObjectId(bill_id)})
    return format_doc(updated)


@router.delete("/{bill_id}", response_model=dict)
async def delete_bill(
    bill_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    result = await db.bills.delete_one({
        "_id": ObjectId(bill_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return {"message": "Conta deletada com sucesso"}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Adicionada função format_doc() para padronizar respostas
# ✅ Adicionada função parse_installments_dates() para conversão de datas
# ✅ update_bill agora atualiza updated_at automaticamente
# ✅ update_bill arredonda amount (round) quando enviado
# ✅ update_bill define paid_date automaticamente quando paid=True
# ✅ update_bill converte installments.start_date se for string
#
# ⏳ Paginação (skip/limit) no list_bills: postergado para pós-MVP
# 📌 Logging estruturado: planejado (substituir print)