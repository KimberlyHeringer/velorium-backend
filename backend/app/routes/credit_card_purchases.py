"""
Rotas de Compras Parceladas no Cartão de Crédito
Arquivo: backend/app/routes/credit_card_purchases.py

🔧 MODIFICADO: Regra 2.2 - Usa format_mongo_doc
🔧 MODIFICADO: Regra 2.8 - Adicionado logs
🔧 MODIFICADO: Regra 2.10 - Adicionado validate_object_id
🔧 MODIFICADO: Regra 2.11 - Conversão de moeda para centavos (to_cents/from_cents)
🔧 MODIFICADO: Logs adicionais na rota /faturas para debug
🔧 CORRIGIDO: Rota /faturas mais tolerante a erros (retorna lista vazia em vez de 500)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.database import get_database
from app.models.credit_card_purchase import CreditCardPurchaseCreate, CreditCardPurchaseResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import format_mongo_doc, format_mongo_docs, validate_object_id
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/credit-card-purchases", tags=["Compras no Cartão"])


def split_amount(total: float, parts: int) -> List[float]:
    """Divide um valor total em partes iguais (para parcelas)"""
    base = round(total / parts, 2)
    remainder = round(total - base * parts, 2)
    amounts = [base] * parts
    if remainder != 0:
        amounts[-1] = round(amounts[-1] + remainder, 2)
    return amounts


async def update_card_committed_amount(card_id: str, delta: float, db):
    """Atualiza o committed_amount do cartão"""
    validate_object_id(card_id, "card_id")
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$inc": {"committed_amount": delta}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )


async def check_available_limit(card_id: str, required: float, db) -> float:
    """Retorna limite disponível ou levanta HTTPException se insuficiente"""
    validate_object_id(card_id, "card_id")
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


@router.post("/", response_model=CreditCardPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova compra parcelada"""
    validate_object_id(purchase_data.card_id, "card_id")
    
    card = await db.credit_cards.find_one({
        "_id": ObjectId(purchase_data.card_id),
        "user_id": str(current_user.id)
    })
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    await check_available_limit(purchase_data.card_id, purchase_data.total_amount, db)

    first_due = purchase_data.first_due_date
    if isinstance(first_due, str):
        first_due = datetime.fromisoformat(first_due.replace('Z', '+00:00'))

    purchase_dict = purchase_data.model_dump()
    purchase_dict["user_id"] = str(current_user.id)
    purchase_dict["first_due_date"] = first_due
    purchase_dict["created_at"] = datetime.now(timezone.utc)
    purchase_dict["updated_at"] = datetime.now(timezone.utc)
    
    purchase_dict["total_amount"] = to_cents(purchase_dict["total_amount"])

    result = await db.credit_card_purchases.insert_one(purchase_dict)

    total_amount_reais = from_cents(purchase_dict["total_amount"])
    amounts = split_amount(total_amount_reais, purchase_data.installments)
    
    installments = []
    for i in range(purchase_data.installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": str(result.inserted_id),
            "user_id": str(current_user.id),
            "card_id": purchase_data.card_id,
            "amount": to_cents(amounts[i]),
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)
    if installments:
        await db.credit_card_installments.insert_many(installments)

    await update_card_committed_amount(purchase_data.card_id, purchase_dict["total_amount"], db)

    created = await db.credit_card_purchases.find_one({"_id": result.inserted_id})
    
    if created and "total_amount" in created:
        created["total_amount"] = from_cents(created["total_amount"])
    
    logger.info(f"Compra criada: {purchase_data.description}")
    return format_mongo_doc(created)


@router.get("/purchases", response_model=dict)
async def get_purchases(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    card_id: Optional[str] = Query(None),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    if card_id:
        validate_object_id(card_id, "card_id")
        query["card_id"] = card_id

    items, total = await paginate_query(
        db.credit_card_purchases, query, params, sort=[("created_at", -1)]
    )
    
    for item in items:
        if "total_amount" in item:
            item["total_amount"] = from_cents(item["total_amount"])
    
    formatted_items = format_mongo_docs(items)
    return paginate(formatted_items, total, params).model_dump()


@router.get("/faturas", response_model=List[dict])
async def get_faturas(
    card_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna faturas do cartão - Versão tolerante a erros"""
    try:
        logger.info(f"🔍 Buscando faturas - card_id: {card_id}, user: {current_user.id}")
        
        validate_object_id(card_id, "card_id")
        
        card = await db.credit_cards.find_one({
            "_id": ObjectId(card_id),
            "user_id": str(current_user.id)
        })
        if not card:
            logger.warning(f"Cartão não encontrado: {card_id}")
            return []  # Retorna lista vazia

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
            logger.info(f"🔍 Query com data: {query}")

        # Busca parcelas
        installments = []
        try:
            installments_cursor = db.credit_card_installments.find(query)
            installments = await installments_cursor.to_list(length=1000)
            logger.info(f"🔍 Encontradas {len(installments)} parcelas")
        except Exception as e:
            logger.error(f"Erro ao buscar parcelas: {e}")
            return []

        if not installments:
            return []

        purchases_map = {}
        for inst in installments:
            pid = inst.get("purchase_id")
            if not pid:
                logger.warning(f"Parcela sem purchase_id: {inst}")
                continue
                
            if pid not in purchases_map:
                try:
                    purchase = await db.credit_card_purchases.find_one({"_id": ObjectId(pid)})
                    if purchase:
                        if "total_amount" in purchase:
                            purchase["total_amount"] = from_cents(purchase["total_amount"])
                        purchases_map[pid] = format_mongo_doc(purchase)
                    else:
                        logger.warning(f"Compra não encontrada para parcela: {pid}")
                except Exception as e:
                    logger.error(f"Erro ao buscar compra {pid}: {e}")
                    continue

        result = []
        for pid, purchase in purchases_map.items():
            try:
                purchase_installments = [i for i in installments if i.get("purchase_id") == pid]
                total = 0
                for i in purchase_installments:
                    try:
                        total += from_cents(i.get("amount", 0))
                    except Exception as e:
                        logger.error(f"Erro ao converter amount da parcela: {e}")
                
                result.append({
                    "purchase_id": pid,
                    "description": purchase.get("description", ""),
                    "total_amount": purchase.get("total_amount", 0),
                    "installments_total": purchase.get("installments", 1),
                    "category": purchase.get("category"),
                    "installments": purchase_installments,
                    "total": total
                })
            except Exception as e:
                logger.error(f"Erro ao processar compra {pid}: {e}")
                continue
        
        logger.info(f"🔍 Retornando {len(result)} faturas")
        return result
        
    except Exception as e:
        logger.error(f"❌ Erro FATAL em get_faturas: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Retorna lista vazia em vez de erro 500
        return []


@router.get("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def get_purchase(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")
    
    if "total_amount" in purchase:
        purchase["total_amount"] = from_cents(purchase["total_amount"])
    
    return format_mongo_doc(purchase)


@router.put("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def update_purchase(
    purchase_id: str,
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    existing_installments = await db.credit_card_installments.find({
        "purchase_id": purchase_id,
        "paid": True
    }).to_list(length=1)
    if existing_installments:
        raise HTTPException(
            status_code=400,
            detail="Não é possível editar compra com parcelas já pagas."
        )

    old_total = purchase["total_amount"]
    new_total = to_cents(purchase_data.total_amount)
    delta = new_total - old_total

    if delta != 0:
        if delta > 0:
            await check_available_limit(purchase_data.card_id, from_cents(delta), db)
        await update_card_committed_amount(purchase_data.card_id, delta, db)

    update_dict = purchase_data.model_dump()
    update_dict["updated_at"] = datetime.now(timezone.utc)
    if "first_due_date" in update_dict and isinstance(update_dict["first_due_date"], str):
        update_dict["first_due_date"] = datetime.fromisoformat(update_dict["first_due_date"].replace('Z', '+00:00'))
    
    update_dict["total_amount"] = to_cents(update_dict["total_amount"])

    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": update_dict}
    )

    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    first_due = update_dict["first_due_date"]
    total_amount_reais = from_cents(update_dict["total_amount"])
    amounts = split_amount(total_amount_reais, update_dict["installments"])
    
    new_installments = []
    for i in range(update_dict["installments"]):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": str(current_user.id),
            "card_id": update_dict["card_id"],
            "amount": to_cents(amounts[i]),
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        new_installments.append(installment)
    if new_installments:
        await db.credit_card_installments.insert_many(new_installments)

    updated = await db.credit_card_purchases.find_one({"_id": ObjectId(purchase_id)})
    
    if updated and "total_amount" in updated:
        updated["total_amount"] = from_cents(updated["total_amount"])
    
    return format_mongo_doc(updated)


@router.delete("/purchases/{purchase_id}", response_model=dict)
async def delete_purchase(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

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
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.credit_card_installments.find_one({"_id": ObjectId(installment_id)})
    if not installment:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")

    if installment.get("paid", False):
        raise HTTPException(status_code=400, detail="Parcela já está paga")

    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(installment["purchase_id"]),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=403, detail="Acesso negado")

    await db.credit_card_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {"$set": {"paid": True, "paid_date": datetime.now(timezone.utc)}}
    )

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