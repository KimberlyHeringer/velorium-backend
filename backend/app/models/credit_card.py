"""
Modelos de Cartões de Crédito
Arquivo: backend/app/models/credit_card.py
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

# ============ SCHEMAS PYDANTIC ============

class CreditCardBase(BaseModel):
    """Base para cartão de crédito"""
    name: str = Field(..., description="Nome do cartão (ex: Nubank, Itaú)")
    brand: str = Field(..., description="Bandeira (Visa, Mastercard, etc)")
    limit: float = Field(..., description="Limite total do cartão")
    closing_day: int = Field(..., ge=1, le=31, description="Dia de fechamento da fatura")
    due_day: int = Field(..., ge=1, le=31, description="Dia de vencimento da fatura")


class CreditCardCreate(CreditCardBase):
    """Schema para criação de cartão"""
    pass


class CreditCardUpdate(BaseModel):
    """Schema para atualização de cartão (todos opcionais)"""
    name: Optional[str] = None
    brand: Optional[str] = None
    limit: Optional[float] = None
    closing_day: Optional[int] = Field(None, ge=1, le=31)
    due_day: Optional[int] = Field(None, ge=1, le=31)


class CreditCardResponse(CreditCardBase):
    """Schema para resposta da API"""
    id: str = Field(..., description="ID do cartão")
    user_id: str = Field(..., description="ID do usuário dono do cartão")
    limit_total: float = Field(default=0.0, description="Limite total utilizado")
    committed_amount: float = Field(default=0.0, description="Valor comprometido em compras")
    last_statement_closed_at: Optional[datetime] = None
    next_statement_due_date: Optional[datetime] = None
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ FUNÇÕES AUXILIARES ============

def credit_card_helper(card) -> dict:
    """Converte documento do MongoDB para dicionário"""
    return {
        "id": str(card["_id"]),
        "user_id": card["user_id"],
        "name": card["name"],
        "brand": card["brand"],
        "limit": card["limit"],
        "closing_day": card["closing_day"],
        "due_day": card["due_day"],
        "limit_total": card.get("limit_total", 0.0),
        "committed_amount": card.get("committed_amount", 0.0),
        "last_statement_closed_at": card.get("last_statement_closed_at"),
        "next_statement_due_date": card.get("next_statement_due_date"),
        "created_at": card["created_at"],
        "updated_at": card.get("updated_at"),
    }