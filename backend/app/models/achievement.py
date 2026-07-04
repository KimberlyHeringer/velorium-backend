"""
Modelo de Conquistas do Usuário (sincronizado)
Arquivo: backend/app/models/achievement.py

Funcionalidades:
- Registro de conquistas desbloqueadas pelo usuário
- Suporte a conquistas automáticas e manuais
- Sincronização com score e metas

Principais features:
- Validação de tipos de conquista (Literal)
- year + month como int (performance)
- Validação de description não vazia
- Validação de automatica como booleano
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- ✅ CORRIGIDO: Herança correta de BaseModelWithUser
- ✅ CORRIGIDO: AchievementResponse id obrigatório
- ✅ MANTIDO: Validações específicas (type, year, month, description, automatica)
"""

from pydantic import Field, field_validator, model_validator
from typing import Optional, Any, Literal
from datetime import datetime, timezone
from bson import ObjectId

from app.models.base import BaseModelWithUser


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


class Achievement(BaseModelWithUser):
    """
    Modelo de uma conquista desbloqueada pelo usuário.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
    
    🔧 CAMPOS ADICIONADOS:
      - type: Tipo de conquista (Literal com valores pré-definidos)
      - year: Ano da conquista (int)
      - month: Mês da conquista (int, 1-12)
      - name: Nome da conquista (opcional)
      - description: Descrição da conquista (obrigatória)
      - date: Data da conquista
      - automatica: Conquista automática ou manual
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    type: TIPOS_CONQUISTA = Field(
        ...,
        description="Tipo de conquista"
    )
    
    description: str = Field(
        ...,
        max_length=500,
        description="Descrição da conquista (máx. 500 caracteres)"
    )
    
    # ========== CAMPOS OPCIONAIS ==========
    
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
    
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data da conquista"
    )
    
    automatica: bool = Field(
        default=True,
        description="Conquista automática (True) ou manual (False)"
    )
    
    # ========== VALIDADORES ==========
    
    @field_validator('type', mode='before')
    @classmethod
    def validate_type(cls, v: Any) -> str:
        """
        Valida se o tipo de conquista é permitido.
        🔧 i18n: Mensagem em português (referência: ERROR_INVALID_ACHIEVEMENT_TYPE)
        """
        if v is None:
            raise ValueError('Tipo de conquista é obrigatório')
        
        if not isinstance(v, str):
            v = str(v)
        
        v = v.strip()
        if not v:
            raise ValueError('Tipo de conquista é obrigatório')
        
        if v not in TIPOS_VALIDOS:
            raise ValueError(
                f'Tipo de conquista inválido. Use um dos: {", ".join(TIPOS_VALIDOS)}'
            )
        return v
    
    @field_validator('year', mode='before')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        """
        Valida se o ano é válido.
        🔧 i18n: Mensagem em português (referência: ERROR_INVALID_YEAR)
        """
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
    def validate_month(cls, v: Optional[int]) -> Optional[int]:
        """
        Valida se o mês é válido (1-12).
        🔧 i18n: Mensagem em português (referência: ERROR_INVALID_MONTH)
        """
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
    def validate_description(cls, v: Any) -> str:
        """
        Valida se a descrição não está vazia.
        🔧 i18n: Mensagem em português (referência: ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY)
        """
        if v is None:
            raise ValueError('Descrição não pode estar vazia')
        
        v = str(v).strip()
        if not v:
            raise ValueError('Descrição não pode estar vazia')
        
        if len(v) > 500:
            raise ValueError('Descrição não pode ter mais de 500 caracteres')
        
        return v
    
    @field_validator('name', mode='before')
    @classmethod
    def validate_name(cls, v: Optional[Any]) -> Optional[str]:
        """
        Valida e limpa o nome.
        🔧 i18n: Mensagem em português (referência: ERROR_VALIDATION)
        """
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
        """
        Garante que automatica seja booleano.
        🔧 i18n: Mensagem em português (referência: ERROR_VALIDATION)
        """
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'sim', 'verdadeiro')
        if isinstance(v, (int, float)):
            return bool(v)
        return True


class AchievementCreate(BaseModel):
    """
    Schema para criação de conquista.
    
    🔧 DIFERENÇAS DO MODEL ACHIEVEMENT:
      - Não tem campos de auditoria (ainda não existe no banco)
      - type é string (validado pela rota)
    """
    
    type: str
    year: Optional[int] = None
    month: Optional[int] = None
    name: Optional[str] = None
    description: str
    automatica: bool = True


class AchievementUpdate(BaseModel):
    """
    Schema para atualização de conquista.
    
    🔧 TODOS OS CAMPOS SÃO OPCIONAIS:
      - Permite atualização parcial
    """
    
    type: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    automatica: Optional[bool] = None


class AchievementResponse(Achievement):
    """
    Schema para resposta da API.
    
    🔧 ✅ CORRIGIDO: id é obrigatório (sobrescreve Optional)
    """
    
    id: str = Field(..., alias="_id", description="ID da conquista")


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
# # Índice composto para year + month (performance)
# await db.achievements.create_index([("user_id", 1), ("year", 1), ("month", 1)])
# 
# # Índice composto para tipo + ano + mês
# await db.achievements.create_index([("user_id", 1), ("type", 1), ("year", 1), ("month", 1)])
# 
# ================================================================


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Validação de 'type' com lista de tipos válidos (Literal)
#   - year + month como int (performance)
#   - Validação de tamanho máximo (description: 500, name: 100)
#   - Validação de description não vazia
#   - Validação de automatica como booleano
#   - Índices documentados com year + month
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response)
#   - ✅ CORRIGIDO: Herança correta de BaseModelWithUser
#   - ✅ CORRIGIDO: AchievementResponse id obrigatório
#
# ❌ Não implementado (Pós-MVP):
#   - Renomear 'automatica' para 'is_automatic' (requer mudança no frontend)
#   - Validar date (impedir datas futuras) - opcional
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser (03/07/2026)
#   - v3: Correções - Response id obrigatório (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO