"""
Modelo de Investimento para MongoDB
Arquivo: backend/app/models/investment.py

✅ Define a estrutura do documento de investimento
✅ Usado pelas rotas e schemas
✅ 🔧 CORREÇÃO: timezone UTC, padronização _id
"""

from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field
from bson import ObjectId

class Investment(BaseModel):
    """Modelo de investimento para o MongoDB"""
    
    id: Optional[str] = Field(None, alias="_id")
    user_id: str  # ID do usuário (referência)
    name: str  # Nome do investimento
    amount: float  # Valor investido (R$)
    category: Literal["renda_fixa", "acoes", "fiis", "cripto", "outros"]  # Categoria
    purchase_date: datetime  # Data da compra
    quantity: Optional[float] = None  # Quantidade de cotas/ações
    current_value: Optional[float] = None  # Valor atualizado (opcional)
    notes: Optional[str] = None  # Observações
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        populate_by_name = True