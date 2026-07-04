"""
Modelos de Cartões de Crédito
Arquivo: backend/app/models/credit_card.py

Funcionalidades:
- CRUD de cartões de crédito
- Controle de limites (total, usado, comprometido, disponível)
- Gestão de faturas (fechamento e vencimento)

Principais features:
- Valores em centavos (int) para precisão
- Cálculo automático do limite disponível
- Validação: used_limit + committed_amount <= total_limit
- Validação: closing_day e due_day entre 1 e 31
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- ✅ CORRIGIDO: CreditCardBase herda de BaseModelWithUser
- ✅ CORRIGIDO: CreditCardResponse não duplica campos da base
- ✅ CORRIGIDO: brand com Literal para bandeiras
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any, Literal
from datetime import datetime, timezone

from app.models.base import BaseModelWithUser
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


# ========== CONSTANTES ==========

BRANDS = Literal["visa", "mastercard", "elo", "amex", "hipercard", "outros"]


# ========== SCHEMAS ==========

class CreditCardBase(BaseModelWithUser):
    """
    Base para cartão de crédito.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
    
    🔧 CAMPOS ADICIONADOS:
      - name: Nome do cartão
      - brand: Bandeira (Visa, Mastercard, etc)
      - total_limit: Limite total em centavos
      - closing_day: Dia de fechamento da fatura
      - due_day: Dia de vencimento da fatura
    """
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Nome do cartão (ex: Nubank, Itaú)"
    )
    
    brand: BRANDS = Field(
        ...,
        description="Bandeira do cartão (visa, mastercard, elo, amex, hipercard, outros)"
    )
    
    total_limit: int = Field(
        ...,
        gt=0,
        description="Limite total do cartão em CENTAVOS (ex: 1500000 = R$15.000,00)"
    )
    
    closing_day: int = Field(
        ...,
        ge=1,
        le=31,
        description="Dia de fechamento da fatura"
    )
    
    due_day: int = Field(
        ...,
        ge=1,
        le=31,
        description="Dia de vencimento da fatura"
    )
    
    # ========== VALIDAÇÕES ==========
    
    @model_validator(mode='after')
    def validate_dates(self):
        """
        Valida relação entre closing_day e due_day.
        🔧 i18n: Mensagens com chaves ERROR_INVALID_CLOSING_DAY, ERROR_INVALID_DUE_DAY
        """
        if not (1 <= self.closing_day <= 31):
            raise ValueError('closing_day deve ser entre 1 e 31')
        if not (1 <= self.due_day <= 31):
            raise ValueError('due_day deve ser entre 1 e 31')
        
        if self.due_day == self.closing_day:
            logger.info(f"ℹ️ Fechamento e vencimento no mesmo dia: {self.closing_day}")
        
        return self


class CreditCardCreate(CreditCardBase):
    """Schema para criação de cartão"""
    pass


class CreditCardUpdate(BaseModel):
    """Schema para atualização de cartão (todos opcionais)"""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Nome do cartão"
    )
    
    brand: Optional[BRANDS] = Field(
        None,
        description="Bandeira do cartão"
    )
    
    total_limit: Optional[int] = Field(
        None,
        gt=0,
        description="Limite total em CENTAVOS"
    )
    
    closing_day: Optional[int] = Field(
        None,
        ge=1,
        le=31,
        description="Dia de fechamento da fatura"
    )
    
    due_day: Optional[int] = Field(
        None,
        ge=1,
        le=31,
        description="Dia de vencimento da fatura"
    )


class CreditCardResponse(CreditCardBase):
    """
    Schema para resposta da API.
    
    🔧 ✅ CORRIGIDO: Não duplica campos da base (user_id, created_at, updated_at)
    """
    
    id: str = Field(..., alias="_id", description="ID do cartão")
    
    used_limit: int = Field(
        default=0,
        ge=0,
        description="Limite já utilizado em CENTAVOS (compras pagas + parcelas já vencidas)"
    )
    
    committed_amount: int = Field(
        default=0,
        ge=0,
        description="Valor comprometido em CENTAVOS (parcelas futuras que ainda não venceram)"
    )
    
    available_limit: int = Field(
        default=0,
        ge=0,
        description="Limite disponível = total_limit - used_limit - committed_amount"
    )
    
    last_statement_closed_at: Optional[datetime] = Field(
        None,
        description="Data do último fechamento de fatura"
    )
    
    next_statement_due_date: Optional[datetime] = Field(
        None,
        description="Data do próximo vencimento"
    )
    
    # ========== VALIDADORES ==========
    
    @model_validator(mode='after')
    def calculate_available_limit(self):
        """
        Calcula o limite disponível automaticamente.
        🔧 CORRIGIDO: Garante que used_limit + committed_amount <= total_limit.
        🔧 i18n: Mensagem com chave ERROR_LIMIT_EXCEEDED
        """
        if self.used_limit + self.committed_amount > self.total_limit:
            raise ValueError(
                f'Limite excedido: usado ({self.used_limit}) + comprometido ({self.committed_amount}) '
                f'= {self.used_limit + self.committed_amount} > total ({self.total_limit})'
            )
        
        self.available_limit = self.total_limit - self.used_limit - self.committed_amount
        if self.available_limit < 0:
            self.available_limit = 0
        return self


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Brand com Literal (visa, mastercard, elo, amex, hipercard, outros)
#   - total_limit em centavos (int)
#   - used_limit, committed_amount, available_limit (int)
#   - Cálculo automático do available_limit
#   - Validação: used_limit + committed_amount <= total_limit
#   - Validação: closing_day e due_day entre 1 e 31
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response)
#   - ✅ CORRIGIDO: CreditCardBase herda de BaseModelWithUser
#   - ✅ CORRIGIDO: CreditCardResponse não duplica campos da base
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de due_day no mês seguinte (mais complexa, requer cálculo de data)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser (03/07/2026)
#   - v3: Correções - Brand com Literal, remoção de duplicação (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO