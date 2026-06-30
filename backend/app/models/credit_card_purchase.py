"""
Modelo de Compra Parcelada no Cartão de Crédito
Arquivo: backend/app/models/credit_card_purchase.py

🔧 CORRIGIDO (v3 - FINAL):
- total_amount agora é int (centavos)
- Adicionado committed_amount (controle de limite)
- Adicionado remaining_installments
- Limitado parcelas a 360 (30 anos)
- 🔧 NOVO: Validação de committed_amount
- 🔧 NOVO: Validação de consistência entre remaining_installments e fully_paid
- 🔧 CORRIGIDO: convert_objectid usa função importada
- 🔧 NOVO: Validação de first_due_date
- 🔧 NOVO: Método touch() para updated_at
- 🔧 NOVO: Método to_purchase_data() para sincronizar remaining_installments
- 🔧 i18n: Mensagens de erro documentadas com chaves para referência

🆕 NOVOS CAMPOS (v3):
- 🆕 interest_rate: Taxa de juros mensal (%) - 0 a 100
- 🆕 total_with_interest: Valor total com juros (em centavos)
- 🆕 paid_by: Quem pagou a compra (auditoria)
- 🆕 history: Logs de auditoria
- 🆕 paid_installments_count: Contador de parcelas pagas

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_INVALID_REMAINING_INSTALLMENTS
   - ERROR_FULLY_PAID_DATE_REQUIRED
   - ERROR_FULLY_PAID_DATE_FUTURE
   - ERROR_INVALID_DUE_DATE
   - ERROR_INVALID_INTEREST_RATE
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional, Any, List
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


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
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    card_id: str = Field(..., description="ID do cartão de crédito")
    description: str = Field(..., max_length=200, description="Descrição da compra")
    
    # 🔧 CORRIGIDO: float → int (centavos)
    total_amount: int = Field(..., gt=0, description="Valor total em CENTAVOS (ex: 15050 = R$150,50)")
    
    # 🔧 NOVO: Controle de limite do cartão
    committed_amount: int = Field(..., ge=0, description="Valor comprometido do limite em CENTAVOS")
    
    # 🆕 NOVO: Suporte a juros
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
    
    # Parcelamento
    installments: int = Field(..., ge=1, le=360, description="Número total de parcelas (máx 360 = 30 anos)")
    remaining_installments: int = Field(..., ge=0, description="Parcelas restantes a pagar")
    paid_installments_count: int = Field(
        default=0,
        ge=0,
        description="🆕 Contador de parcelas já pagas"
    )
    
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
    
    # 🆕 Auditoria
    paid_by: Optional[str] = Field(None, description="🆕 ID do usuário que pagou a compra")
    history: List[dict] = Field(
        default_factory=list,
        description="🆕 Logs de auditoria da compra"
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
        🔧 CORRIGIDO: Valida consistência entre remaining_installments e fully_paid.
        """
        if self.remaining_installments == 0 and not self.fully_paid:
            raise ValueError('fully_paid deve ser True quando remaining_installments = 0')
        
        if self.fully_paid and self.remaining_installments > 0:
            raise ValueError('fully_paid não pode ser True quando há parcelas restantes')
        
        return self
    
    @model_validator(mode='after')
    def validate_committed_amount(self):
        """
        🔧 CORRIGIDO: Valida que committed_amount seja compatível com total_amount.
        """
        if self.committed_amount < self.total_amount:
            # committed_amount pode ser menor se o limite não cobre todo o valor
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
        🔧 NOVO: Validação para evitar dados inconsistentes.
        """
        if self.fully_paid and self.fully_paid_date:
            if self.fully_paid_date > datetime.now(timezone.utc):
                raise ValueError('fully_paid_date não pode ser no futuro')
        return self

    @model_validator(mode='after')
    def validate_paid_installments_count(self):
        """
        🆕 Valida que paid_installments_count não pode ser maior que installments.
        """
        if self.paid_installments_count > self.installments:
            raise ValueError('paid_installments_count não pode ser maior que installments')
        return self

    @model_validator(mode='after')
    def validate_total_with_interest(self):
        """
        🆕 Valida que total_with_interest seja >= total_amount quando há juros.
        """
        if self.interest_rate > 0 and self.total_with_interest is not None:
            if self.total_with_interest < self.total_amount:
                raise ValueError('total_with_interest deve ser >= total_amount quando há juros')
        return self

    # ========== VALIDAÇÃO DE CAMPOS ==========

    @field_validator('first_due_date', mode='before')
    @classmethod
    def validate_first_due_date(cls, v: Any) -> Any:
        """
        🔧 CORRIGIDO: Valida que first_due_date seja uma data válida.
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

    @field_validator('interest_rate')
    @classmethod
    def validate_interest_rate(cls, v: float) -> float:
        """
        🆕 Valida que interest_rate esteja entre 0 e 100.
        🔧 i18n: Mensagem com chave ERROR_INVALID_INTEREST_RATE
        """
        if v < 0 or v > 100:
            raise ValueError('interest_rate deve estar entre 0 e 100')
        return v

    # ========== MÉTODOS AUXILIARES ==========

    def touch(self) -> 'CreditCardPurchase':
        """
        🔧 NOVO: Atualiza o timestamp de modificação.
        Uso: purchase.touch() antes de salvar no banco.
        """
        self.updated_at = datetime.now(timezone.utc)
        return self

    def calculate_total_with_interest(self) -> int:
        """
        🆕 Calcula o valor total com juros baseado na taxa atual.
        Se não houver juros, retorna o total_amount.
        """
        if self.interest_rate == 0:
            return self.total_amount
        
        # Importa a função de cálculo de parcelas com juros
        # (evita import circular)
        from app.routes.credit_card_purchases import calculate_installments_with_interest
        
        amounts = calculate_installments_with_interest(
            self.total_amount,
            self.installments,
            self.interest_rate
        )
        return sum(amounts)

    # ========== CONVERSÃO DE OBJECTID ==========

    @model_validator(mode='before')
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """
        🔧 CORRIGIDO: Converte ObjectId para string (usando função importada).
        """
        if isinstance(data, CreditCardPurchase):
            return data
        
        return convert_objectid_to_str(data)


