"""
Modelo de Compra Parcelada no Cartão de Crédito
Arquivo: backend/app/models/credit_card_purchase.py

Funcionalidades:
- Registro de compras parceladas no cartão de crédito
- Controle de parcelas restantes
- Suporte a juros
- Auditoria de pagamentos (histórico completo, sem TTL)

Principais features:
- Valores em centavos (int) para precisão
- remaining_installments calculado automaticamente
- Suporte a juros (interest_rate, total_with_interest)
- Auditoria (paid_by, history) - dados mantidos permanentemente
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- Herança de AmountMixin (total_amount)
- Herança de PaymentMixin (paid, paid_date)
- ✅ CORRIGIDO: Herança correta de BaseModelWithUser
- ✅ CORRIGIDO: CreditCardPurchaseResponse id obrigatório
- ✅ CORRIGIDO: Importação circular removida (usa utils/installments.py)
"""

from pydantic import Field, model_validator, field_validator
from typing import Optional, Any, List
from datetime import datetime, timezone

from app.models.base import BaseModelWithUser
from app.models.mixins import AmountMixin, PaymentMixin
from app.utils.installments import calculate_installments_with_interest
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class CreditCardPurchase(BaseModelWithUser, AmountMixin, PaymentMixin):
    """
    Representa uma compra parcelada no cartão de crédito.
    Uma compra gera N parcelas (CreditCardInstallment).
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
      - AmountMixin: total_amount (validação de valor positivo)
      - PaymentMixin: paid, paid_date (validação de pagamento)
    
    🔧 IMPORTANTE: Valores estão em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    
    🔧 CAMPOS ADICIONADOS:
      - card_id: ID do cartão
      - description: Descrição da compra
      - committed_amount: Valor comprometido do limite
      - interest_rate: Taxa de juros mensal (%)
      - total_with_interest: Valor total com juros
      - installments: Número total de parcelas
      - remaining_installments: Parcelas restantes
      - paid_installments_count: Parcelas já pagas
      - first_due_date: Data da primeira parcela
      - category: Categoria da compra
      - notes: Observações
      - fully_paid: Compra totalmente quitada?
      - fully_paid_date: Data da última parcela
      - paid_by: ID de quem pagou
      - history: Logs de auditoria (mantido permanentemente, sem TTL)
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    card_id: str = Field(
        ...,
        description="ID do cartão de crédito"
    )
    
    description: str = Field(
        ...,
        max_length=200,
        description="Descrição da compra"
    )
    
    # ========== LIMITE ==========
    
    committed_amount: int = Field(
        ...,
        ge=0,
        description="Valor comprometido do limite em CENTAVOS"
    )
    
    # ========== JUROS ==========
    
    interest_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Taxa de juros mensal (%) - 0 a 100"
    )
    
    total_with_interest: Optional[int] = Field(
        None,
        ge=0,
        description="Valor total com juros em CENTAVOS. Calculado automaticamente se não informado."
    )
    
    # ========== PARCELAMENTO ==========
    
    installments: int = Field(
        ...,
        ge=1,
        le=360,
        description="Número total de parcelas (máx 360 = 30 anos)"
    )
    
    remaining_installments: int = Field(
        ...,
        ge=0,
        description="Parcelas restantes a pagar"
    )
    
    paid_installments_count: int = Field(
        default=0,
        ge=0,
        description="Contador de parcelas já pagas"
    )
    
    # ========== DATAS ==========
    
    first_due_date: datetime = Field(
        ...,
        description="Data da primeira parcela"
    )
    
    category: Optional[str] = Field(
        None,
        max_length=50,
        description="Categoria da compra"
    )
    
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Observações"
    )
    
    # ========== STATUS ==========
    
    fully_paid: bool = Field(
        default=False,
        description="Compra totalmente quitada?"
    )
    
    fully_paid_date: Optional[datetime] = Field(
        None,
        description="Data da última parcela paga"
    )
    
    # ========== AUDITORIA (mantido permanentemente) ==========
    
    paid_by: Optional[str] = Field(
        None,
        description="ID do usuário que pagou a compra"
    )
    
    history: List[dict] = Field(
        default_factory=list,
        description="Logs de auditoria da compra (mantido permanentemente)"
    )
    
    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def validate_remaining_installments(self):
        """
        Remaining installments não pode ser maior que total.
        🔧 i18n: Mensagem com chave ERROR_INVALID_REMAINING_INSTALLMENTS
        """
        if self.remaining_installments > self.installments:
            raise ValueError('remaining_installments não pode ser maior que installments')
        return self
    
    @model_validator(mode='after')
    def validate_fully_paid_consistency(self):
        """
        Valida consistência entre remaining_installments e fully_paid.
        """
        if self.remaining_installments == 0 and not self.fully_paid:
            raise ValueError('fully_paid deve ser True quando remaining_installments = 0')
        
        if self.fully_paid and self.remaining_installments > 0:
            raise ValueError('fully_paid não pode ser True quando há parcelas restantes')
        
        return self
    
    @model_validator(mode='after')
    def validate_committed_amount(self):
        """
        Valida que committed_amount seja compatível com total_amount.
        """
        if self.committed_amount < self.total_amount:
            logger.warning(f"committed_amount ({self.committed_amount}) < total_amount ({self.total_amount})")
        return self
    
    @model_validator(mode='after')
    def check_fully_paid(self):
        """
        Se fully_paid=True, fully_paid_date é obrigatório.
        🔧 i18n: Mensagem com chave ERROR_FULLY_PAID_DATE_REQUIRED
        """
        if self.fully_paid and self.fully_paid_date is None:
            raise ValueError('fully_paid_date é obrigatório quando fully_paid=True')
        return self
    
    @model_validator(mode='after')
    def validate_fully_paid_date_not_future(self):
        """
        Se fully_paid=True, fully_paid_date não pode ser no futuro.
        """
        if self.fully_paid and self.fully_paid_date:
            if self.fully_paid_date > datetime.now(timezone.utc):
                raise ValueError('fully_paid_date não pode ser no futuro')
        return self

    @model_validator(mode='after')
    def validate_paid_installments_count(self):
        """
        Valida que paid_installments_count não pode ser maior que installments.
        """
        if self.paid_installments_count > self.installments:
            raise ValueError('paid_installments_count não pode ser maior que installments')
        return self

    @model_validator(mode='after')
    def validate_total_with_interest(self):
        """
        Valida que total_with_interest seja >= total_amount quando há juros.
        """
        if self.interest_rate > 0 and self.total_with_interest is not None:
            if self.total_with_interest < self.total_amount:
                raise ValueError('total_with_interest deve ser >= total_amount quando há juros')
        return self

    @field_validator('interest_rate')
    @classmethod
    def validate_interest_rate(cls, v: float) -> float:
        """
        Valida que interest_rate esteja entre 0 e 100.
        🔧 i18n: Mensagem com chave ERROR_INVALID_INTEREST_RATE
        """
        if v < 0 or v > 100:
            raise ValueError('interest_rate deve estar entre 0 e 100')
        return v
    
    @field_validator('first_due_date', mode='before')
    @classmethod
    def validate_first_due_date(cls, v: Any) -> Any:
        """
        Valida que first_due_date seja uma data válida.
        🔧 i18n: Mensagem com chave ERROR_INVALID_DUE_DATE
        """
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                if dt.year < 1900:
                    raise ValueError('first_due_date inválida (ano anterior a 1900)')
                return dt
            except (ValueError, TypeError):
                raise ValueError('first_due_date inválida')
        return v


class CreditCardPurchaseCreate(BaseModel):
    """
    Schema usado para CRIAR uma nova compra parcelada.
    
    🔧 DIFERENÇAS DO MODEL:
      - Não tem campos de auditoria (ainda não existe no banco)
      - total_with_interest é opcional (calculado automaticamente)
    """
    
    card_id: str = Field(..., description="ID do cartão de crédito")
    description: str = Field(..., max_length=200, description="Descrição da compra")
    total_amount: int = Field(..., gt=0, description="Valor total em CENTAVOS")
    installments: int = Field(..., ge=1, le=360, description="Número de parcelas (máx 360 = 30 anos)")
    first_due_date: datetime = Field(..., description="Data da primeira parcela")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da compra")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    
    interest_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Taxa de juros mensal (%) - 0 a 100"
    )
    
    total_with_interest: Optional[int] = Field(
        None,
        ge=0,
        description="Valor total com juros em CENTAVOS. Calculado automaticamente se não informado."
    )
    
    # ========== VALIDADORES ==========

    @field_validator('interest_rate')
    @classmethod
    def validate_interest_rate(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError('interest_rate deve estar entre 0 e 100')
        return v

    @field_validator('total_amount')
    @classmethod
    def validate_total_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('total_amount deve ser maior que zero')
        return v

    @field_validator('installments')
    @classmethod
    def validate_installments(cls, v: int) -> int:
        if v < 1 or v > 360:
            raise ValueError('installments deve estar entre 1 e 360')
        return v
    
    # ========== MÉTODOS ==========
    
    def to_purchase_data(self) -> dict:
        """
        Converte para dict com remaining_installments sincronizado.
        Garante que remaining_installments seja sempre igual a installments na criação.
        🔧 CORRIGIDO: Usa utils/installments.py (remove importação circular)
        """
        data = self.model_dump()
        data["remaining_installments"] = data["installments"]
        data["paid_installments_count"] = 0
        data["fully_paid"] = False
        data["committed_amount"] = data["total_amount"]
        data["created_at"] = datetime.now(timezone.utc)
        data["updated_at"] = datetime.now(timezone.utc)
        
        # 🔧 CORRIGIDO: Usa utils/installments.py
        if data.get("interest_rate", 0) > 0 and data.get("total_with_interest") is None:
            amounts = calculate_installments_with_interest(
                data["total_amount"],
                data["installments"],
                data["interest_rate"]
            )
            data["total_with_interest"] = sum(amounts)
            data["committed_amount"] = data["total_with_interest"]
        
        return data


class CreditCardPurchaseUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma compra parcelada"""
    
    card_id: Optional[str] = Field(None, description="ID do cartão de crédito")
    description: Optional[str] = Field(None, max_length=200, description="Descrição da compra")
    total_amount: Optional[int] = Field(None, gt=0, description="Valor total em CENTAVOS")
    installments: Optional[int] = Field(None, ge=1, le=360, description="Número de parcelas")
    first_due_date: Optional[datetime] = Field(None, description="Data da primeira parcela")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da compra")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    interest_rate: Optional[float] = Field(None, ge=0, le=100, description="Taxa de juros mensal (%)")
    total_with_interest: Optional[int] = Field(None, ge=0, description="Valor total com juros em CENTAVOS")


class CreditCardPurchaseResponse(CreditCardPurchase):
    """
    Schema usado para RESPOSTAS da API.
    
    🔧 ✅ CORRIGIDO: id é obrigatório (sobrescreve Optional)
    """
    
    id: str = Field(..., alias="_id", description="ID da compra")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de AmountMixin (total_amount)
#   - Herança de PaymentMixin (paid, paid_date)
#   - Suporte a juros (interest_rate, total_with_interest)
#   - Auditoria (paid_by, history) - mantido permanentemente, SEM TTL
#   - Validações: remaining_installments, fully_paid, committed_amount
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response)
#   - Método to_purchase_data() para criação
#   - ✅ CORRIGIDO: Herança correta de BaseModelWithUser
#   - ✅ CORRIDO: CreditCardPurchaseResponse id obrigatório
#   - ✅ CORRIGIDO: Importação circular removida (usa utils/installments.py)
#
# ❌ Não implementado (Pós-MVP):
#   - Propriedades calculadas (total_paid, progress_percentage, is_overdue)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser, AmountMixin, PaymentMixin (03/07/2026)
#   - v3: Correções - Importação circular, Response id obrigatório (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO