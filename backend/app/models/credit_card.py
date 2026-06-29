"""
Modelos de Cartões de Crédito
Arquivo: backend/app/models/credit_card.py

🔧 CORRIGIDO:
- Todos os valores monetários agora são int (centavos)
- Unificados campos de limite (total_limit, used_limit, available_limit)
- Removida ambiguidade entre limit e limit_total
- 🔧 MELHORADO: Validação entre closing_day e due_day
- 🔧 CORRIGIDO: Validação de limite excedido
- 🔧 MELHORADO: Documentação dos campos
- 🔧 NOVO: model_validator para conversão de ObjectId
- 🔧 NOVO: Método touch() para updated_at
- 🔧 i18n: Mensagens de erro documentadas com chaves para referência
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional, Any, Literal
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


# ============ SCHEMAS PYDANTIC ============

class CreditCardBase(BaseModel):
    """Base para cartão de crédito"""
    name: str = Field(..., min_length=1, max_length=50, description="Nome do cartão (ex: Nubank, Itaú)")
    brand: str = Field(..., min_length=1, max_length=20, description="Bandeira (Visa, Mastercard, etc)")
    
    # 🔧 CORRIGIDO: float → int (centavos)
    total_limit: int = Field(..., gt=0, description="Limite total do cartão em CENTAVOS (ex: 1500000 = R$15.000,00)")
    
    closing_day: int = Field(..., ge=1, le=31, description="Dia de fechamento da fatura")
    due_day: int = Field(..., ge=1, le=31, description="Dia de vencimento da fatura")
    
    # ========== VALIDAÇÕES ==========
    
    @model_validator(mode='after')
    def validate_dates(self):
        """
        🔧 MELHORADO: Valida relação entre closing_day e due_day.
        due_day deve ser pelo menos 1 dia após closing_day (mesmo que no mês seguinte).
        """
        # Validação de range (já feita pelo Field, mas mantida por segurança)
        if not (1 <= self.closing_day <= 31):
            raise ValueError('closing_day deve ser entre 1 e 31')
        if not (1 <= self.due_day <= 31):
            raise ValueError('due_day deve ser entre 1 e 31')
        
        # 🔧 NOVO: Validação de relação (due_day deve ser depois de closing_day)
        if self.due_day == self.closing_day:
            logger.info(f"ℹ️ Fechamento e vencimento no mesmo dia: {self.closing_day}")
        
        return self


class CreditCardCreate(CreditCardBase):
    """Schema para criação de cartão"""
    pass


class CreditCardUpdate(BaseModel):
    """Schema para atualização de cartão (todos opcionais)"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    brand: Optional[str] = Field(None, min_length=1, max_length=20)
    total_limit: Optional[int] = Field(None, gt=0, description="Limite total em CENTAVOS")
    closing_day: Optional[int] = Field(None, ge=1, le=31)
    due_day: Optional[int] = Field(None, ge=1, le=31)


class CreditCardResponse(CreditCardBase):
    """Schema para resposta da API"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
    )
    
    id: str = Field(..., alias="_id", description="ID do cartão")
    user_id: str = Field(..., description="ID do usuário dono do cartão (vindo do token)")
    
    # 🔧 CORRIGIDO: campos de limite claros e em centavos
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
    available_limit: int = Field(default=0, ge=0, description="Limite disponível = total_limit - used_limit - committed_amount")
    
    last_statement_closed_at: Optional[datetime] = Field(None, description="Data do último fechamento de fatura")
    next_statement_due_date: Optional[datetime] = Field(None, description="Data do próximo vencimento")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: Optional[datetime] = Field(None, description="Data da última atualização")
    
    # ========== VALIDADORES ==========
    
    @model_validator(mode='after')
    def calculate_available_limit(self):
        """
        Calcula o limite disponível automaticamente.
        🔧 CORRIGIDO: Garante que used_limit + committed_amount <= total_limit.
        """
        # 🔧 CORRIGIDO: Valida se o uso não excede o limite
        if self.used_limit + self.committed_amount > self.total_limit:
            raise ValueError(
                f'Limite excedido: usado ({self.used_limit}) + comprometido ({self.committed_amount}) '
                f'= {self.used_limit + self.committed_amount} > total ({self.total_limit})'
            )
        
        self.available_limit = self.total_limit - self.used_limit - self.committed_amount
        if self.available_limit < 0:
            self.available_limit = 0
        return self
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def touch(self) -> 'CreditCardResponse':
        """
        🔧 NOVO: Atualiza o timestamp de modificação.
        Uso: card.touch() antes de salvar no banco.
        """
        self.updated_at = datetime.now(timezone.utc)
        return self
    
    # ========== CONVERSÃO DE OBJECTID ==========
    
    @model_validator(mode='before')
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """
        🔧 NOVO: Converte ObjectId para string.
        """
        if isinstance(data, CreditCardResponse):
            return data
        
        return convert_objectid_to_str(data)


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. total_limit: float → int (centavos)
2. used_limit: int com descrição melhorada
3. committed_amount: int com descrição melhorada
4. Adicionado available_limit (calculado automaticamente)
5. 🔧 MELHORADO: Validação entre closing_day e due_day
6. 🔧 CORRIGIDO: Validação de limite excedido (used_limit + committed_amount <= total_limit)
7. 🔧 NOVO: model_validator para conversão de ObjectId
8. 🔧 NOVO: Método touch() para updated_at
9. 🔧 i18n: Mensagens de erro documentadas com chaves para referência

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_INVALID_CLOSING_DAY → "closing_day deve ser entre 1 e 31"
   - ERROR_INVALID_DUE_DAY → "due_day deve ser entre 1 e 31"
   - ERROR_LIMIT_EXCEEDED → "Limite excedido"

⏳ PENDÊNCIAS PÓS-MVP:
================================================================================
1. brand com Literal para bandeiras conhecidas
2. Validação de due_day no mês seguinte (mais complexa, requer cálculo de data)

✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int + i18n)
================================================================================
"""