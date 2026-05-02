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
    """
    Modelo principal de Usuário.
    Contém dados de autenticação e perfil básico.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: Optional[str] = Field(None, alias="_id")
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password_hash: str  # armazenado com hash (bcrypt)
    monthly_income: float = Field(default=0.0, ge=0)  # ← trocado para float
    location: str = Field(default="", max_length=200)
    profession_type: str = Field(default="", max_length=50)
    occupation: str = Field(default="", max_length=100)
    financial_goal: str = Field(default="", max_length=500)
    
    # Campo para consentimento de uso de dados (futuro)
    research_consent: bool = Field(default=False)
    consent_updated_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(BaseModel):
    """Schema usado para CRIAR um novo usuário (cadastro)"""
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    monthly_income: float = Field(default=0.0, ge=0)  # ← trocado para float
    location: str = Field(default="", max_length=200)
    profession_type: str = Field(default="", max_length=50)
    occupation: str = Field(default="", max_length=100)
    financial_goal: str = Field(default="", max_length=500)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Valida força da senha (mínimo 8 caracteres, maiúscula, número, especial)"""
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
    """Schema usado para LOGIN"""
    model_config = ConfigDict(populate_by_name=True)
    
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Modelo seguro para respostas - SEM password_hash"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )
    
    id: str = Field(..., alias="_id")  # ← agora obrigatório (não Optional)
    name: str
    email: EmailStr
    monthly_income: float  # ← trocado para float
    location: str
    profession_type: str
    occupation: str
    financial_goal: str
    created_at: datetime
    research_consent: bool = False  # opcional, para uso futuro


class Token(BaseModel):
    """Schema para resposta de autenticação (JWT)"""
    model_config = ConfigDict(populate_by_name=True)
    
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserUpdate(BaseModel):
    """Schema para atualização de perfil (opcional)"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    monthly_income: Optional[float] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=200)
    profession_type: Optional[str] = Field(None, max_length=50)
    occupation: Optional[str] = Field(None, max_length=100)
    financial_goal: Optional[str] = Field(None, max_length=500)
    research_consent: Optional[bool] = None


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