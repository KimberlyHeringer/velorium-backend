from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from app.database import get_database
from app.models.credit_card_purchase import CreditCardPurchaseCreate, CreditCardPurchaseResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/credit-card-purchases", tags=["Compras no Cartão"])

def serialize_doc(doc: dict) -> dict:
    """Converte ObjectId e datas para tipos serializáveis JSON."""
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    if "first_due_date" in doc and isinstance(doc["first_due_date"], datetime):
        doc["first_due_date"] = doc["first_due_date"].isoformat()
    if "created_at" in doc and isinstance(doc["created_at"], datetime):
        doc["created_at"] = doc["created_at"].isoformat()
    if "updated_at" in doc and isinstance(doc["updated_at"], datetime):
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc

@router.post("/", response_model=CreditCardPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    print(f"🔍 Recebida compra: {purchase_data}")

    # Validar cartão
    try:
        card = await db.credit_cards.find_one({
            "_id": ObjectId(purchase_data.card_id),
            "user_id": str(current_user.id)
        })
    except:
        raise HTTPException(status_code=400, detail="card_id inválido")
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    # Converter first_due_date para datetime (se string)
    first_due = purchase_data.first_due_date
    if isinstance(first_due, str):
        first_due = datetime.fromisoformat(first_due.replace('Z', '+00:00'))

    # Preparar documento da compra
    purchase_dict = purchase_data.model_dump()
    purchase_dict["user_id"] = str(current_user.id)
    purchase_dict["first_due_date"] = first_due
    purchase_dict["created_at"] = datetime.now(timezone.utc)
    purchase_dict["updated_at"] = datetime.now(timezone.utc)

    # Inserir compra
    result = await db.credit_card_purchases.insert_one(purchase_dict)

    # Calcular valor da parcela
    amount_per_installment = round(purchase_data.total_amount / purchase_data.installments, 2)

    # Gerar parcelas
    installments = []
    for i in range(purchase_data.installments):
        due_date = first_due + timedelta(days=30 * i)
        installment = {
            "purchase_id": str(result.inserted_id),
            "user_id": str(current_user.id),
            "card_id": purchase_data.card_id,
            "amount": amount_per_installment,
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)

    if installments:
        await db.credit_card_installments.insert_many(installments)

    # Buscar a compra criada e serializar
    created = await db.credit_card_purchases.find_one({"_id": result.inserted_id})
    if not created:
        raise HTTPException(status_code=500, detail="Erro ao recuperar compra criada")
    return serialize_doc(created)

@router.get("/faturas", response_model=List[dict])
async def get_faturas(
    card_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    print(f"🔍 get_faturas: card_id={card_id}, month={month}, year={year}")
    try:
        card = await db.credit_cards.find_one({
            "_id": ObjectId(card_id),
            "user_id": str(current_user.id)
        })
    except:
        raise HTTPException(status_code=400, detail="card_id inválido")
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    query = {
        "card_id": card_id,
        "user_id": str(current_user.id)
    }
    if month is not None and year is not None:
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        query["due_date"] = {"$gte": start_date, "$lt": end_date}

    installments_cursor = db.credit_card_installments.find(query)
    installments = await installments_cursor.to_list(length=100)

    # Agrupar por purchase_id
    purchases_map = {}
    for inst in installments:
        pid = inst["purchase_id"]
        if pid not in purchases_map:
            purchase = await db.credit_card_purchases.find_one({"_id": ObjectId(pid)})
            if purchase:
                purchase["id"] = str(purchase["_id"])
                purchases_map[pid] = purchase
        inst["_id"] = str(inst["_id"])
        inst["id"] = inst["_id"]
        # Converter datas para string
        if "due_date" in inst and isinstance(inst["due_date"], datetime):
            inst["due_date"] = inst["due_date"].isoformat()

    result = []
    for pid, purchase in purchases_map.items():
        purchase_installments = [i for i in installments if i["purchase_id"] == pid]
        total = sum(i["amount"] for i in purchase_installments)
        result.append({
            "purchase_id": pid,
            "description": purchase["description"],
            "total_amount": purchase["total_amount"],
            "installments_total": purchase["installments"],
            "category": purchase.get("category"),
            "installments": purchase_installments,
            "total": total
        })
    return result

@router.get("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def get_purchase(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")
    return serialize_doc(purchase)

@router.put("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def update_purchase(
    purchase_id: str,
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar existência
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    # Atualizar dados
    update_dict = purchase_data.model_dump()
    update_dict["updated_at"] = datetime.now(timezone.utc)

    # Converter first_due_date para datetime se necessário
    if "first_due_date" in update_dict and isinstance(update_dict["first_due_date"], str):
        update_dict["first_due_date"] = datetime.fromisoformat(update_dict["first_due_date"].replace('Z', '+00:00'))

    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": update_dict}
    )

    # Recriar parcelas
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})

    first_due = update_dict["first_due_date"]
    amount_per_installment = round(update_dict["total_amount"] / update_dict["installments"], 2)
    installments = []
    for i in range(update_dict["installments"]):
        due_date = first_due + timedelta(days=30 * i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": str(current_user.id),
            "card_id": update_dict["card_id"],
            "amount": amount_per_installment,
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)
    if installments:
        await db.credit_card_installments.insert_many(installments)

    updated = await db.credit_card_purchases.find_one({"_id": ObjectId(purchase_id)})
    return serialize_doc(updated)

@router.delete("/purchases/{purchase_id}", response_model=dict)
async def delete_purchase(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")
    await db.credit_card_purchases.delete_one({"_id": ObjectId(purchase_id)})
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    return {"message": "Compra e parcelas excluídas com sucesso"}

@router.put("/installments/{installment_id}", response_model=dict)
async def mark_installment_paid(
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    installment = await db.credit_card_installments.find_one({"_id": ObjectId(installment_id)})
    if not installment:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(installment["purchase_id"]),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=403, detail="Acesso negado")
    result = await db.credit_card_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {"$set": {"paid": True, "paid_date": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Parcela já estava paga")
    return {"message": "Parcela marcada como paga"}