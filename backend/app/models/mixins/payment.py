"""
Arquivo: backend/app/models/mixins/payment.py
Objetivo: Fornecer campos e validações para pagamentos

Funcionalidades:
- Define o mixin PaymentMixin com campos paid e paid_date
- Fornece validação: se paid=True, paid_date é obrigatório
- Fornece validação: paid_date não pode ser no futuro

Principais features:
- Campo paid (bool) indicando se foi pago
- Campo paid_date (datetime) com data do pagamento
- Validação automática de consistência dos dados
"""

from pydantic import Field, model_validator
from typing import Optional
from datetime import datetime, timezone


class PaymentMixin:
    """
    Mixin que adiciona campos e validações de pagamento.
    
    🔧 CAMPOS ADICIONADOS:
      - paid: bool (indica se foi pago)
      - paid_date: Optional[datetime] (data do pagamento)
    
    🔧 VALIDAÇÕES:
      1. Se paid=True, paid_date é obrigatório
      2. Se paid=True, paid_date não pode ser no futuro
    """
    
    paid: bool = Field(
        default=False,
        description="Indica se o item já foi pago"
    )
    
    paid_date: Optional[datetime] = Field(
        default=None,
        description="Data em que o pagamento foi realizado"
    )
    
    @model_validator(mode='after')
    def validate_payment(self):
        """
        Valida os campos de pagamento.
        
        REGRAS:
          1. Se paid=True, paid_date é obrigatório
          2. Se paid=True, paid_date não pode ser no futuro
        """
        if self.paid and self.paid_date is None:
            raise ValueError('paid_date é obrigatório quando paid=True')
        
        if self.paid and self.paid_date is not None:
            if self.paid_date > datetime.now(timezone.utc):
                raise ValueError('paid_date não pode ser no futuro')
        
        return self


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Campos paid (bool) e paid_date (Optional[datetime])
#   - Validação: paid=True exige paid_date
#   - Validação: paid_date não pode ser no futuro
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de paid_date >= due_date (depende do model)
#   - Campo paid_by (quem pagou) - está no audit.py
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO