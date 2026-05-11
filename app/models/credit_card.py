"""
Modelo de Cartão de Crédito
Arquivo: backend/app/models/credit_card.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone, date
from bson import ObjectId


class CreditCard(BaseModel):
    """
    Modelo principal de Cartão de Crédito.
    Controle de limite: limit_total - committed_amount = limite disponível.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str                                    # injetado pelo backend
    name: str                                       # nome do cartão (ex: "Nubank")
    brand: Optional[str] = None                     # bandeira (Visa, Mastercard, etc.)
    closing_day: int = Field(..., ge=1, le=31)      # dia do fechamento da fatura
    due_day: int = Field(..., ge=1, le=31)          # dia do vencimento da fatura

    # ========== CAMPOS PARA CONTROLE DE LIMITE (futuro, mas já adiantado) ==========
    limit_total: float = Field(default=0, ge=0)           # limite total do cartão
    committed_amount: float = Field(default=0, ge=0)      # valor já comprometido em compras
    # O limite disponível é calculado: limit_total - committed_amount

    last_statement_closed_at: Optional[datetime] = None   # data do último fechamento
    next_statement_due_date: Optional[date] = None        # próximo vencimento

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def check_days(self):
        """
        Valida que o dia de fechamento e vencimento são diferentes.
        (não impede que due_day seja menor que closing_day, pois alguns cartões têm essa característica)
        """
        if self.closing_day == self.due_day:
            raise ValueError('closing_day and due_day must be different')
        return self

    @property
    def limit_available(self) -> float:
        """Calcula o limite disponível (derivado, não salvo no banco)"""
        return self.limit_total - self.committed_amount


class CreditCardCreate(BaseModel):
    """Schema usado para CRIAR um novo cartão"""
    name: str = Field(..., min_length=1)
    brand: Optional[str] = None
    closing_day: int = Field(..., ge=1, le=31)
    due_day: int = Field(..., ge=1, le=31)

    @model_validator(mode='after')
    def check_days(self):
        if self.closing_day == self.due_day:
            raise ValueError('closing_day and due_day must be different')
        return self


class CreditCardResponse(CreditCard):
    """Schema usado para RESPOSTAS da API (força id como string)"""
    id: str


class CreditCardUpdate(BaseModel):
    """Schema usado para ATUALIZAR um cartão existente"""
    name: Optional[str] = None
    brand: Optional[str] = None
    closing_day: Optional[int] = Field(None, ge=1, le=31)
    due_day: Optional[int] = Field(None, ge=1, le=31)
    limit_total: Optional[float] = Field(None, ge=0)        # permite atualizar limite
    committed_amount: Optional[float] = Field(None, ge=0)   # permite ajuste manual

    @model_validator(mode='after')
    def check_days(self):
        """Se ambos os dias forem fornecidos, não podem ser iguais"""
        if self.closing_day is not None and self.due_day is not None and self.closing_day == self.due_day:
            raise ValueError('closing_day and due_day must be different')
        return self

    @model_validator(mode='before')
    @classmethod
    def round_amounts(cls, values):
        """Arredonda valores monetários para 2 casas decimais"""
        if 'limit_total' in values and values['limit_total'] is not None:
            values['limit_total'] = round(values['limit_total'], 2)
        if 'committed_amount' in values and values['committed_amount'] is not None:
            values['committed_amount'] = round(values['committed_amount'], 2)
        return values


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Validador cruzado closing_day != due_day (em todos os schemas)
# ✅ Apenas uma definição de CreditCardResponse (com id: str)
# ✅ Adicionados campos limit_total e committed_amount (com default=0)
# ✅ Adicionada propriedade limit_available (calculada, não salva)
# ✅ round() aplicado em valores monetários no update
#
# 📅 Funcionalidade futura (controle de limite):
#    A lógica de atualizar committed_amount (ao criar compra/pagar parcela)
#    será implementada nas rotas (credit_card_purchases.py, credit_card_installments.py)