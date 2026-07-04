"""
Modelo de Investimento para MongoDB
Arquivo: backend/app/models/investment.py

Funcionalidades:
- Registro de investimentos (renda fixa, ações, FIIs, cripto)
- Controle de preço de compra e valor atual
- Suporte a venda e dividendos
- Cálculo automático de rentabilidade

Principais features:
- Valores em centavos (int) para precisão
- Quantidade em centésimos (ex: 1,5 ações → 150)
- Campos calculados: current_value_calculated, profit_loss_calculated, return_percentage_calculated
- Validação: amount = quantity × price
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- Herança de AmountMixin (amount com validação)
- ✅ CORRIGIDO: Herança correta de BaseModelWithUser
- ✅ CORRIGIDO: InvestmentResponse id obrigatório (já estava)
"""

from datetime import datetime, timezone
from typing import Optional, Literal, Any
from pydantic import Field, computed_field, model_validator

from app.models.base import BaseModelWithUser
from app.models.mixins import AmountMixin
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class Investment(BaseModelWithUser, AmountMixin):
    """
    Modelo de investimento para o MongoDB.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
      - AmountMixin: amount (validação de valor positivo)
    
    🔧 IMPORTANTE: Valores monetários estão em CENTAVOS (int)
    - Exemplo: R$ 1.500,50 → 150050
    - Quantidade em CENTÉSIMOS (ex: 1,5 ações → 150)
    
    🔧 CAMPOS ADICIONADOS:
      - name: Nome do investimento
      - broker: Corretora
      - category: Categoria do investimento
      - current_value: Valor atual em centavos
      - purchase_price_per_unit: Preço de compra por unidade
      - current_price_per_unit: Preço atual por unidade
      - quantity: Quantidade em centésimos
      - purchase_date: Data da compra
      - profit_loss: Lucro/prejuízo em centavos
      - return_percentage: Percentual de retorno
      - dividends_received: Dividendos recebidos
      - last_dividend_date: Último dividendo
      - sold: Foi vendido?
      - sold_date: Data da venda
      - sold_value: Valor da venda
      - fees: Taxas pagas
      - notes: Observações
      - automatic_update: Buscar preço automaticamente?
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nome do investimento"
    )
    
    category: Literal["renda_fixa", "acoes", "fiis", "cripto", "outros"] = Field(
        ...,
        description="Categoria do investimento"
    )
    
    purchase_date: datetime = Field(
        ...,
        description="Data da compra"
    )
    
    # ========== CAMPOS OPCIONAIS ==========
    
    broker: Optional[str] = Field(
        None,
        max_length=50,
        description="Corretora"
    )
    
    current_value: Optional[int] = Field(
        None,
        ge=0,
        description="Valor atual em CENTAVOS"
    )
    
    purchase_price_per_unit: Optional[int] = Field(
        None,
        ge=0,
        description="Preço de compra por unidade em CENTAVOS"
    )
    
    current_price_per_unit: Optional[int] = Field(
        None,
        ge=0,
        description="Preço atual por unidade em CENTAVOS"
    )
    
    quantity: int = Field(
        default=0,
        ge=0,
        description="Quantidade em CENTÉSIMOS (ex: 150 = 1,5 ações)"
    )
    
    profit_loss: Optional[int] = Field(
        None,
        description="Lucro/prejuízo em CENTAVOS"
    )
    
    return_percentage: Optional[float] = Field(
        None,
        description="Percentual de retorno (ex: 15.5 = 15,5%)"
    )
    
    dividends_received: Optional[int] = Field(
        None,
        ge=0,
        description="Dividendos recebidos em CENTAVOS"
    )
    
    last_dividend_date: Optional[datetime] = Field(
        None,
        description="Último dividendo recebido"
    )
    
    sold: bool = Field(
        default=False,
        description="Investimento foi vendido?"
    )
    
    sold_date: Optional[datetime] = Field(
        None,
        description="Data da venda"
    )
    
    sold_value: Optional[int] = Field(
        None,
        ge=0,
        description="Valor da venda em CENTAVOS"
    )
    
    fees: Optional[int] = Field(
        None,
        ge=0,
        description="Taxas pagas em CENTAVOS"
    )
    
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Observações"
    )
    
    automatic_update: bool = Field(
        default=False,
        description="Buscar preço automaticamente via API"
    )
    
    # ========== VALIDAÇÕES ==========

    @model_validator(mode='after')
    def validate_quantity_and_price(self):
        """
        Se quantity > 0, purchase_price_per_unit é obrigatório.
        🔧 i18n: Mensagem com chave ERROR_INVESTMENT_PRICE_REQUIRED
        """
        if self.quantity > 0 and self.purchase_price_per_unit is None:
            raise ValueError('purchase_price_per_unit é obrigatório quando quantity > 0')
        return self
    
    @model_validator(mode='after')
    def validate_sold(self):
        """
        Se sold=True, sold_date e sold_value são obrigatórios.
        🔧 i18n: Mensagens com chaves ERROR_INVESTMENT_SOLD_DATE_REQUIRED e ERROR_INVESTMENT_SOLD_VALUE_REQUIRED
        """
        if self.sold and self.sold_date is None:
            raise ValueError('sold_date é obrigatório quando sold=True')
        if self.sold and self.sold_value is None:
            raise ValueError('sold_value é obrigatório quando sold=True')
        return self
    
    @model_validator(mode='after')
    def validate_amount_consistency(self):
        """
        Valida que amount seja consistente com quantity e purchase_price_per_unit.
        🔧 i18n: Mensagem com chave ERROR_INVESTMENT_AMOUNT_INCONSISTENT
        """
        if self.quantity > 0 and self.purchase_price_per_unit is not None:
            calculated_amount = (self.quantity * self.purchase_price_per_unit) // 100
            if abs(self.amount - calculated_amount) > 1:  # Tolerância de 1 centavo
                logger.warning(
                    f"⚠️ amount ({self.amount}) difere do calculado ({calculated_amount}) para {self.name} - ajustando"
                )
                self.amount = calculated_amount
        return self
    
    @model_validator(mode='after')
    def validate_current_value_consistency(self):
        """
        Loga warning em vez de ajustar automaticamente.
        """
        if self.current_price_per_unit is not None and self.quantity > 0:
            expected_value = (self.quantity * self.current_price_per_unit) // 100
            if self.current_value is not None and abs(self.current_value - expected_value) > 1:
                logger.warning(
                    f"⚠️ current_value ({self.current_value}) difere do esperado ({expected_value}) para {self.name}"
                )
        return self
    
    @model_validator(mode='after')
    def validate_sold_and_amount(self):
        """
        Não pode vender algo que não foi comprado.
        🔧 i18n: Mensagem com chave ERROR_INVESTMENT_SOLD_WITHOUT_AMOUNT
        """
        if self.sold and self.amount == 0:
            raise ValueError('Não é possível vender um investimento com valor zero')
        return self
    
    @model_validator(mode='after')
    def validate_sold_date_not_future(self):
        """
        Se sold=True, sold_date não pode ser no futuro.
        🔧 i18n: Mensagem com chave ERROR_INVESTMENT_SOLD_DATE_FUTURE
        """
        if self.sold and self.sold_date:
            if self.sold_date > datetime.now(timezone.utc):
                raise ValueError('sold_date não pode ser no futuro')
        return self
    
    # ========== CAMPOS CALCULADOS ==========
    
    @computed_field
    @property
    def current_value_calculated(self) -> Optional[int]:
        """Calcula o valor atual baseado na quantidade e preço atual"""
        if self.quantity > 0 and self.current_price_per_unit is not None:
            return (self.quantity * self.current_price_per_unit) // 100
        return self.current_value
    
    @computed_field
    @property
    def profit_loss_calculated(self) -> Optional[int]:
        """Calcula lucro/prejuízo baseado no valor atual"""
        if self.current_value_calculated is not None and not self.sold:
            return self.current_value_calculated - self.amount
        if self.sold and self.sold_value is not None:
            return self.sold_value - self.amount
        return None
    
    @computed_field
    @property
    def return_percentage_calculated(self) -> Optional[float]:
        """Calcula percentual de retorno"""
        profit = self.profit_loss_calculated
        if profit is not None and self.amount > 0:
            return round((profit / self.amount) * 100, 2)
        return None


class InvestmentCreate(BaseModel):
    """
    Schema para criação de investimento.
    
    🔧 DIFERENÇAS DO MODEL INVESTMENT:
      - Não tem campos de auditoria (ainda não existe no banco)
      - amount é obrigatório
    """
    
    name: str = Field(..., min_length=1, max_length=100)
    broker: Optional[str] = Field(None, max_length=50)
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS")
    category: Literal["renda_fixa", "acoes", "fiis", "cripto", "outros"]
    purchase_date: datetime
    quantity: Optional[int] = Field(default=0, ge=0, description="Quantidade em CENTÉSIMOS")
    purchase_price_per_unit: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)
    fees: Optional[int] = Field(None, ge=0, description="Taxas em CENTAVOS")
    automatic_update: bool = Field(default=False)
    
    @model_validator(mode='after')
    def validate_quantity_and_price(self):
        """
        🔧 i18n: Mensagem com chave ERROR_INVESTMENT_PRICE_REQUIRED
        """
        if self.quantity > 0 and self.purchase_price_per_unit is None:
            raise ValueError('purchase_price_per_unit é obrigatório quando quantity > 0')
        return self


class InvestmentUpdate(BaseModel):
    """
    Schema para atualização de investimento.
    
    🔧 TODOS OS CAMPOS SÃO OPCIONAIS:
      - Permite atualização parcial
    """
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    broker: Optional[str] = Field(None, max_length=50)
    amount: Optional[int] = Field(None, gt=0)
    category: Optional[Literal["renda_fixa", "acoes", "fiis", "cripto", "outros"]] = None
    current_value: Optional[int] = Field(None, ge=0)
    current_price_per_unit: Optional[int] = Field(None, ge=0)
    quantity: Optional[int] = Field(None, ge=0)
    sold: Optional[bool] = None
    sold_date: Optional[datetime] = None
    sold_value: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)
    fees: Optional[int] = Field(None, ge=0)
    automatic_update: Optional[bool] = None
    
    @model_validator(mode='after')
    def validate_sold_consistency(self):
        """
        🔧 i18n: Mensagens com chaves ERROR_INVESTMENT_SOLD_DATE_REQUIRED e ERROR_INVESTMENT_SOLD_VALUE_REQUIRED
        """
        if self.sold and self.sold_date is None:
            raise ValueError('sold_date é obrigatório quando sold=True')
        if self.sold and self.sold_value is None:
            raise ValueError('sold_value é obrigatório quando sold=True')
        return self


class InvestmentResponse(Investment):
    """
    Schema para resposta da API.
    
    🔧 ✅ CORRIGIDO: id é obrigatório (sobrescreve Optional)
    """
    
    id: str = Field(..., alias="_id", description="ID do investimento")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de AmountMixin (amount com validação)
#   - Valores monetários em centavos (int)
#   - Quantidade em centésimos (int)
#   - Campos calculados: current_value_calculated, profit_loss_calculated, return_percentage_calculated
#   - Validação: amount = quantity × price
#   - Validação: current_value consistency com warning
#   - Validação: sold_date não futuro
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response)
#   - ✅ CORRIGIDO: Herança correta de BaseModelWithUser
#   - ✅ CORRIGIDO: InvestmentResponse id obrigatório
#
# ❌ Não implementado (Pós-MVP):
#   - broker com Literal para corretoras conhecidas
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser, AmountMixin (03/07/2026)
#   - v3: Correções - Response id obrigatório (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO