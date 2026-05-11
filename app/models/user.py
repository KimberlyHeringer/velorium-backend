"""
Modelo de Usuário
Arquivo: backend/app/models/user.py
"""

from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId
import re


class User(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: Optional[str] = Field(None, alias="_id")
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password_hash: str
    monthly_income: float = Field(default=0.0, ge=0)
    location: str = Field(default="", max_length=200)
    profession_type: str = Field(default="", max_length=50)
    occupation: str = Field(default="", max_length=100)
    financial_goal: str = Field(default="", max_length=500)
    
    # Consentimento para uso de dados em IA (research_consent)
    research_consent: bool = Field(default=False)
    # Aceitação dos Termos de Uso (obrigatório)
    terms_accepted: bool = Field(default=False)
    terms_accepted_at: Optional[datetime] = None
    consent_updated_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    monthly_income: float = Field(default=0.0, ge=0)
    location: str = Field(default="", max_length=200)
    profession_type: str = Field(default="", max_length=50)
    occupation: str = Field(default="", max_length=100)
    financial_goal: str = Field(default="", max_length=500)
    # Novos campos no cadastro (opcional, mas recomendado)
    terms_accepted: bool = Field(default=False)
    research_consent: bool = Field(default=False)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('A senha deve ter pelo menos 8 caracteres')
        if not re.search(r"[A-Z]", v):
            raise ValueError('A senha deve conter pelo menos uma letra maiúscula')
        if not re.search(r"\d", v):
            raise ValueError('A senha deve conter pelo menos um número')
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError('A senha deve conter pelo menos um caractere especial')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: str = Field(..., alias="_id")
    name: str
    email: EmailStr
    monthly_income: float
    location: str
    profession_type: str
    occupation: str
    financial_goal: str
    created_at: datetime
    research_consent: bool = False
    terms_accepted: bool = False      # ← NOVO
    terms_accepted_at: Optional[datetime] = None   # ← NOVO


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    monthly_income: Optional[float] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=200)
    profession_type: Optional[str] = Field(None, max_length=50)
    occupation: Optional[str] = Field(None, max_length=100)
    financial_goal: Optional[str] = Field(None, max_length=500)
    research_consent: Optional[bool] = None
    terms_accepted: Optional[bool] = None   # ← NOVO

# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Trocado monthly_income de Decimal para float (compatibilidade MongoDB)
# ✅ UserResponse com id: str (não opcional)
# ✅ Adicionado campo research_consent (futuro/pós-MVP)
# ✅ Adicionado UserUpdate (para edição de perfil)
# ✅ Mantida validação forte de senha
# ✅ Adicionados comentários explicativos
#
# 📌 Normalização de email (lowercase): será feita nas rotas, não no model
# 📅 research_consent: será usado futuramente para coleta de dados anônimos