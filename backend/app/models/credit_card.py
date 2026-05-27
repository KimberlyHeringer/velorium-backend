"""
Modelos de Cartões de Crédito
Arquivo: backend/app/models/credit_card.py
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from bson import ObjectId

# ============ SCHEMAS PYDANTIC ============

class CreditCardBase(BaseModel):
    """Base para cartão de crédito"""
    name: str = Field(..., min_length=1, max_length=50, description="Nome do cartão (ex: Nubank, Itaú)")
    brand: str = Field(..., min_length=1, max_length=20, description="Bandeira (Visa, Mastercard, etc)")
    limit: float = Field(..., gt=0, description="Limite total do cartão")
    closing_day: int = Field(..., ge=1, le=31, description="Dia de fechamento da fatura")
    due_day: int = Field(..., ge=1, le=31, description="Dia de vencimento da fatura")


class CreditCardCreate(CreditCardBase):
    """Schema para criação de cartão"""
    pass


class CreditCardUpdate(BaseModel):
    """Schema para atualização de cartão (todos opcionais)"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    brand: Optional[str] = Field(None, min_length=1, max_length=20)
    limit: Optional[float] = Field(None, gt=0)
    closing_day: Optional[int] = Field(None, ge=1, le=31)
    due_day: Optional[int] = Field(None, ge=1, le=31)


class CreditCardResponse(CreditCardBase):
    """Schema para resposta da API"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: str = Field(..., alias="_id", description="ID do cartão")
    user_id: str = Field(..., description="ID do usuário dono do cartão")
    limit_total: float = Field(default=0.0, description="Limite total utilizado")
    committed_amount: float = Field(default=0.0, description="Valor comprometido em compras")
    last_statement_closed_at: Optional[datetime] = None
    next_statement_due_date: Optional[datetime] = None
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: Optional[datetime] = None