"""
Modelo de Parcelas de Cartão de Crédito
Arquivo: backend/app/models/credit_card_installment.py

🔧 CORRIGIDO: amount agora é int (centavos) para consistência com to_cents()
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class CreditCardInstallment(BaseModel):
    """
    Modelo de uma parcela individual de uma compra no cartão de crédito.
    Cada compra parcelada gera N parcelas.
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    - As rotas devem usar to_cents() e from_cents()
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    purchase_id: str = Field(..., description="ID da compra original")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    card_id: str = Field(..., description="ID do cartão usado")
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    due_date: datetime = Field(..., description="Data de vencimento da parcela")
    paid: bool = Field(default=False, description="Se já foi paga")
    paid_date: Optional[datetime] = Field(None, description="Data do pagamento")
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


class CreditCardInstallmentResponse(CreditCardInstallment):
    """
    Schema para respostas da API.
    Força que o campo id seja obrigatório (não opcional).
    """
    id: str = Field(..., description="ID único da parcela")


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. amount: float → int (centavos) - consistente com to_cents()
2. Removido round_amount (não necessário para int)
3. Adicionados descriptions em todos os Field()
4. Melhor documentação sobre centavos

✅ PENDENTE PARA FUTURO (pós-MVP):
================================================================================
1. Adicionar validação de due_date >= hoje (opcional)
2. Adicionar updated_at automático via evento no MongoDB

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int)
================================================================================
"""