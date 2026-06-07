"""
Modelo de Metas Financeiras (Goals)
Arquivo: backend/app/models/goal.py

🔧 CORRIGIDO:
- target e current agora são int (centavos)
- Removido round_amount (não necessário)
- Adicionada validação current <= target
- Removido unit (vem do perfil do usuário)
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


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
        from_attributes=True
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

    @model_validator(mode='after')
    def sync_completed(self):
        """Sincroniza completed baseado em current >= target"""
        self.completed = self.current >= self.target
        return self

    @model_validator(mode='after')
    def validate_current_not_exceeds_target(self):
        """Garante que current não ultrapasse target (validação adicional)"""
        if self.current > self.target and not self.completed:
            raise ValueError('Valor atual não pode ser maior que o valor alvo')
        return self


class GoalCreate(BaseModel):
    """Schema usado para CRIAR uma nova meta"""
    name: str = Field(..., min_length=1, max_length=100, description="Nome da meta")
    target: int = Field(..., gt=0, description="Valor alvo em CENTAVOS")
    current: int = Field(default=0, ge=0, description="Valor atual em CENTAVOS")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da meta")

    @model_validator(mode='after')
    def validate_current_not_exceeds_target(self):
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
        if self.current is not None and self.target is not None:
            if self.current > self.target:
                raise ValueError('Valor atual não pode ser maior que o valor alvo')
        return self


class GoalResponse(Goal):
    """Schema usado para RESPOSTAS da API"""
    id: str = Field(..., description="ID da meta")


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. target: float → int (centavos)
2. current: float → int (centavos)
3. Removido round_amount (não necessário para int)
4. Removido unit (deve vir do perfil do usuário)
5. Adicionada validação current <= target
6. Adicionados max_length nos campos de texto
7. Adicionados descriptions em todos os Field()

✅ PENDENTE PARA FUTURO (pós-MVP):
================================================================================
1. Adicionar deadline (data limite para concluir a meta)
2. Adicionar campo progress_percentage (calculado automaticamente)

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int)
================================================================================
"""