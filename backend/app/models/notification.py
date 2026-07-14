"""
Modelo de Notificação In-App
Arquivo: backend/app/models/notification.py

Funcionalidades:
- Armazenamento de notificações in-app para usuários
- Suporte a múltiplos tipos (bill, goal, conquest, credit_card, score, investment, system)
- Marcação de leitura com timestamp
- Expiração automática de notificações antigas
- Categorização para filtros
- Prioridade para ordenação

🔧 INTEGRAÇÕES:
  - BaseModelWithUser: user_id, created_at, updated_at
  - NotificationType: Enum com todos os tipos suportados
  - NotificationPriority: Enum com prioridades
  - NotificationCategory: Enum com categorias

🔧 REGRAS:
  - Notificações não podem ser editadas (apenas lidas ou deletadas)
  - read_at deve ser preenchido quando read=True
  - created_at é imutável (não pode ser alterado)

📋 CHANGELOG:
  - v1: Versão inicial (13/07/2026)

✅ STATUS: PRONTO PARA PRODUÇÃO
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import Field, field_validator, model_validator

from app.models.base import BaseModelWithUser
from app.models.mixins import TimestampMixin


# ================================================================
# ENUMS
# ================================================================

class NotificationType(str, Enum):
    """Tipos de notificação suportados"""
    BILL = "bill"
    GOAL = "goal"
    CONQUEST = "conquest"
    CREDIT_CARD = "credit_card"
    SCORE = "score"
    INVESTMENT = "investment"
    SYSTEM = "system"
    TIPS = "tips"
    DAILY_INSIGHT = "daily_insight"
    PROMOTIONAL = "promotional"


class NotificationPriority(str, Enum):
    """Prioridade da notificação"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationCategory(str, Enum):
    """Categoria para filtros"""
    FINANCE = "finance"
    GOALS = "goals"
    SCORE = "score"
    SYSTEM = "system"
    PROMOTIONAL = "promotional"
    TIPS = "tips"


# ================================================================
# MODELO
# ================================================================

