"""
Modelo de Compra Parcelada no Cartão de Crédito
Arquivo: backend/app/models/credit_card_purchase.py

🔧 CORRIGIDO: 
- total_amount agora é int (centavos)
- Adicionado committed_amount (controle de limite)
- Adicionado remaining_installments
- Limitado parcelas a 360 (30 anos)
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class CreditCardPurchase(BaseModel):
    """
    Representa uma compra parcelada no cartão de crédito.
    Uma compra gera N parcelas (CreditCardInstallment).
    
    🔧 IMPORTANTE: Valores estão em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    card_id: str = Field(..., description="ID do cartão de crédito")
    description: str = Field(..., max_length=200, description="Descrição da compra")
    
    # 🔧 CORRIGIDO: float → int (centavos)
    total_amount: int = Field(..., gt=0, description="Valor total em CENTAVOS (ex: 15050 = R$150,50)")
    
    # 🔧 NOVO: Controle de limite do cartão
    committed_amount: int = Field(..., ge=0, description="Valor comprometido do limite em CENTAVOS")
    
    # Parcelamento
    installments: int = Field(..., ge=1, le=360, description="Número total de parcelas (máx 360 = 30 anos)")
    remaining_installments: int = Field(..., ge=0, description="Parcelas restantes a pagar")
    
    # Datas
    first_due_date: datetime = Field(..., description="Data da primeira parcela")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da compra")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    
    # Controle
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Status
    fully_paid: bool = Field(default=False, description="Compra totalmente quitada?")
    fully_paid_date: Optional[datetime] = Field(None, description="Data da última parcela paga")

    @model_validator(mode='after')
    def validate_remaining_installments(self):
        """Remaining installments não pode ser maior que total"""
        if self.remaining_installments > self.installments:
            raise ValueError('remaining_installments não pode ser maior que installments')
        return self
    
    @model_validator(mode='after')
    def check_fully_paid(self):
        """Se fully_paid=True, fully_paid_date é obrigatório"""
        if self.fully_paid and self.fully_paid_date is None:
            raise ValueError('fully_paid_date é obrigatório quando fully_paid=True')
        return self


class CreditCardPurchaseCreate(BaseModel):
    """Schema usado para CRIAR uma nova compra parcelada"""
    card_id: str = Field(..., description="ID do cartão de crédito")
    description: str = Field(..., max_length=200, description="Descrição da compra")
    total_amount: int = Field(..., gt=0, description="Valor total em CENTAVOS (ex: 15050 = R$150,50)")
    installments: int = Field(..., ge=1, le=360, description="Número de parcelas (máx 360 = 30 anos)")
    first_due_date: datetime = Field(..., description="Data da primeira parcela")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da compra")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")


class CreditCardPurchaseResponse(CreditCardPurchase):
    """Schema usado para RESPOSTAS da API"""
    pass


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. total_amount: float → int (centavos) - consistente com to_cents()
2. Adicionado committed_amount (controle de limite do cartão)
3. Adicionado remaining_installments (parcelas restantes)
4. Adicionado fully_paid e fully_paid_date
5. Limitado installments para 360 (30 anos, não 999)
6. Removido round_amount (não necessário para int)
7. Adicionadas validações entre campos
8. Adicionados max_length nos campos de texto

✅ PENDENTE PARA FUTURO (pós-MVP):
================================================================================
1. Adicionar campo interest_rate (para compras com juros)
2. Adicionar campo discount (para descontos à vista)

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO
================================================================================
"""