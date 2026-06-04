"""
Modelo de Compra Parcelada no Cartão de Crédito
Arquivo: backend/app/models/credit_card_purchase.py

🔧 MODIFICADO: Aumentado limite máximo de parcelas para 999
- Permite financiamentos longos (carro, casa, etc.)
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class CreditCardPurchase(BaseModel):
    """
    Representa uma compra parcelada no cartão de crédito.
    Uma compra gera N parcelas (CreditCardInstallment).
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    card_id: str
    description: str
    total_amount: float = Field(..., gt=0)
    installments: int = Field(..., ge=1, le=999)  # 🔧 Aumentado para 999
    first_due_date: datetime
    category: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='before')
    @classmethod
    def round_amount(cls, values):
        if 'total_amount' in values and values['total_amount'] is not None:
            values['total_amount'] = round(values['total_amount'], 2)
        return values


class CreditCardPurchaseCreate(BaseModel):
    """Schema usado para CRIAR uma nova compra parcelada"""
    card_id: str
    description: str
    total_amount: float = Field(..., gt=0)
    installments: int = Field(..., ge=1, le=999)  # 🔧 Aumentado para 999
    first_due_date: datetime
    category: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def round_amount(cls, values):
        if 'total_amount' in values and values['total_amount'] is not None:
            values['total_amount'] = round(values['total_amount'], 2)
        return values


class CreditCardPurchaseResponse(CreditCardPurchase):
    """Schema usado para RESPOSTAS da API"""
    pass


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ id como Optional (MongoDB gera o _id)
# ✅ total_amount com gt=0 (não aceita zero ou negativo)
# ✅ installments com ge=1, le=12 (1 a 12 parcelas)
# ✅ round(total_amount, 2) para evitar problemas de precisão
# ✅ Separados schemas para Create e Response
#
# 📅 Funcionalidade futura (controle de limite do cartão):
#    Será implementada nas rotas (credit_card_purchases.py),
#    verificando limit_total e atualizando committed_amount.