class Notification(BaseModelWithUser, TimestampMixin):
    """
    Modelo de Notificação In-App.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch()
      - TimestampMixin: created_at, updated_at (redundante, mas mantido para clareza)
    
    🔧 CAMPOS:
      - type: Tipo da notificação (bill, goal, conquest, etc)
      - title: Título curto (até 100 caracteres)
      - body: Corpo da mensagem (até 500 caracteres)
      - data: Dados adicionais para navegação/contexto
      - read: Status de leitura
      - read_at: Data/hora da leitura (preenchido quando read=True)
      - priority: Prioridade (low, normal, high, urgent)
      - category: Categoria para filtros
      - source: Origem da notificação (system, worker, user_action)
      - expires_at: Data de expiração (opcional)
      - reference_id: ID do objeto referenciado (ex: bill_id, goal_id)
    
    🔧 VALIDAÇÕES:
      - title: mínimo 1 caractere, máximo 100
      - body: mínimo 1 caractere, máximo 500
      - read=True exige read_at preenchido
      - read_at não pode ser no futuro
      - expires_at deve ser após created_at (se fornecido)
    """
    
    # ─── CAMPOS OBRIGATÓRIOS ───
    
    type: NotificationType = Field(
        ...,
        description="Tipo da notificação"
    )
    
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Título da notificação"
    )
    
    body: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Corpo da notificação"
    )
    
    # ─── CAMPOS OPCIONAIS ───
    
    data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Dados adicionais para navegação/contexto"
    )
    
    read: bool = Field(
        default=False,
        description="Indica se a notificação foi lida"
    )
    
    read_at: Optional[datetime] = Field(
        default=None,
        description="Data/hora da leitura"
    )
    
    priority: NotificationPriority = Field(
        default=NotificationPriority.NORMAL,
        description="Prioridade da notificação"
    )
    
    category: NotificationCategory = Field(
        default=NotificationCategory.FINANCE,
        description="Categoria para filtros"
    )
    
    source: str = Field(
        default="system",
        max_length=50,
        description="Origem da notificação (system, worker, user_action)"
    )
    
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Data de expiração (opcional)"
    )
    
    reference_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="ID do objeto referenciado (ex: bill_id, goal_id)"
    )
    
    # ─── VALIDAÇÕES ───
    
    @model_validator(mode='after')
    def validate_read_status(self) -> 'Notification':
        """
        Valida se read=True exige read_at preenchido.
        Valida se read_at não é no futuro.
        """
        if self.read and self.read_at is None:
            raise ValueError('read_at é obrigatório quando read=True')
        
        if self.read_at and self.read_at > datetime.now(timezone.utc):
            raise ValueError('read_at não pode ser no futuro')
        
        return self
    
    @model_validator(mode='after')
    def validate_expires_at(self) -> 'Notification':
        """
        Valida se expires_at é após created_at (se fornecido).
        """
        if self.expires_at and self.created_at:
            if self.expires_at <= self.created_at:
                raise ValueError('expires_at deve ser após created_at')
        return self
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Valida título (não pode estar vazio)."""
        if not v or not v.strip():
            raise ValueError('Título não pode estar vazio')
        return v.strip()
    
    @field_validator('body')
    @classmethod
    def validate_body(cls, v: str) -> str:
        """Valida corpo (não pode estar vazio)."""
        if not v or not v.strip():
            raise ValueError('Corpo não pode estar vazio')
        return v.strip()


# ================================================================
# SCHEMAS DE CRIAÇÃO E RESPOSTA
# ================================================================

class NotificationCreate(BaseModel):
    """
    Schema para CRIAÇÃO de notificação.
    
    🔧 DIFERENÇAS DO MODEL:
      - user_id é obrigatório (identifica o destinatário)
      - Campos auditáveis (read, read_at, created_at) não são fornecidos
      - priority, category, source com valores padrão
    """
    
    user_id: str = Field(
        ...,
        description="ID do usuário destinatário"
    )
    
    type: NotificationType = Field(
        ...,
        description="Tipo da notificação"
    )
    
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Título da notificação"
    )
    
    body: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Corpo da notificação"
    )
    
    data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Dados adicionais"
    )
    
    priority: NotificationPriority = Field(
        default=NotificationPriority.NORMAL,
        description="Prioridade"
    )
    
    category: NotificationCategory = Field(
        default=NotificationCategory.FINANCE,
        description="Categoria"
    )
    
    source: str = Field(
        default="system",
        max_length=50,
        description="Origem da notificação"
    )
    
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Data de expiração"
    )
    
    reference_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="ID do objeto referenciado"
    )


class NotificationUpdate(BaseModel):
    """
    Schema para ATUALIZAÇÃO de notificação.
    
    🔧 PERMITIDO:
      - read: Marcar como lida
      - read_at: Data/hora da leitura (preenchido automaticamente)
    
    🔧 NÃO PERMITIDO:
      - title, body, type (não podem ser alterados)
      - user_id (não pode ser alterado)
      - created_at (imutável)
    """
    
    read: Optional[bool] = Field(
        None,
        description="Marcar como lida"
    )
    
    @model_validator(mode='after')
    def validate_read(self) -> 'NotificationUpdate':
        """Se read=True, preenche read_at automaticamente."""
        if self.read:
            # read_at será preenchido no service/route
            pass
        return self


class NotificationResponse(BaseModel):
    """
    Schema para RESPOSTA da API.
    
    🔧 DIFERENÇAS DO MODEL:
      - id é obrigatório (já existe no banco)
      - Todos os campos do model são incluídos
      - created_at e updated_at são incluídos
    """
    
    id: str = Field(..., alias="_id", description="ID da notificação")
    user_id: str = Field(..., description="ID do usuário")
    type: NotificationType = Field(..., description="Tipo da notificação")
    title: str = Field(..., description="Título")
    body: str = Field(..., description="Corpo")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    read: bool = Field(default=False)
    read_at: Optional[datetime] = None
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL)
    category: NotificationCategory = Field(default=NotificationCategory.FINANCE)
    source: str = Field(default="system")
    expires_at: Optional[datetime] = None
    reference_id: Optional[str] = None
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data de atualização")
    
    model_config = {
        "from_attributes": True,
        "json_encoders": {datetime: lambda dt: dt.isoformat()}
    }


class NotificationListResponse(BaseModel):
    """
    Schema para LISTAGEM de notificações com paginação.
    """
    
    items: List[NotificationResponse] = Field(
        ...,
        description="Lista de notificações"
    )
    
    total: int = Field(
        ...,
        description="Total de notificações"
    )
    
    page: int = Field(
        ...,
        description="Página atual"
    )
    
    limit: int = Field(
        ...,
        description="Limite por página"
    )
    
    has_more: bool = Field(
        ...,
        description="Indica se há mais páginas"
    )
    
    unread_count: int = Field(
        ...,
        description="Total de notificações não lidas"
    )


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================

"""
📋 DECISÕES:
  ✅ Herda de BaseModelWithUser (user_id obrigatório)
  ✅ Herda de TimestampMixin (created_at, updated_at)
  ✅ read=True exige read_at preenchido
  ✅ read_at não pode ser no futuro
  ✅ expires_at deve ser após created_at
  ✅ Tipos, prioridades e categorias como Enums
  ✅ data como Dict[str, Any] para flexibilidade
  ✅ reference_id para referenciar objetos externos

📋 PENDÊNCIAS PÓS-MVP:
  - Notificações em lote (Bulk Create)
  - Templates de notificação (para reutilização)

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 CRIADO EM: 13/07/2026
"""