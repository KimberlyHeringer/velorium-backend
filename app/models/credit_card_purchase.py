from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

class CreditCardPurchase(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    card_id: str
    description: str
    total_amount: float
    installments: int = Field(..., ge=1, le=12)
    first_due_date: datetime
    category: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CreditCardPurchaseCreate(BaseModel):
    card_id: str
    description: str
    total_amount: float
    installments: int
    first_due_date: datetime
    category: Optional[str] = None
    notes: Optional[str] = None

class CreditCardPurchaseResponse(CreditCardPurchase):
    id: str