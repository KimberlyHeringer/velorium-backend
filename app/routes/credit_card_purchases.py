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
    print(f"🔍 Recebida compra: {purchase_data}")
    
    # Verificar cartão
    try:
        card = await db.credit_cards.find_one({
            "_id": ObjectId(purchase_data.card_id),
            "user_id": str(current_user.id)
        })
    except:
        raise HTTPException(status_code=400, detail="card_id inválido")
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    # Converter first_due_date de string para datetime se necessário
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

    await db.credit_card_installments.insert_many(installments)

    # Buscar a compra criada e formatar resposta
    created = await db.credit_card_purchases.find_one({"_id": result.inserted_id})
    if created:
        created["id"] = str(created["_id"])
        # del created["_id"]  # opcional
    return created

@router.get("/faturas", response_model=List[dict])
async def get_faturas(
    card_id: str,
    month: int = None,
    year: int = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    print(f"🔍 get_faturas chamado: card_id={card_id}, month={month}, year={year}")
    try:
        card = await db.credit_cards.find_one({
            "_id": ObjectId(card_id),
            "user_id": str(current_user.id)
        })
    except:
        raise HTTPException(status_code=400, detail="card_id inválido")
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

    # Buscar parcelas diretamente (sem aggregation complexa)
    installments_cursor = db.credit_card_installments.find(query)
    installments = await installments_cursor.to_list(length=100)
    
    # Agrupar por purchase_id para obter detalhes da compra
    from collections import defaultdict
    purchases_map = {}
    for inst in installments:
        pid = inst["purchase_id"]
        if pid not in purchases_map:
            # Buscar compra
            purchase = await db.credit_card_purchases.find_one({"_id": ObjectId(pid)})
            if purchase:
                purchase["id"] = str(purchase["_id"])
                purchases_map[pid] = purchase
        inst["_id"] = str(inst["_id"])
        inst["id"] = inst["_id"]
    
    # Estruturar resultado
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

@router.put("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def update_purchase(
    purchase_id: str,
    purchase_data: CreditCardPurchaseCreate,  # ou crie um modelo de atualização
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar se a compra existe e pertence ao usuário
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    # Atualizar dados da compra
    update_dict = purchase_data.model_dump()
    update_dict["updated_at"] = datetime.now(timezone.utc)
    # Não permitir alterar card_id? Vamos manter
    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": update_dict}
    )

    # Recalcular parcelas? Vamos remover as antigas e recriar (simplificado)
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    
    first_due = update_dict["first_due_date"]
    if isinstance(first_due, str):
        first_due = datetime.fromisoformat(first_due.replace('Z', '+00:00'))
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
    await db.credit_card_installments.insert_many(installments)

    updated = await db.credit_card_purchases.find_one({"_id": ObjectId(purchase_id)})
    updated["id"] = str(updated["_id"])
    return updated

@router.delete("/purchases/{purchase_id}", response_model=dict)
async def delete_purchase_full(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Já existe uma função delete_purchase, mas vamos garantir
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")
    await db.credit_card_purchases.delete_one({"_id": ObjectId(purchase_id)})
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    return {"message": "Compra e parcelas excluídas"}

@router.put("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def update_purchase(
    purchase_id: str,
    purchase_data: CreditCardPurchaseCreate,  # ou crie um modelo de atualização
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verificar se a compra existe e pertence ao usuário
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    # Atualizar dados da compra
    update_dict = purchase_data.model_dump()
    update_dict["updated_at"] = datetime.now(timezone.utc)
    # Não permitir alterar card_id? Vamos manter
    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": update_dict}
    )

    # Recalcular parcelas? Vamos remover as antigas e recriar (simplificado)
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    
    first_due = update_dict["first_due_date"]
    if isinstance(first_due, str):
        first_due = datetime.fromisoformat(first_due.replace('Z', '+00:00'))
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
    await db.credit_card_installments.insert_many(installments)

    updated = await db.credit_card_purchases.find_one({"_id": ObjectId(purchase_id)})
    updated["id"] = str(updated["_id"])
    return updated

@router.delete("/purchases/{purchase_id}", response_model=dict)
async def delete_purchase_full(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # Já existe uma função delete_purchase, mas vamos garantir
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")
    await db.credit_card_purchases.delete_one({"_id": ObjectId(purchase_id)})
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    return {"message": "Compra e parcelas excluídas"}

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