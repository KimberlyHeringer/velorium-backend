"""
Modelo de Contas a Pagar (Bills)
Arquivo: backend/app/models/bill.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class InstallmentInfo(BaseModel):
    """Informações sobre parcelamento da conta"""
    total: int = Field(..., ge=1)
    current: int = Field(1, ge=1)
    start_date: datetime
    due_day: Optional[int] = Field(None, ge=1, le=31)


class NotificationInfo(BaseModel):
    """Configurações de notificação para esta conta"""
    enabled: bool = False
    days_before: int = Field(0, ge=0)


class Bill(BaseModel):
    """
    Modelo principal de Conta a Pagar
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str  # injetado pelo backend, nunca vem do frontend
    description: str
    amount: float = Field(..., gt=0)
    installments: InstallmentInfo
    category: Optional[str] = None
    notes: Optional[str] = None
    notification: NotificationInfo = Field(default_factory=NotificationInfo)
    paid: bool = False
    paid_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def check_paid_date(self):
        """
        VALIDAÇÃO: Se a conta está marcada como paga (paid=True),
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
        Evita problemas de precisão com float (ex: 0.1 + 0.2 = 0.30000000000000004)
        """
        return round(v, 2) if v is not None else v


class BillCreate(BaseModel):
    """Schema usado para CRIAR uma nova conta"""
    description: str
    amount: float = Field(..., gt=0)
    installments: InstallmentInfo
    category: Optional[str] = None
    notes: Optional[str] = None
    notification: NotificationInfo = Field(default_factory=NotificationInfo)

    @field_validator('amount')
    @classmethod
    def round_amount(cls, v):
        return round(v, 2) if v is not None else v


class BillUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma conta existente"""
    description: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    installments: Optional[InstallmentInfo] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    notification: Optional[NotificationInfo] = None
    paid: Optional[bool] = None
    paid_date: Optional[datetime] = None

    @field_validator('amount')
    @classmethod
    def round_amount(cls, v):
        return round(v, 2) if v is not None else v


class BillResponse(Bill):
    """Schema usado para RESPOSTAS (herda tudo de Bill)"""
    pass