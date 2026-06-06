"""
Modelo de Contas a Pagar (Bills)
Arquivo: backend/app/models/bill.py

🔧 CORRIGIDO: amount agora é int (centavos) para consistência com to_cents()
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class InstallmentInfo(BaseModel):
    """Informações sobre parcelamento da conta"""
    total: int = Field(..., ge=1, description="Número total de parcelas")
    current: int = Field(1, ge=1, description="Parcela atual")
    start_date: datetime = Field(..., description="Data da primeira parcela")
    due_day: Optional[int] = Field(None, ge=1, le=31, description="Dia de vencimento (opcional)")


class NotificationInfo(BaseModel):
    """Configurações de notificação para esta conta"""
    enabled: bool = Field(default=False, description="Notificações ativas?")
    days_before: int = Field(0, ge=0, description="Dias antes para lembrar")


class Bill(BaseModel):
    """
    Modelo principal de Conta a Pagar
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    - As rotas usam to_cents() e from_cents() automaticamente
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (preenchido pelo backend)")
    description: str = Field(..., max_length=200, description="Descrição da conta")
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    installments: InstallmentInfo = Field(..., description="Informações de parcelamento")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da conta")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    notification: NotificationInfo = Field(default_factory=NotificationInfo, description="Configurações de notificação")
    paid: bool = Field(default=False, description="Conta totalmente paga?")
    paid_date: Optional[datetime] = Field(None, description="Data em que foi totalmente paga")
    recurring: bool = Field(default=False, description="É recorrente?")
    recurring_end_date: Optional[datetime] = Field(None, description="Data final da recorrência")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def check_paid_date(self):
        """Se paid=True, paid_date é obrigatório"""
        if self.paid and self.paid_date is None:
            raise ValueError('paid_date é obrigatório quando paid=True')
        return self
    
    @model_validator(mode='after')
    def validate_installment_due_day(self):
        """due_day é opcional - pode ser None"""
        return self


class BillCreate(BaseModel):
    """Schema usado para CRIAR uma nova conta"""
    description: str = Field(..., max_length=200, description="Descrição da conta")
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    installments: InstallmentInfo = Field(..., description="Informações de parcelamento")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da conta")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    notification: NotificationInfo = Field(default_factory=NotificationInfo, description="Configurações de notificação")
    recurring: bool = Field(default=False, description="É recorrente?")
    recurring_end_date: Optional[datetime] = Field(None, description="Data final da recorrência")

    @model_validator(mode='after')
    def validate_installment_due_day(self):
        return self


class BillUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma conta existente"""
    description: Optional[str] = Field(None, max_length=200, description="Descrição da conta")
    amount: Optional[int] = Field(None, gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    installments: Optional[InstallmentInfo] = Field(None, description="Informações de parcelamento")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da conta")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    notification: Optional[NotificationInfo] = Field(None, description="Configurações de notificação")
    paid: Optional[bool] = Field(None, description="Conta totalmente paga?")
    paid_date: Optional[datetime] = Field(None, description="Data em que foi totalmente paga")
    recurring: Optional[bool] = Field(None, description="É recorrente?")
    recurring_end_date: Optional[datetime] = Field(None, description="Data final da recorrência")


class BillResponse(Bill):
    """Schema usado para RESPOSTAS da API"""
    pass


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. amount: float → int (centavos) - consistente com to_cents()
2. Removido round_amount_field (não necessário para int)
3. Adicionados max_length nos campos de texto
4. Adicionados descriptions em todos os Field()
5. Melhor documentação sobre centavos

✅ STATUS: CONSISTENTE COM AS ROTAS E BANCO DE DADOS
================================================================================
"""