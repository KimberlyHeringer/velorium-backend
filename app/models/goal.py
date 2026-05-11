"""
Modelo de Metas Financeiras (Goals)
Arquivo: backend/app/models/goal.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId


class Goal(BaseModel):
    """
    Modelo principal de Meta Financeira.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str                                    # injetado pelo backend
    name: str = Field(..., min_length=1)            # nome da meta (obrigatório)
    target: float = Field(..., gt=0)                # valor alvo (positivo)
    current: float = Field(default=0, ge=0)         # valor já acumulado
    category: Optional[str] = None                  # categoria (economia, pagamento, investimento)
    unit: str = "R$"                                # unidade (R$, kg, km, etc.)
    completed: bool = False                         # se a meta foi atingida (sincronizado via validador)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def sync_completed(self):
        """
        Sincroniza o campo completed com base em current >= target.
        Resolve o problema de dessincronização se current ou target forem alterados.
        """
        self.completed = self.current >= self.target
        return self

    @field_validator('target', 'current')
    @classmethod
    def round_amount(cls, v):
        """Arredonda valores monetários para 2 casas decimais"""
        return round(v, 2) if v is not None else v


class GoalCreate(BaseModel):
    """Schema usado para CRIAR uma nova meta"""
    name: str = Field(..., min_length=1)
    target: float = Field(..., gt=0)
    current: float = Field(default=0, ge=0)
    category: Optional[str] = None
    unit: str = "R$"

    @field_validator('target', 'current')
    @classmethod
    def round_amount(cls, v):
        return round(v, 2) if v is not None else v


class GoalUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma meta existente"""
    name: Optional[str] = None
    target: Optional[float] = Field(None, gt=0)
    current: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    unit: Optional[str] = None
    completed: Optional[bool] = None   # normalmente não se envia, será sobrescrito

    @field_validator('target', 'current')
    @classmethod
    def round_amount(cls, v):
        return round(v, 2) if v is not None else v


class GoalResponse(Goal):
    """Schema usado para RESPOSTAS da API (garante id como string)"""
    id: str


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Padronizado created_at / updated_at (snake_case)
# ✅ Adicionado validador sync_completed (mantém completed sincronizado)
# ✅ Mantido campo completed (útil para consultas diretas)
# ✅ Adicionado round() para valores monetários
# ✅ Adicionado min_length=1 para name
# ✅ GoalResponse com id: str (não opcional)
#
# ⏳ Validação current <= target: postergada (não crítica para MVP)
# ⏳ Validação de unit (Enum): postergada (pode vir depois)
# ⏳ updated_at automático: postergado (rotas atualizam manualmente)