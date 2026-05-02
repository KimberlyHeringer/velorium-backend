"""
Modelo de Parcelas de Cartão de Crédito
Arquivo: backend/app/models/credit_card_installment.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class CreditCardInstallment(BaseModel):
    """
    Modelo de uma parcela individual de uma compra no cartão de crédito.
    Cada compra parcelada gera N parcelas.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    purchase_id: str          # ID da compra original
    user_id: str              # injetado pelo backend
    card_id: str              # ID do cartão usado
    amount: float = Field(..., gt=0)   # valor da parcela individual
    due_date: datetime        # data de vencimento da parcela
    paid: bool = False        # se já foi paga
    paid_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def check_paid_date(self):
        """
        Se a parcela está marcada como paga (paid=True),
        o campo paid_date não pode ser None.
        """
        if self.paid and self.paid_date is None:
            raise ValueError('paid_date é obrigatório quando paid=True')
        return self

    @field_validator('amount')
    @classmethod
    def round_amount(cls, v):
        """
        Arredonda o valor para 2 casas decimais.
        Evita problemas de precisão com float.
        """
        return round(v, 2) if v is not None else v


class CreditCardInstallmentResponse(CreditCardInstallment):
    """
    Schema para respostas da API.
    Força que o campo id seja obrigatório (não opcional).
    """
    id: str   # garante que o frontend sempre receba um ID


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Mantivemos float (não Decimal) por compatibilidade com MongoDB
# ✅ Adicionamos round(amount, 2) para evitar precisão de float
# ✅ Adicionamos validador paid/paid_date
# ⏳ Validação de due_date >= hoje: postergado (opcional para MVP)
# ⏳ updated_at automático: postergado (mantém atualização manual nas rotas)