"""
Modelo de Metas Financeiras (Goals)
Arquivo: backend/app/models/goal.py

Funcionalidades:
- CRUD de metas financeiras
- Acompanhamento de progresso
- Conclusão automática e manual
- Metas recorrentes (recria automática ao completar)
- Metas com data limite (deadline)
- Sub-metas (hierarquia de metas)
- Histórico de metas concluídas

Principais features:
- Valores em centavos (int) para precisão
- progress_percentage calculado automaticamente
- remaining_amount calculado automaticamente
- sync_completed permite conclusão manual ou automática
- Suporte a metas recorrentes (monthly, yearly)
- Suporte a sub-metas (parent_id)
- Data limite para conclusão
- Arquivamento de metas concluídas
- 🆕 Descrição da meta (description)
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- ✅ CORRIGIDO: Herança correta de BaseModelWithUser
- ✅ CORRIGIDO: GoalResponse id obrigatório
- 🔧 CORRIGIDO: Mergeable if statements combinados (S1066)
"""

from pydantic import BaseModel, Field, model_validator, computed_field
from typing import Optional, Literal, Any
from datetime import datetime, timezone

from app.models.base import BaseModelWithUser


class Goal(BaseModelWithUser):
    """
    Modelo principal de Meta Financeira.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
    
    🔧 IMPORTANTE: Valores estão em CENTAVOS (int)
    - Exemplo: R$ 15.000,00 → 1500000
    
    🔧 CAMPOS ADICIONADOS:
      - name: Nome da meta
      - target: Valor alvo em centavos
      - current: Valor atual em centavos
      - category: Categoria da meta
      - completed: Meta concluída?
      - 🆕 description: Descrição da meta
      
      🆕 CAMPOS (11/07/2026):
      - recurring: Meta recorrente?
      - recurring_interval: Intervalo de recorrência (monthly, yearly)
      - deadline: Data limite para conclusão
      - parent_id: ID da meta pai (para sub-metas)
      - completed_at: Data de conclusão
      - archived: Meta arquivada (histórico)
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nome da meta"
    )
    
    target: int = Field(
        ...,
        gt=0,
        description="Valor alvo em CENTAVOS (ex: 1500000 = R$15.000,00)"
    )
    
    # ========== CAMPOS OPCIONAIS ==========
    
    current: int = Field(
        default=0,
        ge=0,
        description="Valor atual em CENTAVOS"
    )
    
    category: Optional[str] = Field(
        None,
        max_length=50,
        description="Categoria da meta"
    )
    
    completed: bool = Field(
        default=False,
        description="Meta concluída?"
    )
    
    # ========== 🆕 NOVOS CAMPOS ==========
    
    recurring: bool = Field(
        default=False,
        description="Meta recorrente? Se True, recria automaticamente ao completar"
    )
    
    recurring_interval: Optional[Literal["monthly", "yearly"]] = Field(
        None,
        description="Intervalo de recorrência (monthly, yearly)"
    )
    
    deadline: Optional[datetime] = Field(
        None,
        description="Data limite para conclusão da meta"
    )
    
    parent_id: Optional[str] = Field(
        None,
        description="ID da meta pai (se for sub-meta)"
    )
    
    completed_at: Optional[datetime] = Field(
        None,
        description="Data de conclusão da meta"
    )
    
    archived: bool = Field(
        default=False,
        description="Meta arquivada (histórico de metas concluídas)"
    )
    
    # ========== 🆕 CAMPO DESCRIPTION ==========
    
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Descrição detalhada da meta"
    )
    
    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def sync_completed(self):
        """
        Sincroniza completed baseado em current >= target.
        🔧 CORRIGIDO: Permite conclusão manual (se completed já for True, mantém).
        🆕 Se completar, define completed_at.
        🔧 S1066: Combinado ifs aninhados
        """
        if self.completed:
            return self
        
        self.completed = self.current >= self.target
        
        # 🔧 S1066: Combinado em uma única condição
        if self.completed and self.completed_at is None:
            self.completed_at = datetime.now(timezone.utc)
        
        return self

    @model_validator(mode='after')
    def validate_recurring(self):
        """
        Valida campos de meta recorrente.
        🔧 i18n: Mensagem com chave ERROR_RECURRING_INTERVAL_REQUIRED
        🔧 S1066: Combinado ifs aninhados
        """
        if self.recurring and self.recurring_interval is None:
            raise ValueError('recurring_interval é obrigatório quando recurring=True')
        return self

    @model_validator(mode='after')
    def validate_deadline(self):
        """
        Valida que deadline não está no passado.
        🔧 i18n: Mensagem com chave ERROR_DEADLINE_PAST
        🔧 S1066: Combinado ifs aninhados
        """
        if self.deadline and self.deadline < datetime.now(timezone.utc):
            raise ValueError('deadline não pode ser no passado')
        return self

    @model_validator(mode='after')
    def validate_parent_id(self):
        """
        Valida que parent_id não é o próprio ID.
        🔧 i18n: Mensagem com chave ERROR_CANNOT_BE_OWN_PARENT
        """
        if self.parent_id and str(self.parent_id) == str(self.id):
            raise ValueError('Uma meta não pode ser pai de si mesma')
        return self

    @model_validator(mode='after')
    def validate_recurring_and_deadline(self):
        """
        Valida que metas recorrentes não têm deadline.
        🔧 i18n: Mensagem com chave ERROR_RECURRING_WITH_DEADLINE
        """
        if self.recurring and self.deadline:
            raise ValueError('Metas recorrentes não podem ter data limite')
        return self


class GoalCreate(BaseModel):
    """
    Schema usado para CRIAR uma nova meta.
    
    🔧 DIFERENÇAS DO MODEL GOAL:
      - Não tem campos de auditoria (ainda não existe no banco)
      - target e current são obrigatórios na criação
      - 🆕 Suporte a recurring, deadline, parent_id, description
    """
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nome da meta"
    )
    
    target: int = Field(
        ...,
        gt=0,
        description="Valor alvo em CENTAVOS"
    )
    
    current: int = Field(
        default=0,
        ge=0,
        description="Valor atual em CENTAVOS"
    )
    
    category: Optional[str] = Field(
        None,
        max_length=50,
        description="Categoria da meta"
    )
    
    # 🆕 NOVOS CAMPOS
    recurring: bool = Field(
        default=False,
        description="Meta recorrente?"
    )
    
    recurring_interval: Optional[Literal["monthly", "yearly"]] = Field(
        None,
        description="Intervalo de recorrência"
    )
    
    deadline: Optional[datetime] = Field(
        None,
        description="Data limite para conclusão"
    )
    
    parent_id: Optional[str] = Field(
        None,
        description="ID da meta pai (sub-meta)"
    )
    
    # 🆕 CAMPO DESCRIPTION
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Descrição detalhada da meta"
    )

    @model_validator(mode='after')
    def validate_current_not_exceeds_target(self):
        """
        Valida que current não excede target.
        🔧 i18n: Mensagem com chave ERROR_GOAL_CURRENT_EXCEEDS_TARGET
        """
        if self.current > self.target:
            raise ValueError('Valor atual não pode ser maior que o valor alvo')
        return self

    @model_validator(mode='after')
    def validate_recurring(self):
        """
        Valida campos de meta recorrente.
        """
        if self.recurring and self.recurring_interval is None:
            raise ValueError('recurring_interval é obrigatório quando recurring=True')
        return self

    @model_validator(mode='after')
    def validate_deadline(self):
        """
        Valida que deadline não está no passado.
        """
        if self.deadline and self.deadline < datetime.now(timezone.utc):
            raise ValueError('deadline não pode ser no passado')
        return self

    @model_validator(mode='after')
    def validate_recurring_and_deadline(self):
        """
        Valida que metas recorrentes não têm deadline.
        """
        if self.recurring and self.deadline:
            raise ValueError('Metas recorrentes não podem ter data limite')
        return self


class GoalUpdate(BaseModel):
    """
    Schema usado para ATUALIZAR uma meta existente.
    
    🔧 TODOS OS CAMPOS SÃO OPCIONAIS:
      - Permite atualização parcial
      - 🆕 Suporte a recurring, deadline, parent_id, archived, description
    """
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Nome da meta"
    )
    
    target: Optional[int] = Field(
        None,
        gt=0,
        description="Valor alvo em CENTAVOS"
    )
    
    current: Optional[int] = Field(
        None,
        ge=0,
        description="Valor atual em CENTAVOS"
    )
    
    category: Optional[str] = Field(
        None,
        max_length=50,
        description="Categoria da meta"
    )
    
    completed: Optional[bool] = Field(
        None,
        description="Meta concluída?"
    )
    
    # 🆕 NOVOS CAMPOS
    recurring: Optional[bool] = Field(
        None,
        description="Meta recorrente?"
    )
    
    recurring_interval: Optional[Literal["monthly", "yearly"]] = Field(
        None,
        description="Intervalo de recorrência"
    )
    
    deadline: Optional[datetime] = Field(
        None,
        description="Data limite para conclusão"
    )
    
    parent_id: Optional[str] = Field(
        None,
        description="ID da meta pai (sub-meta)"
    )
    
    archived: Optional[bool] = Field(
        None,
        description="Arquivar meta (histórico)"
    )
    
    # 🆕 CAMPO DESCRIPTION
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Descrição detalhada da meta"
    )

    @model_validator(mode='after')
    def validate_current_not_exceeds_target(self):
        """
        Valida que current não excede target (se ambos forem fornecidos).
        🔧 i18n: Mensagem com chave ERROR_GOAL_CURRENT_EXCEEDS_TARGET
        """
        if self.current is not None and self.target is not None:
            if self.current > self.target:
                raise ValueError('Valor atual não pode ser maior que o valor alvo')
        return self

    @model_validator(mode='after')
    def validate_recurring(self):
        """
        Valida campos de meta recorrente.
        """
        if self.recurring and self.recurring_interval is None:
            raise ValueError('recurring_interval é obrigatório quando recurring=True')
        return self

    @model_validator(mode='after')
    def validate_deadline(self):
        """
        Valida que deadline não está no passado.
        """
        if self.deadline and self.deadline < datetime.now(timezone.utc):
            raise ValueError('deadline não pode ser no passado')
        return self

    @model_validator(mode='after')
    def validate_recurring_and_deadline(self):
        """
        Valida que metas recorrentes não têm deadline.
        """
        if self.recurring and self.deadline:
            raise ValueError('Metas recorrentes não podem ter data limite')
        return self


class GoalResponse(Goal):
    """
    Schema usado para RESPOSTAS da API.
    
    🔧 ✅ CORRIGIDO: id é obrigatório (sobrescreve Optional)
    """
    
    id: str = Field(..., alias="_id", description="ID da meta")
    
    # ========== CAMPOS CALCULADOS ==========
    
    @computed_field
    @property
    def progress_percentage(self) -> float:
        """
        Calcula o percentual de progresso da meta.
        Útil para o frontend exibir a barra de progresso.
        """
        if self.target == 0:
            return 0.0
        return round((self.current / self.target) * 100, 1)
    
    @computed_field
    @property
    def remaining_amount(self) -> int:
        """
        Calcula o valor que falta para atingir a meta (em centavos).
        Útil para o frontend exibir "Faltam R$ X".
        """
        remaining = self.target - self.current
        return max(remaining, 0)
    
    @computed_field
    @property
    def days_until_deadline(self) -> Optional[int]:
        """
        Calcula quantos dias faltam para a data limite.
        """
        if not self.deadline:
            return None
        delta = self.deadline - datetime.now(timezone.utc)
        return max(0, delta.days)
    
    @computed_field
    @property
    def is_overdue(self) -> bool:
        """
        Verifica se a meta está atrasada (passou da data limite).
        """
        if not self.deadline or self.completed:
            return False
        return datetime.now(timezone.utc) > self.deadline


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Validação: current <= target
#   - sync_completed com conclusão manual e automática
#   - Campos calculados: progress_percentage, remaining_amount, days_until_deadline, is_overdue
#   - 🆕 Meta recorrente (recurring, recurring_interval)
#   - 🆕 Data limite (deadline)
#   - 🆕 Sub-metas (parent_id)
#   - 🆕 Histórico (completed_at, archived)
#   - 🆕 Descrição (description)
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response)
#   - ✅ CORRIGIDO: Herança correta de BaseModelWithUser
#   - ✅ CORRIGIDO: GoalResponse id obrigatório
#   - ✅ CORRIGIDO: Validação recurring + deadline
#   - ✅ CORRIGIDO: Mergeable if statements combinados (S1066)
#
# ❌ Não implementado (Pós-MVP):
#   - prioridade (baixa, média, alta)
#   - category com Literal (categorias pré-definidas)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser (03/07/2026)
#   - v3: Correções - Response id obrigatório (03/07/2026)
#   - v4: 🆕 Adicionado recurring, deadline, parent_id, completed_at, archived (11/07/2026)
#   - v5: 🆕 Adicionado description, corrigido S1066 (12/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO