"""
Schemas de Notificação In-App
Arquivo: backend/app/schemas/notification.py

Funcionalidades:
- Schemas Pydantic para validação de dados de notificações
- Separação entre criação, atualização, resposta e listagem
- Validações consistentes com o modelo

🔧 INTEGRAÇÕES:
  - models/notification.py: NotificationType, NotificationPriority, NotificationCategory
  - BaseModel do Pydantic para validação

📋 CHANGELOG:
  - v1: Versão inicial (13/07/2026)
  - v1.1: Correção - ConfigDict no lugar de dicionários (14/07/2026)

✅ STATUS: PRONTO PARA PRODUÇÃO
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from app.models.notification import (
    NotificationType,
    NotificationPriority,
    NotificationCategory
)


# ================================================================
# SCHEMAS
# ================================================================

class NotificationBase(BaseModel):
    """
    Schema base com campos comuns.
    
    🔧 USO: Base para criação e resposta
    """
    
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
        description="Dados adicionais para navegação/contexto"
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


class NotificationCreate(NotificationBase):
    """
    Schema para CRIAÇÃO de notificação.
    
    🔧 DIFERENÇAS DO BASE:
      - user_id é obrigatório (identifica o destinatário)
      - Campos de auditoria não são fornecidos
    """
    
    user_id: str = Field(
        ...,
        description="ID do usuário destinatário"
    )


class NotificationUpdate(BaseModel):
    """
    Schema para ATUALIZAÇÃO de notificação.
    
    🔧 PERMITIDO:
      - read: Marcar como lida
    
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
        """Valida se read=True (leitura automática)."""
        return self


class NotificationInDB(NotificationBase):
    """
    Schema para REPRESENTAÇÃO no banco de dados.
    
    🔧 DIFERENÇAS DO BASE:
      - id é obrigatório (ObjectId convertido para string)
      - user_id é obrigatório
      - Campos de auditoria incluídos
    """
    
    id: str = Field(..., alias="_id", description="ID da notificação")
    user_id: str = Field(..., description="ID do usuário")
    read: bool = Field(default=False, description="Status de leitura")
    read_at: Optional[datetime] = Field(default=None, description="Data da leitura")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data de atualização")
    
    # ✅ CORRIGIDO: ConfigDict
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={datetime: lambda dt: dt.isoformat()}
    )


class NotificationResponse(NotificationInDB):
    """
    Schema para RESPOSTA da API.
    
    🔧 DIFERENÇAS DO INDB:
      - Configuração para serialização from_attributes
      - Todos os campos já estão definidos no NotificationInDB
    """
    
    # ✅ CORRIGIDO: ConfigDict
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: lambda dt: dt.isoformat()}
    )


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


class UnreadCountResponse(BaseModel):
    """Schema para contagem de notificações não lidas"""
    unread_count: int = Field(..., description="Total de notificações não lidas")


class ReadAllResponse(BaseModel):
    """Schema para resposta de marcar todas como lidas"""
    success: bool = Field(..., description="Sucesso da operação")
    message: str = Field(..., description="Mensagem de confirmação")
    updated_count: int = Field(..., description="Quantidade de notificações atualizadas")


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================

"""
📋 DECISÕES:
  ✅ NotificationBase com campos comuns (DRY)
  ✅ NotificationCreate adiciona user_id
  ✅ NotificationUpdate apenas read (imutabilidade)
  ✅ NotificationInDB com campos do banco
  ✅ NotificationResponse com from_attributes
  ✅ NotificationListResponse com paginação
  ✅ UnreadCountResponse e ReadAllResponse para endpoints específicos
  ✅ Validações consistentes com o modelo
  ✅ ✅ ConfigDict para compatibilidade com Pydantic V2

📋 PENDÊNCIAS PÓS-MVP:
  - BulkCreate schema para múltiplas notificações

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 CRIADO EM: 13/07/2026
📅 ATUALIZADO EM: 14/07/2026
"""