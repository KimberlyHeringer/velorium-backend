"""
Modelo de Metas Financeiras (Goals)
Arquivo: backend/app/models/goal.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import round_amount  # ← centralizado


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
    user_id: str
    name: str = Field(..., min_length=1)
    target: float = Field(..., gt=0)
    current: float = Field(default=0, ge=0)
    category: Optional[str] = None
    unit: str = "R$"
    completed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def sync_completed(self):
        """Sincroniza completed baseado em current >= target"""
        self.completed = self.current >= self.target
        return self

    @model_validator(mode='after')
    def round_amounts(self):
        """Arredonda valores usando função centralizada"""
        if self.target is not None:
            self.target = round_amount(self.target)
        if self.current is not None:
            self.current = round_amount(self.current)
        return self


class GoalCreate(BaseModel):
    """Schema usado para CRIAR uma nova meta"""
    name: str = Field(..., min_length=1)
    target: float = Field(..., gt=0)
    current: float = Field(default=0, ge=0)
    category: Optional[str] = None
    unit: str = "R$"

    @model_validator(mode='after')
    def round_amounts(self):
        if self.target is not None:
            self.target = round_amount(self.target)
        if self.current is not None:
            self.current = round_amount(self.current)
        return self


class GoalUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma meta existente"""
    name: Optional[str] = None
    target: Optional[float] = Field(None, gt=0)
    current: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    unit: Optional[str] = None
    completed: Optional[bool] = None

    @model_validator(mode='after')
    def round_amounts(self):
        if self.target is not None:
            self.target = round_amount(self.target)
        if self.current is not None:
            self.current = round_amount(self.current)
        return self


class GoalResponse(Goal):
    """Schema usado para RESPOSTAS da API"""
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