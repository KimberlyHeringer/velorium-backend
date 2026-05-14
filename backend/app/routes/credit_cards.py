"""
Modelo de Cartão de Crédito
Arquivo: backend/app/models/credit_card.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone, date
from bson import ObjectId


class CreditCard(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    brand: Optional[str] = None
    closing_day: int = Field(..., ge=1, le=31)
    due_day: int = Field(..., ge=1, le=31)

    limit_total: float = Field(default=0, ge=0)
    committed_amount: float = Field(default=0, ge=0)   # ← será atualizado pelas rotas

    last_statement_closed_at: Optional[datetime] = None
    next_statement_due_date: Optional[date] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def check_days(self):
        if self.closing_day == self.due_day:
            raise ValueError('closing_day and due_day must be different')
        return self

    @property
    def limit_available(self) -> float:
        return self.limit_total - self.committed_amount


class CreditCardCreate(BaseModel):
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
    id: str


class CreditCardUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    closing_day: Optional[int] = Field(None, ge=1, le=31)
    due_day: Optional[int] = Field(None, ge=1, le=31)
    limit_total: Optional[float] = Field(None, ge=0)
    committed_amount: Optional[float] = Field(None, ge=0)

    @model_validator(mode='after')
    def check_days(self):
        if self.closing_day is not None and self.due_day is not None and self.closing_day == self.due_day:
            raise ValueError('closing_day and due_day must be different')
        return self

    @model_validator(mode='before')
    @classmethod
    def round_amounts(cls, values):
        if values.get('limit_total') is not None:
            values['limit_total'] = round(values['limit_total'], 2)
        if values.get('committed_amount') is not None:
            values['committed_amount'] = round(values['committed_amount'], 2)
        return values
    
    
# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Adicionada função format_card_doc() para padronizar respostas
# ✅ Adicionada verificação de compras associadas antes de deletar cartão
# ✅ Arredondamento de limit_total e committed_amount no update
# ✅ Todas as rotas usam format_card_doc() agora
#
# 📌 Pendente (futuro):
#    - Paginação no list_credit_cards (pós-MVP)
#    - Logging estruturado (substituir print)
#
# 🔍 Verificação necessária:
#    - Modelo CreditCard deve ter validador closing_day != due_day
#      (adicionar se não existir)