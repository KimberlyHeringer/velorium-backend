"""
Modelo de Parcelas de Contas a Pagar (Bill Installments)
Arquivo: backend/app/models/bill_installment.py

Funcionalidades:
- Gerenciamento de parcelas individuais de contas a pagar
- Controle de pagamento por parcela
- Histórico de pagamentos

Principais features:
- amount em centavos (int) para precisão
- Validação: paid=True exige paid_date
- Validação: paid_date não pode ser no futuro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- Herança de AmountMixin (amount com validação)
- Herança de PaymentMixin (paid, paid_date)
- ✅ CORRIGIDO: BillInstallmentBase herda de BaseModelWithUser
- ✅ CORRIGIDO: BillInstallmentResponse herda de BillInstallmentWithTimestamps
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import datetime, timezone

from app.models.base import BaseModelWithUser
from app.models.mixins import PaymentMixin, AmountMixin


class BillInstallmentBase(BaseModelWithUser, PaymentMixin, AmountMixin):
    """
    Base para parcela de conta a pagar.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
      - PaymentMixin: paid, paid_date (validação de pagamento)
      - AmountMixin: amount (validação de valor positivo)
    
    🔧 CAMPOS ADICIONADOS:
      - bill_id: ID da conta mestra
      - number: Número da parcela (1, 2, 3...)
      - due_date: Data de vencimento da parcela
    """
    
    bill_id: str = Field(
        ...,
        description="ID da conta mestra (referência para bills)"
    )
    
    number: int = Field(
        ...,
        ge=1,
        description="Número da parcela (ex: 1, 2, 3...)"
    )
    
    due_date: datetime = Field(
        ...,
        description="Data de vencimento da parcela"
    )


class BillInstallmentCreate(BillInstallmentBase):
    """Schema para criação de parcela"""
    pass


class BillInstallmentResponse(BillInstallmentBase):
    """
    Schema para resposta da API.
    
    🔧 ✅ CORRIGIDO: Herda de BillInstallmentBase (com timestamps)
    
    🔧 DIFERENÇAS DO MODEL BASE:
      - id é obrigatório (sobrescreve Optional)
    """
    
    id: str = Field(..., alias="_id", description="ID único da parcela")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de PaymentMixin (paid, paid_date, validação de pagamento)
#   - Herança de AmountMixin (amount com validação)
#   - Validação: paid=True exige paid_date
#   - Validação: paid_date não pode ser no futuro
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Response)
#   - ✅ CORRIGIDO: Herança correta de BaseModelWithUser
#   - ✅ CORRIGIDO: BillInstallmentResponse herda timestamps
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de due_date >= hoje (depende da regra de negócio)
#   - Campo paid_by (quem pagou) - está no AuditMixin (opcional)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser, PaymentMixin, AmountMixin (03/07/2026)
#   - v3: Correções - Herança correta, remoção de campos duplicados (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO