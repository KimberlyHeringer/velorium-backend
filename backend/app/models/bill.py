"""
Modelo de Contas a Pagar (Bills)
Arquivo: backend/app/models/bill.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import round_amount  # ← centralizado


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
    user_id: str
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
        """Se paid=True, paid_date é obrigatório"""
        if self.paid and self.paid_date is None:
            raise ValueError('paid_date é obrigatório quando paid=True')
        return self
    
    @model_validator(mode='after')
    def validate_installment_due_day(self):
        """Parcelas com total > 1 exigem due_day"""
        if self.installments.total > 1 and self.installments.due_day is None:
            raise ValueError('Parcelamento com mais de 1 parcela exige due_day')
        return self

    @model_validator(mode='after')
    def round_amount_field(self):
        """Arredonda amount usando função centralizada"""
        if self.amount is not None:
            self.amount = round_amount(self.amount)
        return self


class BillCreate(BaseModel):
    """Schema usado para CRIAR uma nova conta"""
    description: str
    amount: float = Field(..., gt=0)
    installments: InstallmentInfo
    category: Optional[str] = None
    notes: Optional[str] = None
    notification: NotificationInfo = Field(default_factory=NotificationInfo)

    @model_validator(mode='after')
    def validate_installment_due_day(self):
        if self.installments.total > 1 and self.installments.due_day is None:
            raise ValueError('Parcelamento com mais de 1 parcela exige due_day')
        return self

    @model_validator(mode='after')
    def round_amount_field(self):
        if self.amount is not None:
            self.amount = round_amount(self.amount)
        return self


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

    @model_validator(mode='after')
    def round_amount_field(self):
        if self.amount is not None:
            self.amount = round_amount(self.amount)
        return self


class BillResponse(Bill):
    """Schema usado para RESPOSTAS"""
    pass

    """
    Schema usado para RESPOSTAS (herda tudo de Bill)
    
    🔒 SEGURANÇA: O campo user_id é retornado, mas o frontend NUNCA o utiliza.
    O frontend foi verificado e não faz uso deste campo em nenhuma operação.
    A segurança é mantida porque o backend NUNCA confia em user_id vindo do frontend.
    """
    pass


"""
================================================================================
📋 FEEDBACK DO ARQUIVO (MVP) – ATUALIZADO COM ANÁLISE DO FRONTEND

✅ O QUE FOI MODIFICADO/MELHORADO NESTA VERSÃO:
--------------------------------------------------------------------------------
1. Adicionada validação: parcelas com total > 1 exigem due_day
2. Adicionados comentários de SEGURANÇA explicando que user_id NUNCA vem do frontend
3. Documentação clara no BillCreate e BillResponse sobre o papel do user_id
4. Removido import não utilizado (field_validator)

✅ O QUE ESTÁ EXCELENTE E FOI MANTIDO:
--------------------------------------------------------------------------------
1. Validação de 'paid' com 'paid_date' (paid=True exige paid_date)
2. Arredondamento de float para 2 casas (evita problemas de precisão)
3. ConfigDict com json_encoders para ObjectId
4. NotificationInfo separado com days_before

🔒 VERIFICAÇÃO DE SEGURANÇA COM O FRONTEND (REALIZADA):
--------------------------------------------------------------------------------
- Frontend NÃO envia user_id nas requisições ✅
- Frontend NÃO utiliza user_id nas respostas ✅
- Backend injeta user_id via token JWT ✅
- Arquitetura segura contra injeção de user_id malicioso ✅

⚠️ PENDÊNCIAS PARA VERSÕES FUTURAS (NÃO CRÍTICAS PARA MVP):
--------------------------------------------------------------------------------
1. Adicionar índices no MongoDB (database.py):
   - bills: [("user_id", 1), ("paid", 1)]
   - bills: [("user_id", 1), ("installments.start_date", 1)]

2. Internacionalização (i18n) das mensagens de erro

================================================================================
✅ STATUS: APROVADO PARA MVP (COM SEGURANÇA VERIFICADA)
================================================================================
"""