from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
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
    # Verificar cartão
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

    # Gerar parcelas
    amount_per_installment = round(purchase_data.total_amount / purchase_data.installments, 2)
    installments = []
    for i in range(purchase_data.installments):
        due_date = purchase_data.first_due_date + timedelta(days=30 * i)
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
    await db.credit_card_installments.insert_many(installments)

    # Buscar a compra criada e formatar resposta
    created = await db.credit_card_purchases.find_one({"_id": result.inserted_id})
    if created:
        created["id"] = str(created.pop("_id"))  # remove _id e adiciona id
        # Converte campos de data para ISO string se necessário (pydantic fará automaticamente)
    return created

@router.get("/faturas", response_model=dict)  # mudamos para dict para retornar estrutura amigável
async def get_faturas(
    card_id: str,
    month: int = None,
    year: int = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar cartão
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
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        query["due_date"] = {"$gte": start_date, "$lt": end_date}

    # Buscar parcelas
    cursor = db.credit_card_installments.find(query)
    installments = await cursor.to_list(length=1000)
    
    total = sum(inst["amount"] for inst in installments)
    # Converter ObjectId para string
    for inst in installments:
        inst["_id"] = str(inst["_id"])
        inst["id"] = inst["_id"]
    
    return {
        "total": total,
        "purchases": installments  # ou você pode agrupar por purchase_id, mas para simplificar
    }

# As demais rotas (GET /purchases/{purchase_id}, DELETE /purchases/{purchase_id}, PUT /installments/{installment_id}) permanecem iguais, apenas corrigindo a conversão de id
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
    purchase["id"] = str(purchase.pop("_id"))
    return purchase

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