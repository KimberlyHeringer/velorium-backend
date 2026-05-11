"""
Modelo de Perfil Financeiro do Usuário
Arquivo: backend/app/models/profile.py
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId


class UserProfile(BaseModel):
    """
    Perfil financeiro detalhado do usuário.
    Armazena respostas de questionários sobre hábitos, metas e perfil de risco.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str  # referência ao User (injetado pelo backend)

    # ========== Bloco 1: Psicologia Financeira ==========
    money_feeling: Optional[str] = None      # sentimento em relação ao dinheiro
    post_purchase: Optional[str] = None      # reação após comprar
    satisfaction: Optional[str] = None       # o que te deixa satisfeito financeiramente
    planning_habit: Optional[str] = None     # hábito de planejamento

    # ========== Bloco 2: Metas Pessoais ==========
    dream_5y: Optional[str] = None           # sonho para 5 anos
    dream_other: Optional[str] = None        # outro sonho (se aplicável)
    dream_value: Optional[str] = None        # valor estimado do sonho (string por enquanto)
    emergency_target: Optional[str] = None   # meta para reserva de emergência
    next_year_goals: List[str] = Field(default_factory=list)  # lista de metas para o próximo ano
    next_year_goal_value: Optional[str] = None  # valor da meta (string por enquanto)

    # ========== Bloco 3: Hábitos de Consumo ==========
    spending_blindspot: Optional[str] = None  # onde o dinheiro "some"
    price_comparison: Optional[str] = None    # hábito de comparar preços
    money_phrase: Optional[str] = None        # frase que define relação com dinheiro

    # ========== Bloco 4: Tolerância a Risco ==========
    risk_scenario: Optional[str] = None       # reação a cenário de risco
    risk_phrase: Optional[str] = None         # frase sobre risco
    has_debt: Optional[str] = None            # se possui dívidas (cartão rotativo, financiamento, etc.)
    credit_card_behavior: Optional[str] = None # comportamento com cartão de crédito

    # ========== Metadados ==========
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserProfileCreate(BaseModel):
    """Schema usado para CRIAR um perfil (sem campos autogerados)"""
    money_feeling: Optional[str] = None
    post_purchase: Optional[str] = None
    satisfaction: Optional[str] = None
    planning_habit: Optional[str] = None
    dream_5y: Optional[str] = None
    dream_other: Optional[str] = None
    dream_value: Optional[str] = None
    emergency_target: Optional[str] = None
    next_year_goals: List[str] = Field(default_factory=list)
    next_year_goal_value: Optional[str] = None
    spending_blindspot: Optional[str] = None
    price_comparison: Optional[str] = None
    money_phrase: Optional[str] = None
    risk_scenario: Optional[str] = None
    risk_phrase: Optional[str] = None
    has_debt: Optional[str] = None
    credit_card_behavior: Optional[str] = None


class UserProfileResponse(UserProfile):
    """Schema usado para RESPOSTAS da API (força id como string)"""
    id: str


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Corrigido next_year_goals para usar Field(default_factory=list)
# ✅ Adicionado id: str em UserProfileResponse (consistência)
# ✅ Comentários explicativos em português
#
# 📅 Dívida técnica registrada (pós-MVP):
#    - Campos monetários como str (dream_value, emergency_target, next_year_goal_value)
#      → Migrar para float ou Decimal quando precisar de cálculos
#    - Criar Enums para campos fixos (money_feeling, risk_phrase, etc.)
#      → Evitar dados inconsistentes
#
# ⏳ updated_at: atualização manual nas rotas (já documentado no plano geral)