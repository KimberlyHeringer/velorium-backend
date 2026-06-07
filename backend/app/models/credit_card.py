"""
Modelos de Cartões de Crédito
Arquivo: backend/app/models/credit_card.py

🔧 CORRIGIDO:
- Todos os valores monetários agora são int (centavos)
- Unificados campos de limite (total_limit, used_limit, available_limit)
- Removida ambiguidade entre limit e limit_total
- Corrigido erro de sintaxe (vírgula no final)
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


# ============ SCHEMAS PYDANTIC ============

class CreditCardBase(BaseModel):
    """Base para cartão de crédito"""
    name: str = Field(..., min_length=1, max_length=50, description="Nome do cartão (ex: Nubank, Itaú)")
    brand: str = Field(..., min_length=1, max_length=20, description="Bandeira (Visa, Mastercard, etc)")
    
    # 🔧 CORRIGIDO: float → int (centavos)
    total_limit: int = Field(..., gt=0, description="Limite total do cartão em CENTAVOS (ex: 1500000 = R$15.000,00)")
    
    closing_day: int = Field(..., ge=1, le=31, description="Dia de fechamento da fatura")
    due_day: int = Field(..., ge=1, le=31, description="Dia de vencimento da fatura")


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
        from_attributes=True
    )
    
    id: str = Field(..., alias="_id", description="ID do cartão")
    user_id: str = Field(..., description="ID do usuário dono do cartão (vindo do token)")
    
    # 🔧 CORRIGIDO: campos de limite claros e em centavos
    used_limit: int = Field(default=0, ge=0, description="Limite já utilizado em CENTAVOS (compras pagas)")
    committed_amount: int = Field(default=0, ge=0, description="Valor comprometido em compras parceladas futuras em CENTAVOS")
    available_limit: int = Field(default=0, ge=0, description="Limite disponível = total_limit - used_limit - committed_amount")
    
    last_statement_closed_at: Optional[datetime] = Field(None, description="Data do último fechamento de fatura")
    next_statement_due_date: Optional[datetime] = Field(None, description="Data do próximo vencimento")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: Optional[datetime] = Field(None, description="Data da última atualização")
    
    @model_validator(mode='after')
    def calculate_available_limit(self):
        """Calcula o limite disponível automaticamente"""
        self.available_limit = self.total_limit - self.used_limit - self.committed_amount
        if self.available_limit < 0:
            # Se estourou o limite, disponível fica 0 (ou pode ser negativo para indicar estouro)
            self.available_limit = 0
        return self


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. total_limit: float → int (centavos)
2. used_limit: int (antes limit_total, ambíguo)
3. committed_amount: float → int
4. Adicionado available_limit (calculado automaticamente)
5. Removida ambiguidade entre limit e limit_total
6. Corrigido erro de sintaxe (vírgula no updated_at)
7. Adicionado model_validator para calcular available_limit

✅ RELAÇÃO COM AS ROTAS (para você verificar):
================================================================================
- As rotas em credit_cards.py devem usar to_cents() ao criar/atualizar
- Ao listar cartões, devem usar from_cents() para exibir
- O committed_amount é atualizado quando novas compras parceladas são criadas
- O used_limit é atualizado quando parcelas são pagas

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int)
================================================================================
"""