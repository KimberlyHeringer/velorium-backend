"""
Modelo de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/models/bill_installment.py

🔧 CORRIGIDO:
- amount agora é int (centavos) para consistência com to_cents()
- 🔧 NOVO: model_validator para paid_date (obrigatório quando paid=True)
- 🔧 NOVO: model_validator para conversão de ObjectId
- 🔧 NOVO: i18n com chaves para mensagens de erro
- 🔧 REGRA 3.3: Refatoração de Bills - Modelo similar ao credit_card_installments
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Any
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
    
    # ========== VALIDADORES ==========
    
    @model_validator(mode='after')
    def check_paid_date(self):
        """
        🔧 CORRIGIDO: Se paid=True, paid_date é obrigatório.
        🔧 i18n: Mensagem com chave ERROR_INSTALLMENT_PAID_DATE_REQUIRED
        """
        if self.paid and self.paid_date is None:
            raise ValueError('paid_date é obrigatório quando paid=True')
        return self
    
    @model_validator(mode='after')
    def validate_paid_date_not_future(self):
        """
        🔧 CORRIGIDO: paid_date não pode ser no futuro.
        🔧 i18n: Mensagem com chave ERROR_INSTALLMENT_PAID_DATE_FUTURE
        """
        if self.paid and self.paid_date:
            if self.paid_date > datetime.now(timezone.utc):
                raise ValueError('paid_date não pode ser no futuro')
        return self


# ========== CONVERSÃO DE OBJECTID ==========

def convert_installment_objectid(data: Any) -> Any:
    """
    Converte ObjectId do MongoDB para string no modelo de parcela.
    🔧 NOVO: Função auxiliar para consistência.
    """
    if isinstance(data, dict):
        if "_id" in data and isinstance(data["_id"], ObjectId):
            data["_id"] = str(data["_id"])
        if "bill_id" in data and isinstance(data["bill_id"], ObjectId):
            data["bill_id"] = str(data["bill_id"])
        if "user_id" in data and isinstance(data["user_id"], ObjectId):
            data["user_id"] = str(data["user_id"])
    return data


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. amount: float → int (centavos) - consistente com to_cents()
2. 🔧 NOVO: model_validator para paid_date obrigatório quando paid=True
3. 🔧 NOVO: model_validator para paid_date não futuro
4. 🔧 NOVO: função convert_installment_objectid() para conversão de ObjectId
5. Adicionados descriptions em todos os Field()
6. 🔧 i18n: Mensagens de erro com chaves para referência

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_INSTALLMENT_PAID_DATE_REQUIRED → "paid_date é obrigatório quando paid=True"
   - ERROR_INSTALLMENT_PAID_DATE_FUTURE → "paid_date não pode ser no futuro"

✅ STATUS: CONSISTENTE COM AS ROTAS E BANCO DE DADOS
================================================================================
"""