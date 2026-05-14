"""
Rotas de Compras Parceladas no Cartão de Crédito
Arquivo: backend/app/routes/credit_card_purchases.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.database import get_database
from app.models.credit_card_purchase import CreditCardPurchaseCreate, CreditCardPurchaseResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/credit-card-purchases", tags=["Compras no Cartão"])


# ========== FUNÇÕES AUXILIARES ==========

def split_amount(total: float, parts: int) -> List[float]:
    base = round(total / parts, 2)
    remainder = round(total - base * parts, 2)
    amounts = [base] * parts
    if remainder != 0:
        amounts[-1] = round(amounts[-1] + remainder, 2)
    return amounts


def serialize_doc(doc: dict) -> dict:
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    doc["id"] = doc["_id"]
    return doc


async def update_card_committed_amount(card_id: str, delta: float, db):
    """Atualiza o committed_amount do cartão (delta pode ser positivo ou negativo)."""
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$inc": {"committed_amount": delta}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )


async def check_available_limit(card_id: str, required: float, db) -> float:
    """Retorna limite disponível ou levanta HTTPException se insuficiente."""
    card = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    available = card["limit_total"] - card["committed_amount"]
    if required > available:
        raise HTTPException(
            status_code=400,
            detail=f"Limite insuficiente. Disponível: {available:.2f}, Necessário: {required:.2f}"
        )
    return available


# ========== ENDPOINTS ==========

@router.post("/", response_model=CreditCardPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Validar cartão e limite
    try:
        card = await db.credit_cards.find_one({
            "_id": ObjectId(purchase_data.card_id),
            "user_id": str(current_user.id)
        })
    except:
        raise HTTPException(status_code=400, detail="card_id inválido")
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    # Verificar limite disponível
    await check_available_limit(purchase_data.card_id, purchase_data.total_amount, db)

    # Converter data
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

    # Gerar parcelas
    amounts = split_amount(purchase_data.total_amount, purchase_data.installments)
    installments = []
    for i in range(purchase_data.installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": str(result.inserted_id),
            "user_id": str(current_user.id),
            "card_id": purchase_data.card_id,
            "amount": amounts[i],
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)
    if installments:
        await db.credit_card_installments.insert_many(installments)

    # Atualizar committed_amount (valor total da compra)
    await update_card_committed_amount(purchase_data.card_id, purchase_data.total_amount, db)

    created = await db.credit_card_purchases.find_one({"_id": result.inserted_id})
    return serialize_doc(created)


@router.get("/faturas", response_model=List[dict])
async def get_faturas(
    card_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # ... (mantido igual, sem alterações de limite)
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
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        query["due_date"] = {"$gte": start_date, "$lt": end_date}

    installments_cursor = db.credit_card_installments.find(query)
    installments = await installments_cursor.to_list(length=100)

    if not installments:
        return []

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
    # Verificar compra existente
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    # Verificar parcelas pagas
    existing_installments = await db.credit_card_installments.find({
        "purchase_id": purchase_id,
        "paid": True
    }).to_list(length=1)
    if existing_installments:
        raise HTTPException(
            status_code=400,
            detail="Não é possível editar compra com parcelas já pagas."
        )

    # Calcular diferença de valor total
    old_total = purchase["total_amount"]
    new_total = purchase_data.total_amount
    delta = new_total - old_total

    if delta != 0:
        # Verificar limite disponível se o valor aumentou
        if delta > 0:
            await check_available_limit(purchase_data.card_id, delta, db)
        # Atualizar committed_amount
        await update_card_committed_amount(purchase_data.card_id, delta, db)

    # Atualizar dados da compra
    update_dict = purchase_data.model_dump()
    update_dict["updated_at"] = datetime.now(timezone.utc)
    if "first_due_date" in update_dict and isinstance(update_dict["first_due_date"], str):
        update_dict["first_due_date"] = datetime.fromisoformat(update_dict["first_due_date"].replace('Z', '+00:00'))

    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": update_dict}
    )

    # Recriar parcelas
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    first_due = update_dict["first_due_date"]
    amounts = split_amount(new_total, update_dict["installments"])
    installments = []
    for i in range(update_dict["installments"]):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": str(current_user.id),
            "card_id": update_dict["card_id"],
            "amount": amounts[i],
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

    # Subtrair o valor total do committed_amount
    total_amount = purchase["total_amount"]
    await update_card_committed_amount(purchase["card_id"], -total_amount, db)

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

    if installment.get("paid", False):
        raise HTTPException(status_code=400, detail="Parcela já está paga")

    # Verificar propriedade da compra
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(installment["purchase_id"]),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=403, detail="Acesso negado")

    # Marcar parcela como paga
    await db.credit_card_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {"$set": {"paid": True, "paid_date": datetime.now(timezone.utc)}}
    )

    # 🔥 EXTRA: Reduzir committed_amount pelo valor da parcela paga
    await update_card_committed_amount(installment["card_id"], -installment["amount"], db)

    return {"message": "Parcela marcada como paga e compromisso reduzido"}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Validação de limite na criação, edição (aumento) e exclusão
# ✅ Atualização do committed_amount via $inc
# ✅ Redução por parcela paga (implementado)
# ✅ Proteção contra edição com parcelas pagas
# ✅ Cálculo de delta para edição
# ✅ Funções auxiliares para reaproveitamento