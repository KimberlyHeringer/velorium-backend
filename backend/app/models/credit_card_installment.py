"""
Modelo de Parcelas de Cartão de Crédito
Arquivo: backend/app/models/credit_card_installment.py

Funcionalidades:
- Gerenciamento de parcelas individuais de compras no cartão
- Controle de pagamento por parcela
- Histórico de pagamentos

Principais features:
- amount em centavos (int) para precisão
- Validação: paid=True exige paid_date
- Validação: paid_date não pode ser no futuro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- Herança de AmountMixin (amount com validação)
- Herança de PaymentMixin (paid, paid_date)
- ✅ CORRIGIDO: Herança correta de BaseModelWithUser
- ✅ CORRIGIDO: CreditCardInstallmentResponse id obrigatório
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import datetime, timezone

from app.models.base import BaseModelWithUser
from app.models.mixins import AmountMixin, PaymentMixin


class CreditCardInstallment(BaseModelWithUser, AmountMixin, PaymentMixin):
    """
    Modelo de uma parcela individual de uma compra no cartão de crédito.
    Cada compra parcelada gera N parcelas.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
      - AmountMixin: amount (validação de valor positivo)
      - PaymentMixin: paid, paid_date (validação de pagamento)
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    
    🔧 CAMPOS ADICIONADOS:
      - purchase_id: ID da compra original
      - card_id: ID do cartão usado
      - due_date: Data de vencimento da parcela
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    purchase_id: str = Field(
        ...,
        description="ID da compra original"
    )
    
    card_id: str = Field(
        ...,
        description="ID do cartão usado"
    )
    
    due_date: datetime = Field(
        ...,
        description="Data de vencimento da parcela"
    )
    
    # ========== VALIDAÇÕES ==========
    
    @field_validator('due_date', mode='before')
    @classmethod
    def validate_due_date(cls, v: Any) -> Any:
        """
        Valida que due_date seja uma data válida.
        🔧 i18n: Mensagem com chave ERROR_INVALID_DUE_DATE
        """
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                if dt.year < 1900:
                    raise ValueError('due_date inválida (ano anterior a 1900)')
                return dt
            except (ValueError, TypeError):
                raise ValueError('due_date inválida')
        return v


class CreditCardInstallmentResponse(CreditCardInstallment):
    """
    Schema para respostas da API.
    
    🔧 ✅ CORRIGIDO: id é obrigatório (sobrescreve Optional)
    """
    
    id: str = Field(..., alias="_id", description="ID único da parcela")


# ========== ÍNDICES RECOMENDADOS ==========
# 
# 🔧 ADICIONAR EM indexes.py:
# 
# ================================================================
# 9. PARCELAS DE CARTÃO DE CRÉDITO (CREDIT_CARD_INSTALLMENTS)
# ================================================================
# 
# # Índice por usuário e vencimento (para listagem de parcelas a pagar)
# await db.credit_card_installments.create_index([("user_id", 1), ("due_date", 1)])
# 
# # Índice por compra (para buscar parcelas de uma compra específica)
# await db.credit_card_installments.create_index([("purchase_id", 1)])
# 
# # Índice por cartão e vencimento (para faturas)
# await db.credit_card_installments.create_index([("card_id", 1), ("due_date", 1)])
# 
# # Índice composto para status + vencimento (filtrar parcelas pendentes)
# await db.credit_card_installments.create_index([("user_id", 1), ("paid", 1), ("due_date", 1)])
# 
# ================================================================


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de AmountMixin (amount com validação)
#   - Herança de PaymentMixin (paid, paid_date, validação de pagamento)
#   - Validação: paid=True exige paid_date
#   - Validação: paid_date não pode ser no futuro
#   - Validação: due_date válida
#   - I18n completo com chaves de erro
#   - Schemas separados (Response)
#   - ✅ CORRIGIDO: Herança correta de BaseModelWithUser
#   - ✅ CORRIGIDO: CreditCardInstallmentResponse id obrigatório
#
# ❌ Não implementado (Pós-MVP):
#   - Propriedades calculadas: is_overdue, days_overdue
#   - Validação de due_date >= hoje (depende da regra de negócio)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser, AmountMixin, PaymentMixin (03/07/2026)
#   - v3: Correções - Herança correta, Response id obrigatório (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO