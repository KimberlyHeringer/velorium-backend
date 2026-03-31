# app/models/credit_card.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

class CreditCard(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    id: Optional[str] = Field(None, alias="_id")  # ← alias garante que o campo "_id" do MongoDB vire "id"
    user_id: str
    name: str
    brand: Optional[str] = None
    closing_day: int = Field(..., ge=1, le=31)
    due_day: int = Field(..., ge=1, le=31)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Modelo para criar (não tem id)
class CreditCardCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    closing_day: int
    due_day: int

# Modelo de resposta (apenas id, sem user_id e datas internas? na verdade reutiliza CreditCard)
class CreditCardResponse(CreditCard):
    # herdamos todos os campos, inclusive id com alias
    pass