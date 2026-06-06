"""
Modelo de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/models/bill_installment.py

🔧 CORRIGIDO: amount agora é int (centavos) para consistência com to_cents()
🔧 REGRA 3.3: Refatoração de Bills - Modelo similar ao credit_card_installments
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class BillInstallmentBase(BaseModel):
    """Base para parcela de conta a pagar"""
    bill_id: str = Field(..., description="ID da conta mestra (referência para bills)")
    user_id: str = Field(..., description="ID do usuário (segurança multi-tenant)")
    number: int = Field(..., ge=1, description="Número da parcela (ex: 1, 2, 3...)")
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    due_date: datetime = Field(..., description="Data de vencimento da parcela")
    paid: bool = Field(default=False, description="Se já foi paga")
    paid_date: Optional[datetime] = Field(None, description="Data do pagamento (preenchido quando paid=True)")


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
    
    id: str = Field(..., alias="_id", description="ID único da parcela")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Data de criação")
    updated_at: Optional[datetime] = Field(None, description="Data da última atualização")


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. amount: float → int (centavos) - consistente com to_cents()
2. Adicionados descriptions em todos os Field()
3. Adicionado updated_at no Response
4. Melhor documentação sobre centavos

✅ STATUS: CONSISTENTE COM AS ROTAS E BANCO DE DADOS
================================================================================
"""