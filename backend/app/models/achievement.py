"""
Modelo de Conquistas do Usuário (sincronizado)
Arquivo: backend/app/models/achievement.py

🔧 CORRIGIDO (VERSÃO COMPLETA):
- month separado em year (int) + month (int) → melhor performance
- Adicionado model_validator para converter ObjectId para string
- Adicionado max_length em description (500) e name (100)
- Adicionado created_at e updated_at
- field_validator com mode="before"
- Validação de description vazia
- Validação de automatica como booleano
- Índices documentados para performance
- Preparado para i18n (mensagens em português)
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any, Literal
from datetime import datetime, timezone
from bson import ObjectId


# ========== CONSTANTES ==========

TIPOS_CONQUISTA = Literal[
    'month_closed',      # Fechou o mês no azul
    'goal_completed',    # Completou uma meta
    'score_milestone',   # Atingiu uma pontuação de score
    'first_transaction', # Primeira transação cadastrada
    'savings_milestone', # Atingiu meta de economia
    'debt_paid'          # Pagou uma dívida
]

TIPOS_VALIDOS = [
    'month_closed',
    'goal_completed',
    'score_milestone',
    'first_transaction',
    'savings_milestone',
    'debt_paid'
]


# ========== MODELO PRINCIPAL ==========

class Achievement(BaseModel):
    """
    Modelo de uma conquista desbloqueada pelo usuário.
    
    🔧 CORRIGIDO:
    - month separado em year + month (int) → performance
    - Campos de auditoria (created_at, updated_at)
    - Validação de tamanho máximo
    - Validação de tipo com Literal
    - Conversão automática de ObjectId
    """
    
    # ========== CAMPOS PRINCIPAIS ==========
    
    id: Optional[str] = Field(None, alias="_id", description="ID da conquista")
    user_id: str = Field(..., description="ID do usuário")
    type: TIPOS_CONQUISTA = Field(..., description="Tipo de conquista")
    
    # 🔧 CORRIGIDO: month string → year + month (int)
    year: Optional[int] = Field(
        None, 
        ge=1900, 
        le=2100,
        description="Ano da conquista (ex: 2025)"
    )
    month: Optional[int] = Field(
        None, 
        ge=1, 
        le=12,
        description="Mês da conquista (1-12)"
    )
    
    name: Optional[str] = Field(
        None, 
        max_length=100, 
        description="Nome da conquista (opcional)"
    )
    description: str = Field(
        ..., 
        max_length=500, 
        description="Descrição da conquista (máx. 500 caracteres)"
    )
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data da conquista"
    )
    automatica: bool = Field(
        default=True,
        description="Conquista automática (True) ou manual (False)"
    )
    
    # ========== CAMPOS DE AUDITORIA ==========
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de criação do registro"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Data da última atualização"
    )

    # ========== VALIDADORES ==========
    
    @field_validator('type', mode='before')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Valida se o tipo de conquista é permitido."""
        if not v or not v.strip():
            raise ValueError('Tipo de conquista é obrigatório')
        
        v = v.strip()
        if v not in TIPOS_VALIDOS:
            raise ValueError(
                f'Tipo de conquista inválido. Use um dos: {", ".join(TIPOS_VALIDOS)}'
            )
        return v
    
    @field_validator('year', mode='before')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        """Valida se o ano é válido."""
        if v is None:
            return None
        
        try:
            year = int(v)
            if year < 1900 or year > 2100:
                raise ValueError('Ano deve ser entre 1900 e 2100')
            return year
        except (ValueError, TypeError):
            raise ValueError('Ano deve ser um número inteiro')
    
    @field_validator('month', mode='before')
    @classmethod
    def validate_month_int(cls, v: Optional[int]) -> Optional[int]:
        """Valida se o mês é válido (1-12)."""
        if v is None:
            return None
        
        try:
            month = int(v)
            if month < 1 or month > 12:
                raise ValueError('Mês deve ser entre 1 e 12')
            return month
        except (ValueError, TypeError):
            raise ValueError('Mês deve ser um número inteiro')
    
    @field_validator('description', mode='before')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Valida se a descrição não está vazia."""
        if not v or not str(v).strip():
            raise ValueError('Descrição não pode estar vazia')
        
        v = str(v).strip()
        if len(v) > 500:
            raise ValueError('Descrição não pode ter mais de 500 caracteres')
        
        return v
    
    @field_validator('name', mode='before')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Valida e limpa o nome."""
        if v is None:
            return None
        
        v = str(v).strip()
        if not v:
            return None
        
        if len(v) > 100:
            raise ValueError('Nome não pode ter mais de 100 caracteres')
        
        return v
    
    @field_validator('automatica', mode='before')
    @classmethod
    def validate_automatica(cls, v: Any) -> bool:
        """Garante que automatica seja booleano."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'sim', 'verdadeiro')
        if isinstance(v, (int, float)):
            return bool(v)
        return True
    
    # ========== CONVERSÃO DE OBJECTID ==========
    
    @model_validator(mode="before")
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """Converte ObjectId do MongoDB para string."""
        if isinstance(data, dict):
            if isinstance(data.get("_id"), ObjectId):
                data["_id"] = str(data["_id"])
            
            if isinstance(data.get("user_id"), ObjectId):
                data["user_id"] = str(data["user_id"])
            
            if isinstance(data.get("updated_at"), str):
                try:
                    data["updated_at"] = datetime.fromisoformat(
                        data["updated_at"].replace('Z', '+00:00')
                    )
                except (ValueError, TypeError):
                    pass
        
        return data


# ========== SCHEMAS AUXILIARES ==========

class AchievementCreate(BaseModel):
    """Schema para criação de conquista"""
    type: str
    year: Optional[int] = None
    month: Optional[int] = None
    name: Optional[str] = None
    description: str
    automatica: bool = True


class AchievementUpdate(BaseModel):
    """Schema para atualização de conquista."""
    type: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    automatica: Optional[bool] = None


class AchievementResponse(Achievement):
    """Schema para resposta da API"""
    id: str


# ========== ÍNDICES RECOMENDADOS ==========
# 
# 🔧 ADICIONAR EM database.py (ou indexes.py):
# 
# ================================================================
# 10. CONQUISTAS (ACHIEVEMENTS)
# ================================================================
# 
# # Índice básico por usuário
# await db.achievements.create_index([("user_id", 1)])
# 
# # Índice composto para queries com tipo e data
# await db.achievements.create_index([("user_id", 1), ("type", 1), ("date", -1)])
# 
# # 🔧 NOVO: Índice composto para year + month (performance)
# await db.achievements.create_index([("user_id", 1), ("year", 1), ("month", 1)])
# 
# # Índice composto para tipo + ano + mês
# await db.achievements.create_index([("user_id", 1), ("type", 1), ("year", 1), ("month", 1)])
# 
# ================================================================


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Validação de 'type' com lista de tipos válidos
# ✅ 🔧 CORRIGIDO: month (string) → year (int) + month (int)
# ✅ Validação de tamanho máximo (description: 500, name: 100)
# ✅ Validação de description não vazia
# ✅ Conversão de ObjectId para string via model_validator
# ✅ Campos de auditoria (created_at, updated_at)
# ✅ field_validator com mode="before"
# ✅ Uso de timezone.utc para datas
# ✅ Validação de automatica como booleano
# ✅ Índices documentados com year + month
# ✅ Schema de atualização parcial (AchievementUpdate)
#
# ⏳ PENDÊNCIAS PÓS-MVP:
# - Internacionalização (i18n) das mensagens de erro
# - Renomear 'automatica' para 'is_automatic' (requer mudança no frontend)
#
# ✅ STATUS: APROVADO PARA PRODUÇÃO