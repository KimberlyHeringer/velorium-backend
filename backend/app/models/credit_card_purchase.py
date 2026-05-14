"""
Modelo de Compra Parcelada no Cartão de Crédito
Arquivo: backend/app/models/credit_card_purchase.py
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

    id: Optional[str] = Field(None, alias="_id")   # ID gerado pelo MongoDB
    user_id: str                                   # injetado pelo backend
    card_id: str                                   # ID do cartão usado
    description: str                               # descrição da compra
    total_amount: float = Field(..., gt=0)         # valor total (positivo)
    installments: int = Field(..., ge=1, le=12)    # número de parcelas (1-12)
    first_due_date: datetime                       # data da primeira parcela
    category: Optional[str] = None                 # ex: Alimentação, Lazer
    notes: Optional[str] = None                    # observações opcionais
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDADORES ==========

    @model_validator(mode='before')
    @classmethod
    def round_amount(cls, values):
        """
        Arredonda total_amount para 2 casas decimais antes de salvar.
        Evita problemas de precisão com float.
        """
        if 'total_amount' in values and values['total_amount'] is not None:
            values['total_amount'] = round(values['total_amount'], 2)
        return values


class CreditCardPurchaseCreate(BaseModel):
    """
    Schema usado para CRIAR uma nova compra parcelada.
    (não inclui campos gerados pelo backend como id, user_id, created_at)
    """
    card_id: str
    description: str
    total_amount: float = Field(..., gt=0)
    installments: int = Field(..., ge=1, le=12)
    first_due_date: datetime
    category: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def round_amount(cls, values):
        """Arredonda total_amount na criação também"""
        if 'total_amount' in values and values['total_amount'] is not None:
            values['total_amount'] = round(values['total_amount'], 2)
        return values


class CreditCardPurchaseResponse(CreditCardPurchase):
    """
    Schema usado para RESPOSTAS da API.
    Herda tudo de CreditCardPurchase (incluindo o validador).
    """
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