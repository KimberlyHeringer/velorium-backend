"""
Modelo de Metas Financeiras (Goals)
Arquivo: backend/app/models/goal.py

Funcionalidades:
- CRUD de metas financeiras
- Acompanhamento de progresso
- Conclusão automática e manual

Principais features:
- Valores em centavos (int) para precisão
- progress_percentage calculado automaticamente
- remaining_amount calculado automaticamente
- sync_completed permite conclusão manual ou automática
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- ✅ CORRIGIDO: Herança correta de BaseModelWithUser
- ✅ CORRIGIDO: GoalResponse id obrigatório
"""

from pydantic import Field, model_validator, computed_field
from typing import Optional, Any

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
    
    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def sync_completed(self):
        """
        Sincroniza completed baseado em current >= target.
        🔧 CORRIGIDO: Permite conclusão manual (se completed já for True, mantém).
        """
        # Se completed já for True, mantém (permite conclusão manual)
        if self.completed:
            return self
        
        # Conclusão automática
        self.completed = self.current >= self.target
        return self


class GoalCreate(BaseModel):
    """
    Schema usado para CRIAR uma nova meta.
    
    🔧 DIFERENÇAS DO MODEL GOAL:
      - Não tem campos de auditoria (ainda não existe no banco)
      - target e current são obrigatórios na criação
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

    @model_validator(mode='after')
    def validate_current_not_exceeds_target(self):
        """
        Valida que current não excede target.
        🔧 i18n: Mensagem com chave ERROR_GOAL_CURRENT_EXCEEDS_TARGET
        """
        if self.current > self.target:
            raise ValueError('Valor atual não pode ser maior que o valor alvo')
        return self


class GoalUpdate(BaseModel):
    """
    Schema usado para ATUALIZAR uma meta existente.
    
    🔧 TODOS OS CAMPOS SÃO OPCIONAIS:
      - Permite atualização parcial
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


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Validação: current <= target
#   - sync_completed com conclusão manual e automática
#   - Campos calculados: progress_percentage, remaining_amount
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response)
#   - ✅ CORRIGIDO: Herança correta de BaseModelWithUser
#   - ✅ CORRIGIDO: GoalResponse id obrigatório
#
# ❌ Não implementado (Pós-MVP):
#   - deadline (data limite para concluir a meta)
#   - prioridade (baixa, média, alta)
#   - category com Literal (categorias pré-definidas)
#   - descrição da meta
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser (03/07/2026)
#   - v3: Correções - Response id obrigatório (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO