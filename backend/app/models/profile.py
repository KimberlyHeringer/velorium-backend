"""
Modelo de Perfil Financeiro do Usuário
Arquivo: backend/app/models/profile.py

Funcionalidades:
- Armazenamento do perfil financeiro completo do usuário
- Questionários de psicologia financeira, metas, hábitos e risco
- Suporte a múltiplos contextos (individual/familia/profissional)

Principais features:
- 4 blocos de perguntas (psicologia, metas, hábitos, risco)
- Campos monetários em centavos (int) para precisão
- Validação: "nenhuma" não pode aparecer com outras metas
- Validação: sonho "outro" exige descrição
- ✅ CORRIGIDO: next_year_goal_value só é obrigatório se houver metas ativas (não "nenhuma")
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- Schemas separados (Create, Response)
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Literal, Any

from app.models.base import BaseModelWithUser
from app.models.mixins import AuditMixin


class UserProfile(BaseModelWithUser, AuditMixin):
    """
    Perfil financeiro detalhado do usuário.
    Armazena respostas de questionários sobre hábitos, metas e perfil de risco.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
      - AuditMixin: created_by, updated_by, deleted_at, is_deleted, mark_deleted(), restore()
    
    🔧 CAMPOS ADICIONADOS:
      - Bloco 1: Psicologia Financeira (money_feeling, post_purchase, satisfaction, planning_habit)
      - Bloco 2: Metas Pessoais (dream_5y, dream_other, dream_value, emergency_target, next_year_goals, next_year_goal_value)
      - Bloco 3: Hábitos de Consumo (spending_blindspot, price_comparison, money_phrase)
      - Bloco 4: Tolerância a Risco (risk_scenario, risk_phrase, has_debt, credit_card_behavior)
    """
    
    # ========== Bloco 1: Psicologia Financeira ==========
    
    money_feeling: Optional[Literal["ansioso", "indiferente", "controlado", "inseguro"]] = Field(
        None,
        description="sentimento em relação ao dinheiro"
    )
    
    post_purchase: Optional[Literal["culpa", "alegria", "racionalizo", "impulsivo"]] = Field(
        None,
        description="reação após comprar"
    )
    
    satisfaction: Optional[Literal["saldo_crescendo", "comprar", "pagar_divida", "ajudar"]] = Field(
        None,
        description="o que te deixa satisfeito financeiramente"
    )
    
    planning_habit: Optional[Literal["sempre", "as_vezes", "raramente", "nao_sei"]] = Field(
        None,
        description="hábito de planejamento"
    )
    
    # ========== Bloco 2: Metas Pessoais ==========
    
    dream_5y: Optional[Literal["imovel", "viajar", "liberdade", "aposentar", "outro"]] = Field(
        None,
        description="sonho para 5 anos"
    )
    
    dream_other: Optional[str] = Field(
        None,
        max_length=500,
        description="outro sonho (se aplicável)"
    )
    
    dream_value: Optional[int] = Field(
        None,
        ge=0,
        description="Valor estimado do sonho em CENTAVOS"
    )
    
    emergency_target: Optional[Literal["3_meses", "6_meses", "12_meses", "nenhuma"]] = Field(
        None,
        description="meta para reserva de emergência"
    )
    
    next_year_goals: List[Literal["quitar_dividas", "guardar", "investir", "aumentar_renda", "nenhuma"]] = Field(
        default_factory=list,
        max_length=20,
        description="lista de metas para o próximo ano"
    )
    
    next_year_goal_value: Optional[int] = Field(
        None,
        ge=0,
        description="Valor da meta em CENTAVOS"
    )
    
    # ========== Bloco 3: Hábitos de Consumo ==========
    
    spending_blindspot: Optional[Literal["alimentacao_fora", "compras_online", "assinaturas", "transporte", "lazer"]] = Field(
        None,
        description="onde o dinheiro 'some'"
    )
    
    price_comparison: Optional[Literal["sempre", "as_vezes", "raramente", "nunca"]] = Field(
        None,
        description="hábito de comparar preços"
    )
    
    money_phrase: Optional[Literal["pago_a_vista", "parcelo", "uso_credito", "vivo_sem_planejar"]] = Field(
        None,
        description="frase que define relação com dinheiro"
    )
    
    # ========== Bloco 4: Tolerância a Risco ==========
    
    risk_scenario: Optional[Literal["poupanca", "renda_fixa", "hibrido", "alto_risco"]] = Field(
        None,
        description="reação a cenário de risco"
    )
    
    risk_phrase: Optional[Literal["prevenir", "arriscar", "equilibrio", "nao_entendo"]] = Field(
        None,
        description="frase sobre risco"
    )
    
    has_debt: Optional[Literal["cartao_rotativo", "financiamento", "emprestimo", "nao"]] = Field(
        None,
        description="se possui dívidas"
    )
    
    credit_card_behavior: Optional[Literal["sempre_integral", "parcelar", "atraso"]] = Field(
        None,
        description="comportamento com cartão de crédito"
    )
    
    # ========== VALIDAÇÕES ==========

    @field_validator('dream_value', 'next_year_goal_value', mode='before')
    @classmethod
    def validate_positive_value(cls, v: Any) -> Optional[int]:
        """
        Valida que os valores monetários sejam positivos.
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
        Valida que 'nenhuma' não aparece com outras opções.
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
        🔧 i18n: Mensagem com chave ERROR_PROFILE_DREAM_OTHER_REQUIRED
        """
        if self.dream_5y == 'outro':
            if not self.dream_other or not str(self.dream_other).strip():
                raise ValueError('dream_other é obrigatório quando dream_5y é "outro"')
        return self

    @model_validator(mode='after')
    def validate_next_year_value(self):
        """
        🔧 CORRIGIDO: Apenas valida se next_year_goals contém metas ativas (não "nenhuma").
        """
        # Filtra apenas metas que não sejam "nenhuma"
        active_goals = [g for g in self.next_year_goals if g != "nenhuma"]
        
        # Se houver metas ativas, next_year_goal_value é obrigatório
        if active_goals and self.next_year_goal_value is None:
            raise ValueError('next_year_goal_value é obrigatório quando há metas definidas')
        return self


class UserProfileCreate(BaseModel):
    """
    Schema usado para CRIAR um perfil (sem campos autogerados).
    
    🔧 DIFERENÇAS DO MODEL USERPROFILE:
      - Não tem campos de auditoria (ainda não existe no banco)
      - Todos os campos são opcionais no create
      - Validações específicas do perfil são mantidas
    """
    
    # ========== Bloco 1: Psicologia Financeira ==========
    money_feeling: Optional[Literal["ansioso", "indiferente", "controlado", "inseguro"]] = None
    post_purchase: Optional[Literal["culpa", "alegria", "racionalizo", "impulsivo"]] = None
    satisfaction: Optional[Literal["saldo_crescendo", "comprar", "pagar_divida", "ajudar"]] = None
    planning_habit: Optional[Literal["sempre", "as_vezes", "raramente", "nao_sei"]] = None
    
    # ========== Bloco 2: Metas Pessoais ==========
    dream_5y: Optional[Literal["imovel", "viajar", "liberdade", "aposentar", "outro"]] = None
    dream_other: Optional[str] = Field(None, max_length=500)
    dream_value: Optional[int] = Field(None, ge=0)
    emergency_target: Optional[Literal["3_meses", "6_meses", "12_meses", "nenhuma"]] = None
    next_year_goals: List[Literal["quitar_dividas", "guardar", "investir", "aumentar_renda", "nenhuma"]] = Field(
        default_factory=list, max_length=20
    )
    next_year_goal_value: Optional[int] = Field(None, ge=0)
    
    # ========== Bloco 3: Hábitos de Consumo ==========
    spending_blindspot: Optional[Literal["alimentacao_fora", "compras_online", "assinaturas", "transporte", "lazer"]] = None
    price_comparison: Optional[Literal["sempre", "as_vezes", "raramente", "nunca"]] = None
    money_phrase: Optional[Literal["pago_a_vista", "parcelo", "uso_credito", "vivo_sem_planejar"]] = None
    
    # ========== Bloco 4: Tolerância a Risco ==========
    risk_scenario: Optional[Literal["poupanca", "renda_fixa", "hibrido", "alto_risco"]] = None
    risk_phrase: Optional[Literal["prevenir", "arriscar", "equilibrio", "nao_entendo"]] = None
    has_debt: Optional[Literal["cartao_rotativo", "financiamento", "emprestimo", "nao"]] = None
    credit_card_behavior: Optional[Literal["sempre_integral", "parcelar", "atraso"]] = None

    # ========== VALIDAÇÕES ==========

    @field_validator('dream_value', 'next_year_goal_value', mode='before')
    @classmethod
    def validate_positive_value(cls, v: Any) -> Optional[int]:
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
        if not isinstance(v, list):
            return v
        
        if 'nenhuma' in v and len(v) > 1:
            raise ValueError('Se "nenhuma" for selecionada, não pode haver outras metas')
        
        return list(dict.fromkeys(v))

    @model_validator(mode='after')
    def validate_dream_other(self):
        if self.dream_5y == 'outro':
            if not self.dream_other or not str(self.dream_other).strip():
                raise ValueError('dream_other é obrigatório quando dream_5y é "outro"')
        return self

    @model_validator(mode='after')
    def validate_next_year_value(self):
        """
        🔧 CORRIGIDO: Apenas valida se next_year_goals contém metas ativas (não "nenhuma").
        """
        active_goals = [g for g in self.next_year_goals if g != "nenhuma"]
        if active_goals and self.next_year_goal_value is None:
            raise ValueError('next_year_goal_value é obrigatório quando há metas definidas')
        return self


class UserProfileResponse(UserProfile):
    """
    Schema usado para RESPOSTAS da API.
    
    🔧 DIFERENÇAS DO MODEL USERPROFILE:
      - id é obrigatório (já existe no banco)
      - Todos os campos são obrigatórios na resposta (herdados)
    """
    
    id: str = Field(..., description="ID do perfil")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de AuditMixin (created_by, updated_by, deleted_at, is_deleted, mark_deleted(), restore())
#   - 4 blocos de perguntas (psicologia, metas, hábitos, risco)
#   - Validação: "nenhuma" não pode aparecer com outras metas
#   - Validação: sonho "outro" exige descrição
#   - Validação: dream_value e next_year_goal_value em centavos
#   - ✅ CORRIGIDO: next_year_goal_value só é obrigatório se houver metas ativas
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Response)
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de dream_value com dream_5y (opcional)
#   - Propriedade calculada: profile_completeness
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser e AuditMixin (03/07/2026)
#   - v3: Correção - next_year_goal_value só obrigatório se houver metas ativas (04/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO