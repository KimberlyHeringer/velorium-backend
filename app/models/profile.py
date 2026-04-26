# backend/app/models/profile.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

class UserProfile(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str  # referência ao User

    # Bloco 1: Psicologia Financeira
    money_feeling: Optional[str] = None
    post_purchase: Optional[str] = None
    satisfaction: Optional[str] = None
    planning_habit: Optional[str] = None

    # Bloco 2: Metas Pessoais
    dream_5y: Optional[str] = None
    dream_other: Optional[str] = None
    dream_value: Optional[str] = None  # string ou número? vamos manter string
    emergency_target: Optional[str] = None
    next_year_goals: Optional[List[str]] = []
    next_year_goal_value: Optional[str] = None

    # Bloco 3: Hábitos de Consumo
    spending_blindspot: Optional[str] = None
    price_comparison: Optional[str] = None
    money_phrase: Optional[str] = None

    # Bloco 4: Tolerância a Risco
    risk_scenario: Optional[str] = None
    risk_phrase: Optional[str] = None
    has_debt: Optional[str] = None
    credit_card_behavior: Optional[str] = None

    # Metadados
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserProfileCreate(BaseModel):
    # mesmo que UserProfile, mas sem id, user_id, created_at, updated_at
    money_feeling: Optional[str] = None
    post_purchase: Optional[str] = None
    satisfaction: Optional[str] = None
    planning_habit: Optional[str] = None
    dream_5y: Optional[str] = None
    dream_other: Optional[str] = None
    dream_value: Optional[str] = None
    emergency_target: Optional[str] = None
    next_year_goals: Optional[List[str]] = []
    next_year_goal_value: Optional[str] = None
    spending_blindspot: Optional[str] = None
    price_comparison: Optional[str] = None
    money_phrase: Optional[str] = None
    risk_scenario: Optional[str] = None
    risk_phrase: Optional[str] = None
    has_debt: Optional[str] = None
    credit_card_behavior: Optional[str] = None


class UserProfileResponse(UserProfile):
    pass