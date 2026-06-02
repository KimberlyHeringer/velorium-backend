"""
Modelo de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/models/bill_installment.py

🔧 REGRA 3.3: Refatoração de Bills
- Modelo similar ao credit_card_installments
- Cada parcela é um documento independente
- Permite pagamento individual de parcelas
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class BillInstallmentBase(BaseModel):
    """Base para parcela de conta a pagar"""
    bill_id: str = Field(..., description="ID da conta mestra")
    user_id: str = Field(..., description="ID do usuário")
    number: int = Field(..., ge=1, description="Número da parcela (ex: 1, 2, 3...)")
    amount: float = Field(..., gt=0, description="Valor da parcela")
    due_date: datetime = Field(..., description="Data de vencimento")
    paid: bool = Field(default=False, description="Se já foi paga")
    paid_date: Optional[datetime] = Field(None, description="Data do pagamento")


class BillInstallmentCreate(BillInstallmentBase):
    """Schema para criação de parcela"""
    pass


class BillInstallmentResponse(BillInstallmentBase):
    """Schema para resposta da API"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: str = Field(..., alias="_id")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: Optional[datetime] = Field(None, description="Data de atualização")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Modelo similar ao credit_card_installments (consistência)
# ✅ bill_id referencia a conta mestra (relacionamento)
# ✅ number permite saber qual parcela (1, 2, 3...)
# ✅ paid + paid_date para controle de pagamento
# ✅ Validação: number >= 1, amount > 0