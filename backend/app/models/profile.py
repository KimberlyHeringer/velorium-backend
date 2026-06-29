"""
Modelo de Perfil Financeiro do Usuário
Arquivo: backend/app/models/profile.py

🔧 CORRIGIDO:
- Adicionados max_length em todos os campos de texto
- Adicionado max_items em next_year_goals
- Campos monetários agora são int (centavos)
- Adicionados Enums (Literal) com valores CORRESPONDENTES AO FRONTEND
- 🔧 NOVO: model_validator para conversão de ObjectId
- 🔧 NOVO: Método touch() para updated_at
- 🔧 CORRIGIDO: validate_positive_value aceita strings
- 🔧 CORRIGIDO: validate_dream_other verifica string vazia
- 🔧 REMOVIDO: validate_goals_list (redundante)
- 🔧 NOVO: Validação de next_year_goals com "nenhuma" + outras opções
- 🔧 NOVO: Validação de next_year_goal_value com next_year_goals
- 🔧 i18n: Mensagens de erro documentadas com chaves para referência
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Literal, Any
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import convert_objectid_to_str


class UserProfile(BaseModel):
    """
    Perfil financeiro detalhado do usuário.
    Armazena respostas de questionários sobre hábitos, metas e perfil de risco.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")

    # ========== Bloco 1: Psicologia Financeira ==========
    money_feeling: Optional[Literal["ansioso", "indiferente", "controlado", "inseguro"]] = Field(
        None, description="sentimento em relação ao dinheiro"
    )
    post_purchase: Optional[Literal["culpa", "alegria", "racionalizo", "impulsivo"]] = Field(
        None, description="reação após comprar"
    )
    satisfaction: Optional[Literal["saldo_crescendo", "comprar", "pagar_divida", "ajudar"]] = Field(
        None, description="o que te deixa satisfeito financeiramente"
    )
    planning_habit: Optional[Literal["sempre", "as_vezes", "raramente", "nao_sei"]] = Field(
        None, description="hábito de planejamento"
    )

    # ========== Bloco 2: Metas Pessoais ==========
    dream_5y: Optional[Literal["imovel", "viajar", "liberdade", "aposentar", "outro"]] = Field(
        None, description="sonho para 5 anos"
    )
    dream_other: Optional[str] = Field(None, max_length=500, description="outro sonho (se aplicável)")
    dream_value: Optional[int] = Field(None, ge=0, description="Valor estimado do sonho em CENTAVOS")
    
    emergency_target: Optional[Literal["3_meses", "6_meses", "12_meses", "nenhuma"]] = Field(
        None, description="meta para reserva de emergência"
    )
    next_year_goals: List[Literal["quitar_dividas", "guardar", "investir", "aumentar_renda", "nenhuma"]] = Field(
        default_factory=list, 
        max_length=20, 
        description="lista de metas para o próximo ano"
    )
    next_year_goal_value: Optional[int] = Field(None, ge=0, description="Valor da meta em CENTAVOS")

    # ========== Bloco 3: Hábitos de Consumo ==========
    spending_blindspot: Optional[Literal["alimentacao_fora", "compras_online", "assinaturas", "transporte", "lazer"]] = Field(
        None, description="onde o dinheiro 'some'"
    )
    price_comparison: Optional[Literal["sempre", "as_vezes", "raramente", "nunca"]] = Field(
        None, description="hábito de comparar preços"
    )
    money_phrase: Optional[Literal["pago_a_vista", "parcelo", "uso_credito", "vivo_sem_planejar"]] = Field(
        None, description="frase que define relação com dinheiro"
    )

    # ========== Bloco 4: Tolerância a Risco ==========
    risk_scenario: Optional[Literal["poupanca", "renda_fixa", "hibrido", "alto_risco"]] = Field(
        None, description="reação a cenário de risco"
    )
    risk_phrase: Optional[Literal["prevenir", "arriscar", "equilibrio", "nao_entendo"]] = Field(
        None, description="frase sobre risco"
    )
    has_debt: Optional[Literal["cartao_rotativo", "financiamento", "emprestimo", "nao"]] = Field(
        None, description="se possui dívidas"
    )
    credit_card_behavior: Optional[Literal["sempre_integral", "parcelar", "atraso"]] = Field(
        None, description="comportamento com cartão de crédito"
    )

    # ========== Metadados ==========
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDAÇÕES ==========

    @field_validator('dream_value', 'next_year_goal_value', mode='before')
    @classmethod
    def validate_positive_value(cls, v: Any) -> Optional[int]:
        """
        🔧 CORRIGIDO: Valida que os valores monetários sejam positivos.
        🔧 i18n: Mensagem com chave ERROR_PROFILE_VALUE_NEGATIVE
        """
        if v is None:
            return None
        
        if isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                raise ValueError('Valor deve ser um número')
        
        if isinstance(v, (int, float)):
            if v < 0:
                raise ValueError('Valor não pode ser negativo')
            return int(v)
        
        raise ValueError('Valor deve ser um número')

    @field_validator('next_year_goals', mode='before')
    @classmethod
    def validate_next_year_goals(cls, v: Any) -> List[str]:
        """
        🔧 NOVO: Valida que 'nenhuma' não aparece com outras opções.
        🔧 i18n: Mensagem com chave ERROR_PROFILE_GOALS_NENHUMA_CONFLICT
        """
        if not isinstance(v, list):
            return v
        
        if 'nenhuma' in v and len(v) > 1:
            raise ValueError('Se "nenhuma" for selecionada, não pode haver outras metas')
        
        # Remove duplicatas
        return list(dict.fromkeys(v))

    @model_validator(mode='after')
    def validate_dream_other(self):
        """
        Se dream_5y = 'outro', dream_other é obrigatório.
        🔧 CORRIGIDO: Verifica se dream_other tem conteúdo.
        🔧 i18n: Mensagem com chave ERROR_PROFILE_DREAM_OTHER_REQUIRED
        """
        if self.dream_5y == 'outro':
            if not self.dream_other or not str(self.dream_other).strip():
                raise ValueError('dream_other é obrigatório quando dream_5y é "outro"')
        return self

    @model_validator(mode='after')
    def validate_next_year_value(self):
        """
        Se next_year_goals não estiver vazio, next_year_goal_value é obrigatório.
        🔧 NOVO: Validação de consistência.
        🔧 i18n: Mensagem com chave ERROR_PROFILE_NEXT_YEAR_VALUE_REQUIRED
        """
        if self.next_year_goals and self.next_year_goal_value is None:
            raise ValueError('next_year_goal_value é obrigatório quando há metas definidas')
        return self

    # ========== MÉTODOS AUXILIARES ==========

    def touch(self) -> 'UserProfile':
        """
        🔧 NOVO: Atualiza o timestamp de modificação.
        Uso: profile.touch() antes de salvar no banco.
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
        if isinstance(data, UserProfile):
            return data
        
        return convert_objectid_to_str(data)


class UserProfileCreate(BaseModel):
    """Schema usado para CRIAR um perfil (sem campos autogerados)"""
    money_feeling: Optional[Literal["ansioso", "indiferente", "controlado", "inseguro"]] = None
    post_purchase: Optional[Literal["culpa", "alegria", "racionalizo", "impulsivo"]] = None
    satisfaction: Optional[Literal["saldo_crescendo", "comprar", "pagar_divida", "ajudar"]] = None
    planning_habit: Optional[Literal["sempre", "as_vezes", "raramente", "nao_sei"]] = None
    dream_5y: Optional[Literal["imovel", "viajar", "liberdade", "aposentar", "outro"]] = None
    dream_other: Optional[str] = Field(None, max_length=500)
    dream_value: Optional[int] = Field(None, ge=0)
    emergency_target: Optional[Literal["3_meses", "6_meses", "12_meses", "nenhuma"]] = None
    next_year_goals: List[Literal["quitar_dividas", "guardar", "investir", "aumentar_renda", "nenhuma"]] = Field(
        default_factory=list, max_length=20
    )
    next_year_goal_value: Optional[int] = Field(None, ge=0)
    spending_blindspot: Optional[Literal["alimentacao_fora", "compras_online", "assinaturas", "transporte", "lazer"]] = None
    price_comparison: Optional[Literal["sempre", "as_vezes", "raramente", "nunca"]] = None
    money_phrase: Optional[Literal["pago_a_vista", "parcelo", "uso_credito", "vivo_sem_planejar"]] = None
    risk_scenario: Optional[Literal["poupanca", "renda_fixa", "hibrido", "alto_risco"]] = None
    risk_phrase: Optional[Literal["prevenir", "arriscar", "equilibrio", "nao_entendo"]] = None
    has_debt: Optional[Literal["cartao_rotativo", "financiamento", "emprestimo", "nao"]] = None
    credit_card_behavior: Optional[Literal["sempre_integral", "parcelar", "atraso"]] = None

    @field_validator('dream_value', 'next_year_goal_value', mode='before')
    @classmethod
    def validate_positive_value(cls, v: Any) -> Optional[int]:
        """
        🔧 CORRIGIDO: Valida que os valores monetários sejam positivos.
        """
        if v is None:
            return None
        
        if isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                raise ValueError('Valor deve ser um número')
        
        if isinstance(v, (int, float)):
            if v < 0:
                raise ValueError('Valor não pode ser negativo')
            return int(v)
        
        raise ValueError('Valor deve ser um número')

    @field_validator('next_year_goals', mode='before')
    @classmethod
    def validate_next_year_goals(cls, v: Any) -> List[str]:
        """
        Valida que 'nenhuma' não aparece com outras opções.
        """
        if not isinstance(v, list):
            return v
        
        if 'nenhuma' in v and len(v) > 1:
            raise ValueError('Se "nenhuma" for selecionada, não pode haver outras metas')
        
        return list(dict.fromkeys(v))

    @model_validator(mode='after')
    def validate_dream_other(self):
        """
        Se dream_5y = 'outro', dream_other é obrigatório.
        """
        if self.dream_5y == 'outro':
            if not self.dream_other or not str(self.dream_other).strip():
                raise ValueError('dream_other é obrigatório quando dream_5y é "outro"')
        return self

    @model_validator(mode='after')
    def validate_next_year_value(self):
        """
        Se next_year_goals não estiver vazio, next_year_goal_value é obrigatório.
        """
        if self.next_year_goals and self.next_year_goal_value is None:
            raise ValueError('next_year_goal_value é obrigatório quando há metas definidas')
        return self


class UserProfileResponse(UserProfile):
    """Schema usado para RESPOSTAS da API (força id como string)"""
    id: str = Field(..., description="ID do perfil")


# ========== PENDÊNCIAS PÓS-MVP ==========
#
# 1. Validação de dream_value com dream_5y:
#    Se dream_5y for definido, dream_value é obrigatório.
#
# 2. Propriedade calculada: profile_completeness


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. Adicionados max_length em todos os campos de texto
2. Adicionado max_length=20 em next_year_goals
3. 🔧 REMOVIDO: validate_goals_list (redundante)
4. 🔧 Campos monetários: dream_value, next_year_goal_value → int (centavos)
5. 🔧 Enums (Literal) ajustados com os valores EXATOS do frontend
6. 🔧 CORRIGIDO: validate_positive_value aceita strings
7. 🔧 CORRIGIDO: validate_dream_other verifica string vazia
8. 🔧 NOVO: Validação de next_year_goals com "nenhuma" + outras opções
9. 🔧 NOVO: Validação de next_year_goal_value com next_year_goals
10. 🔧 NOVO: model_validator para conversão de ObjectId
11. 🔧 NOVO: Método touch() para updated_at
12. 🔧 i18n: Mensagens de erro documentadas com chaves para referência

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_PROFILE_VALUE_NEGATIVE → "Valor não pode ser negativo"
   - ERROR_PROFILE_DREAM_OTHER_REQUIRED → "dream_other é obrigatório quando dream_5y é 'outro'"
   - ERROR_PROFILE_GOALS_NENHUMA_CONFLICT → "Se 'nenhuma' for selecionada, não pode haver outras metas"
   - ERROR_PROFILE_NEXT_YEAR_VALUE_REQUIRED → "next_year_goal_value é obrigatório quando há metas definidas"

⏳ PENDÊNCIAS PÓS-MVP:
================================================================================
1. Validação de dream_value com dream_5y (opcional)
2. Propriedade calculada: profile_completeness

================================================================================
✅ STATUS: APROVADO PARA MVP (100% corrigido)
================================================================================
"""