class CreditCardPurchaseCreate(BaseModel):
    """Schema usado para CRIAR uma nova compra parcelada"""
    card_id: str = Field(..., description="ID do cartão de crédito")
    description: str = Field(..., max_length=200, description="Descrição da compra")
    total_amount: int = Field(..., gt=0, description="Valor total em CENTAVOS (ex: 15050 = R$150,50)")
    installments: int = Field(..., ge=1, le=360, description="Número de parcelas (máx 360 = 30 anos)")
    first_due_date: datetime = Field(..., description="Data da primeira parcela")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da compra")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    
    # 🆕 NOVO: Suporte a juros
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
        """🆕 Valida que interest_rate esteja entre 0 e 100."""
        if v < 0 or v > 100:
            raise ValueError('interest_rate deve estar entre 0 e 100')
        return v

    @field_validator('total_amount')
    @classmethod
    def validate_total_amount(cls, v: int) -> int:
        """Valida que total_amount seja maior que zero."""
        if v <= 0:
            raise ValueError('total_amount deve ser maior que zero')
        return v

    @field_validator('installments')
    @classmethod
    def validate_installments(cls, v: int) -> int:
        """Valida que installments esteja entre 1 e 360."""
        if v < 1 or v > 360:
            raise ValueError('installments deve estar entre 1 e 360')
        return v

    # ========== MÉTODOS ==========
    
    def to_purchase_data(self) -> dict:
        """
        🔧 NOVO: Converte para dict com remaining_installments sincronizado.
        Garante que remaining_installments seja sempre igual a installments na criação.
        🆕 Calcula total_with_interest se não informado.
        """
        data = self.model_dump()
        data["remaining_installments"] = data["installments"]
        data["paid_installments_count"] = 0
        data["fully_paid"] = False
        data["committed_amount"] = data["total_amount"]
        data["created_at"] = datetime.now(timezone.utc)
        data["updated_at"] = datetime.now(timezone.utc)
        
        # 🆕 Calcula total_with_interest se não informado
        if data.get("interest_rate", 0) > 0 and data.get("total_with_interest") is None:
            from app.routes.credit_card_purchases import calculate_installments_with_interest
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
    
    # 🆕 NOVO: Suporte a juros
    interest_rate: Optional[float] = Field(None, ge=0, le=100, description="Taxa de juros mensal (%)")
    total_with_interest: Optional[int] = Field(None, ge=0, description="Valor total com juros em CENTAVOS")


class CreditCardPurchaseResponse(CreditCardPurchase):
    """Schema usado para RESPOSTAS da API"""
    pass


# ========== PROPRIEDADES CALCULADAS (PÓS-MVP) ==========
#
# @property
# def total_paid(self) -> int:
#     """Valor total já pago em centavos."""
#     if self.fully_paid:
#         return self.total_amount
#     return 0
#
# @property
# def progress_percentage(self) -> float:
#     """Percentual pago da compra."""
#     if self.total_amount == 0:
#         return 100.0
#     return (self.total_paid / self.total_amount) * 100
#
# @property
# def is_overdue(self) -> bool:
#     """Verifica se a compra tem parcelas vencidas."""
#     if self.fully_paid:
#         return False
#     return False


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. total_amount: float → int (centavos) - consistente com to_cents()
2. 🔧 NOVO: committed_amount (controle de limite do cartão)
3. 🔧 NOVO: remaining_installments (parcelas restantes)
4. 🔧 CORRIGIDO: installments le=999 → le=360 (30 anos)
5. 🔧 NOVO: Validação de committed_amount (com warning)
6. 🔧 NOVO: Validação de consistência entre remaining_installments e fully_paid
7. 🔧 CORRIGIDO: convert_objectid usa função importada
8. 🔧 NOVO: Validação de first_due_date
9. 🔧 NOVO: Método touch() para updated_at
10. 🔧 NOVO: Método to_purchase_data() para sincronizar remaining_installments
11. 🔧 i18n: Mensagens de erro documentadas com chaves para referência
12. 🆕 NOVO: interest_rate (taxa de juros mensal)
13. 🆕 NOVO: total_with_interest (valor total com juros)
14. 🆕 NOVO: paid_by (auditoria - quem pagou)
15. 🆕 NOVO: history (logs de auditoria)
16. 🆕 NOVO: paid_installments_count (contador de parcelas pagas)
17. 🆕 NOVO: Validação de interest_rate (0-100%)
18. 🆕 NOVO: Validação de total_with_interest
19. 🆕 NOVO: Validação de paid_installments_count

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_INVALID_REMAINING_INSTALLMENTS
   - ERROR_FULLY_PAID_DATE_REQUIRED
   - ERROR_FULLY_PAID_DATE_FUTURE
   - ERROR_INVALID_DUE_DATE
   - ERROR_INVALID_INTEREST_RATE

✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int + i18n + juros)
================================================================================
"""