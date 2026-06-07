"""
Rotas de Compras Parceladas no Cartão de Crédito
Arquivo: backend/app/routes/credit_card_purchases.py

🔧 CORRIGIDO:
- split_amount_cents() agora trabalha com inteiros (centavos)
- update_card_committed_amount agora recebe delta_cents (int)
- check_available_limit agora recebe required_cents (int)
- create_purchase agora usa centavos internamente
- Removido endpoint /debug/clean-invalid-data (não deve ir para produção)
- Corrigidas mensagens de erro para usar from_cents() na exibição
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

# ========== CONSTANTES ==========
MAX_INSTALLMENTS = 360  # 30 anos


# 🔧 CORRIGIDO: Agora trabalha com inteiros (centavos)
def split_amount_cents(total_cents: int, parts: int) -> List[int]:
    """
    Divide um valor em centavos igualmente entre parcelas.
    Distribui o resto (se houver) nas primeiras parcelas.
    
    Exemplo: 100 centavos em 3 parcelas = [34, 33, 33]
    """
    if parts <= 0:
        return []
    base = total_cents // parts
    remainder = total_cents - (base * parts)
    amounts = [base] * parts
    for i in range(remainder):
        amounts[i] += 1
    return amounts


# 🔧 CORRIGIDO: delta_cents agora é int
async def update_card_committed_amount(card_id: str, delta_cents: int, db):
    """Atualiza o committed_amount do cartão (delta em centavos, pode ser negativo)"""
    validate_object_id(card_id, "card_id")
    await db.credit_cards.update_one(
        {"_id": ObjectId(card_id)},
        {"$inc": {"committed_amount": delta_cents}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )


# 🔧 CORRIGIDO: required_cents agora é int
async def check_available_limit(card_id: str, required_cents: int, db) -> int:
    """
    Retorna limite disponível em centavos.
    Levanta HTTPException se insuficiente.
    """
    validate_object_id(card_id, "card_id")
    card = await db.credit_cards.find_one({"_id": ObjectId(card_id)})
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")
    
    # 🔧 CORRIGIDO: committed_amount deve ser int (centavos)
    available_cents = card.get("total_limit", 0) - card.get("committed_amount", 0)
    
    if required_cents > available_cents:
        # 🔧 Exibe em reais apenas para o usuário entender
        raise HTTPException(
            status_code=400,
            detail=f"Limite insuficiente. Disponível: R$ {from_cents(available_cents):.2f}, Necessário: R$ {from_cents(required_cents):.2f}"
        )
    return available_cents


@router.post("/", response_model=CreditCardPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: CreditCardPurchaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Cria uma nova compra parcelada"""
    validate_object_id(purchase_data.card_id, "card_id")
    
    # Verifica se o cartão pertence ao usuário
    card = await db.credit_cards.find_one({
        "_id": ObjectId(purchase_data.card_id),
        "user_id": str(current_user.id)
    })
    if not card:
        raise HTTPException(status_code=404, detail="Cartão não encontrado")

    # 🔧 CORRIGIDO: Converte total_amount para centavos antes de validar limite
    total_amount_cents = to_cents(purchase_data.total_amount)
    
    # 🔧 CORRIGIDO: Valida limite com centavos
    await check_available_limit(purchase_data.card_id, total_amount_cents, db)

    # Valida número máximo de parcelas
    if purchase_data.installments > MAX_INSTALLMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Número máximo de parcelas é {MAX_INSTALLMENTS}"
        )

    first_due = purchase_data.first_due_date
    if isinstance(first_due, str):
        first_due = datetime.fromisoformat(first_due.replace('Z', '+00:00'))

    purchase_dict = purchase_data.model_dump()
    purchase_dict["user_id"] = str(current_user.id)
    purchase_dict["first_due_date"] = first_due
    purchase_dict["created_at"] = datetime.now(timezone.utc)
    purchase_dict["updated_at"] = datetime.now(timezone.utc)
    
    # 🔧 CORRIGIDO: guarda em centavos
    purchase_dict["total_amount"] = total_amount_cents

    result = await db.credit_card_purchases.insert_one(purchase_dict)

    # 🔧 CORRIGIDO: usa split_amount_cents com inteiros
    amounts_cents = split_amount_cents(total_amount_cents, purchase_data.installments)
    
    installments = []
    for i in range(purchase_data.installments):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": str(result.inserted_id),
            "user_id": str(current_user.id),
            "card_id": purchase_data.card_id,
            "amount": amounts_cents[i],  # já em centavos
            "due_date": due_date,
            "paid": False,
            "paid_date": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        installments.append(installment)
    if installments:
        await db.credit_card_installments.insert_many(installments)

    # 🔧 CORRIGIDO: passa delta em centavos
    await update_card_committed_amount(purchase_data.card_id, total_amount_cents, db)

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
    """Lista compras parceladas do usuário"""
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
    """Retorna faturas do cartão - Versão com conversão de ObjectId"""
    try:
        logger.info(f"🔍 Buscando faturas - card_id: {card_id}")
        
        validate_object_id(card_id, "card_id")
        
        card = await db.credit_cards.find_one({
            "_id": ObjectId(card_id),
            "user_id": str(current_user.id)
        })
        if not card:
            return []

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

        installments = await db.credit_card_installments.find(query).to_list(1000)
        
        if not installments:
            return []

        purchases_map = {}
        for inst in installments:
            pid = inst.get("purchase_id")
            if not pid:
                continue
                
            if pid not in purchases_map:
                try:
                    purchase = await db.credit_card_purchases.find_one({"_id": ObjectId(pid)})
                    if purchase:
                        if "total_amount" in purchase:
                            purchase["total_amount"] = from_cents(purchase["total_amount"])
                        purchase["_id"] = str(purchase["_id"])
                        purchases_map[pid] = purchase
                except Exception as e:
                    logger.error(f"Erro ao buscar compra {pid}: {e}")
                    continue

        result = []
        for pid, purchase in purchases_map.items():
            purchase_installments = [i for i in installments if i.get("purchase_id") == pid]
            total = 0
            for inst in purchase_installments:
                total += from_cents(inst.get("amount", 0))
            
            installments_list = []
            for inst in purchase_installments:
                inst_copy = {
                    "_id": str(inst.get("_id")),
                    "purchase_id": str(inst.get("purchase_id")),
                    "user_id": str(inst.get("user_id")),
                    "card_id": str(inst.get("card_id")),
                    "amount": inst.get("amount"),
                    "due_date": inst.get("due_date"),
                    "paid": inst.get("paid"),
                    "paid_date": inst.get("paid_date"),
                    "created_at": inst.get("created_at"),
                    "updated_at": inst.get("updated_at")
                }
                installments_list.append(inst_copy)
            
            result.append({
                "purchase_id": pid,
                "description": purchase.get("description", ""),
                "total_amount": purchase.get("total_amount", 0),
                "installments_total": purchase.get("installments", 1),
                "category": purchase.get("category"),
                "installments": installments_list,
                "total": total
            })
        
        logger.info(f"🔍 Retornando {len(result)} faturas")
        return result
        
    except Exception as e:
        logger.error(f"❌ Erro FATAL em get_faturas: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


@router.get("/purchases/{purchase_id}", response_model=CreditCardPurchaseResponse)
async def get_purchase(
    purchase_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma compra específica"""
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
    """Atualiza uma compra existente"""
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    # Verifica se há parcelas pagas
    existing_installments = await db.credit_card_installments.find({
        "purchase_id": purchase_id,
        "paid": True
    }).to_list(length=1)
    if existing_installments:
        raise HTTPException(
            status_code=400,
            detail="Não é possível editar compra com parcelas já pagas."
        )

    # 🔧 CORRIGIDO: trabalha com centavos
    old_total_cents = purchase["total_amount"]
    new_total_cents = to_cents(purchase_data.total_amount)
    delta_cents = new_total_cents - old_total_cents

    if delta_cents != 0:
        if delta_cents > 0:
            await check_available_limit(purchase_data.card_id, delta_cents, db)
        await update_card_committed_amount(purchase_data.card_id, delta_cents, db)

    # Valida número máximo de parcelas
    if purchase_data.installments > MAX_INSTALLMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Número máximo de parcelas é {MAX_INSTALLMENTS}"
        )

    update_dict = purchase_data.model_dump()
    update_dict["updated_at"] = datetime.now(timezone.utc)
    if "first_due_date" in update_dict and isinstance(update_dict["first_due_date"], str):
        update_dict["first_due_date"] = datetime.fromisoformat(update_dict["first_due_date"].replace('Z', '+00:00'))
    
    # 🔧 CORRIGIDO: guarda em centavos
    update_dict["total_amount"] = new_total_cents

    await db.credit_card_purchases.update_one(
        {"_id": ObjectId(purchase_id)},
        {"$set": update_dict}
    )

    # Recria parcelas
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    first_due = update_dict["first_due_date"]
    
    # 🔧 CORRIGIDO: usa split_amount_cents com inteiros
    amounts_cents = split_amount_cents(new_total_cents, update_dict["installments"])
    
    new_installments = []
    for i in range(update_dict["installments"]):
        due_date = first_due + relativedelta(months=i)
        installment = {
            "purchase_id": purchase_id,
            "user_id": str(current_user.id),
            "card_id": update_dict["card_id"],
            "amount": amounts_cents[i],  # já em centavos
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
    """Remove uma compra e todas as suas parcelas"""
    validate_object_id(purchase_id, "purchase_id")
    
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(purchase_id),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra não encontrada")

    total_amount_cents = purchase["total_amount"]
    # 🔧 CORRIGIDO: passa delta negativo em centavos
    await update_card_committed_amount(purchase["card_id"], -total_amount_cents, db)

    await db.credit_card_purchases.delete_one({"_id": ObjectId(purchase_id)})
    await db.credit_card_installments.delete_many({"purchase_id": purchase_id})
    
    return {"message": "Compra e parcelas excluídas com sucesso"}


@router.put("/installments/{installment_id}", response_model=dict)
async def mark_installment_paid(
    installment_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Marca uma parcela como paga"""
    validate_object_id(installment_id, "installment_id")
    
    installment = await db.credit_card_installments.find_one({"_id": ObjectId(installment_id)})
    if not installment:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")

    if installment.get("paid", False):
        raise HTTPException(status_code=400, detail="Parcela já está paga")

    # Verifica se a compra pertence ao usuário
    purchase = await db.credit_card_purchases.find_one({
        "_id": ObjectId(installment["purchase_id"]),
        "user_id": str(current_user.id)
    })
    if not purchase:
        raise HTTPException(status_code=403, detail="Acesso negado")

    await db.credit_card_installments.update_one(
        {"_id": ObjectId(installment_id)},
        {"$set": {"paid": True, "paid_date": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}}
    )

    # 🔧 CORRIGIDO: amount já está em centavos
    await update_card_committed_amount(installment["card_id"], -installment["amount"], db)

    return {"message": "Parcela marcada como paga e compromisso reduzido"}


# ========== ENDPOINT REMOVIDO ==========
# O endpoint /debug/clean-invalid-data foi removido.
# Não deve ser usado em produção. Para limpeza de dados,
# execute scripts diretamente no banco ou via CLI.


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. split_amount_cents() agora trabalha com inteiros (centavos)
2. update_card_committed_amount agora recebe delta_cents (int)
3. check_available_limit agora recebe required_cents (int)
4. create_purchase agora usa centavos internamente
5. update_purchase agora usa centavos internamente
6. delete_purchase agora usa centavos internamente
7. mark_installment_paid agora usa centavos internamente
8. Adicionada constante MAX_INSTALLMENTS = 360
9. Removido endpoint /debug/clean-invalid-data
10. Corrigidas mensagens de erro para usar from_cents() na exibição

⚠️ PENDÊNCIAS PARA PÓS-MVP:
================================================================================
1. Internacionalização (i18n) de todas as mensagens de erro
2. Adicionar validação de data (first_due_date não pode ser no passado?)
3. Adicionar suporte a juros em compras parceladas
4. Adicionar rota para desmarcar parcela como paga (rollback)
5. Adicionar logs de auditoria (quem pagou cada parcela)

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int)
================================================================================
"""