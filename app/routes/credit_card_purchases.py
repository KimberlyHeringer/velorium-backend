from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from app.database import get_database
from app.models.credit_card_purchase import CreditCardPurchaseCreate, CreditCardPurchaseResponse
from app.models.credit_card_installment import CreditCardInstallmentResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/credit-card-purchases", tags=["Compras no Cartão"])


@router.post("/", response_model=CreditCardPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar se o cartão pertence ao usuário
    card = await db.credit_cards.find_one({
        "_id": ObjectId(purchase_data.card_id),
        "user_id": str(current_user.id)
    })
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    # Preparar documento da compra
    purchase_dict = purchase_data.model_dump()
    purchase_dict["user_id"] = str(current_user.id)
    purchase_dict["created_at"] = datetime.now(timezone.utc)
    purchase_dict["updated_at"] = datetime.now(timezone.utc)

    # Inserir compra
    result = await db.credit_card_purchases.insert_one(purchase_dict)

    # Calcular valor da parcela (divisão igual)
    amount_per_installment = purchase_data.total_amount / purchase_data.installments
    # Usar duas casas decimais (arredondar)
    amount_per_installment = round(amount_per_installment, 2)

    # Gerar parcelas
    installments = []
    for i in range(purchase_data.installments):
        due_date = purchase_data.first_due_date + timedelta(days=30 * i)  # simplificado: +30 dias
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

    # Inserir parcelas
    await db.credit_card_installments.insert_many(installments)

    # Buscar a compra criada para retornar
    created = await db.credit_card_purchases.find_one({"_id": result.inserted_id})
    created["id"] = str(created["_id"])
    return created


@router.get("/faturas", response_model=List[dict])
async def get_faturas(
    card_id: str,
    month: int = None,
    year: int = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar se o cartão pertence ao usuário
    card = await db.credit_cards.find_one({
        "_id": ObjectId(card_id),
        "user_id": str(current_user.id)
    })
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    # Construir query para parcelas
    query = {
        "card_id": card_id,
        "user_id": str(current_user.id)
    }
    if month is not None and year is not None:
        # Filtrar parcelas com vencimento no mês/ano especificado
        start_date = datetime(year, month, 1)
        end_date = datetime(year + (month // 12), (month % 12) + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
        query["due_date"] = {"$gte": start_date, "$lt": end_date}

    # Agrupar por mês/ano (usar aggregation)
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {
                "year": {"$year": "$due_date"},
                "month": {"$month": "$due_date"}
            },
            "total": {"$sum": "$amount"},
            "installments": {"$push": "$$ROOT"}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}}
    ]
    result = await db.credit_card_installments.aggregate(pipeline).to_list(length=100)
    # Converter _id de ObjectId para string nas parcelas
    for fatura in result:
        for installment in fatura["installments"]:
            installment["_id"] = str(installment["_id"])
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
    purchase["_id"] = str(purchase["_id"])
    return purchase


@router.delete("/purchases/{purchase_id}", response_model=dict)
async def delete_purchase(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar se a compra pertence ao usuário
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    # Excluir a compra e suas parcelas
    await db.credit_card_purchases.delete_one({"_id": ObjectId(purchase_id)})
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})

    return {"message": "Compra e parcelas excluídas com sucesso"}


@router.put("/installments/{installment_id}", response_model=dict)
async def mark_installment_paid(
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar se a parcela pertence ao usuário (através da purchase)
    installment = await db.credit_card_installments.find_one({"_id": ObjectId(installment_id)})
    if not installment:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")

    # Verificar se a compra pertence ao usuário
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(installment["purchase_id"]),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=403, detail="Acesso negado")

    # Marcar como paga
    result = await db.credit_card_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {"$set": {"paid": True, "paid_date": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Parcela já estava paga ou não pôde ser atualizada")
    return {"message": "Parcela marcada como paga"}