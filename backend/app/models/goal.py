"""
Modelo de Metas Financeiras (Goals)
Arquivo: backend/app/models/goal.py

🔧 CORRIGIDO:
- target e current agora são int (centavos)
- Removido round_amount (não necessário)
- Adicionada validação current <= target
- Removido unit (vem do perfil do usuário)
- 🔧 NOVO: progress_percentage calculado automaticamente
- 🔧 NOVO: remaining_amount calculado automaticamente
- 🔧 NOVO: model_validator para conversão de ObjectId
- 🔧 NOVO: Método touch() para updated_at
- 🔧 CORRIGIDO: sync_completed permite conclusão manual
- 🔧 CORRIGIDO: Removida validação redundante
- 🔧 i18n: Mensagens de erro documentadas com chaves para referência
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, computed_field
from typing import Optional, Any
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class Goal(BaseModel):
    """
    Modelo principal de Meta Financeira.
    
    🔧 IMPORTANTE: Valores estão em CENTAVOS (int)
    - Exemplo: R$ 15.000,00 → 1500000
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    name: str = Field(..., min_length=1, max_length=100, description="Nome da meta")
    
    # 🔧 CORRIGIDO: float → int (centavos)
    target: int = Field(..., gt=0, description="Valor alvo em CENTAVOS (ex: 1500000 = R$15.000,00)")
    current: int = Field(default=0, ge=0, description="Valor atual em CENTAVOS")
    
    category: Optional[str] = Field(None, max_length=50, description="Categoria da meta")
    completed: bool = Field(default=False, description="Meta concluída?")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

    # ========== MÉTODOS AUXILIARES ==========

    def touch(self) -> 'Goal':
        """
        🔧 NOVO: Atualiza o timestamp de modificação.
        Uso: goal.touch() antes de salvar no banco.
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
        if isinstance(data, Goal):
            return data
        
        return convert_objectid_to_str(data)


class GoalCreate(BaseModel):
    """Schema usado para CRIAR uma nova meta"""
    name: str = Field(..., min_length=1, max_length=100, description="Nome da meta")
    target: int = Field(..., gt=0, description="Valor alvo em CENTAVOS")
    current: int = Field(default=0, ge=0, description="Valor atual em CENTAVOS")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da meta")

    @model_validator(mode='after')
    def validate_current_not_exceeds_target(self):
        """
        🔧 i18n: Mensagem com chave ERROR_GOAL_CURRENT_EXCEEDS_TARGET
        """
        if self.current > self.target:
            raise ValueError('Valor atual não pode ser maior que o valor alvo')
        return self


class GoalUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma meta existente"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target: Optional[int] = Field(None, gt=0, description="Valor alvo em CENTAVOS")
    current: Optional[int] = Field(None, ge=0, description="Valor atual em CENTAVOS")
    category: Optional[str] = Field(None, max_length=50)
    completed: Optional[bool] = None

    @model_validator(mode='after')
    def validate_current_not_exceeds_target(self):
        """
        🔧 i18n: Mensagem com chave ERROR_GOAL_CURRENT_EXCEEDS_TARGET
        """
        if self.current is not None and self.target is not None:
            if self.current > self.target:
                raise ValueError('Valor atual não pode ser maior que o valor alvo')
        return self


class GoalResponse(Goal):
    """Schema usado para RESPOSTAS da API"""
    id: str = Field(..., description="ID da meta")
    
    # ========== CAMPOS CALCULADOS ==========
    
    @computed_field
    @property
    def progress_percentage(self) -> float:
        """
        🔧 NOVO: Calcula o percentual de progresso da meta.
        Útil para o frontend exibir a barra de progresso.
        """
        if self.target == 0:
            return 0.0
        return round((self.current / self.target) * 100, 1)
    
    @computed_field
    @property
    def remaining_amount(self) -> int:
        """
        🔧 NOVO: Calcula o valor que falta para atingir a meta (em centavos).
        Útil para o frontend exibir "Faltam R$ X".
        """
        remaining = self.target - self.current
        return max(remaining, 0)


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. target: float → int (centavos)
2. current: float → int (centavos)
3. Removido round_amount (não necessário para int)
4. Removido unit (deve vir do perfil do usuário)
5. Adicionada validação current <= target
6. 🔧 NOVO: progress_percentage calculado automaticamente
7. 🔧 NOVO: remaining_amount calculado automaticamente
8. 🔧 NOVO: model_validator para conversão de ObjectId
9. 🔧 NOVO: Método touch() para updated_at
10. 🔧 CORRIGIDO: sync_completed permite conclusão manual
11. 🔧 CORRIGIDO: Removida validação redundante (simplificada)
12. 🔧 i18n: Mensagens de erro documentadas com chaves para referência

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_GOAL_CURRENT_EXCEEDS_TARGET → "Valor atual não pode ser maior que o valor alvo"

⏳ PENDÊNCIAS PÓS-MVP:
================================================================================
1. Adicionar deadline (data limite para concluir a meta)
2. Adicionar campo de prioridade (baixa, média, alta)
3. Adicionar category com Literal (categorias pré-definidas)
4. Adicionar campo de descrição da meta

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int + i18n)
================================================================================
"""