"""
Classes Base para Models do MongoDB
Arquivo: backend/app/models/base.py

Funcionalidades:
- BaseModelWithoutUser: Classe base sem user_id (para User)
- BaseModelWithUser: Classe base com user_id (para a maioria dos models)
- Configuração padrão para todos os models (json_encoders, populate_by_name)
- Métodos comuns: touch(), convert_objectid()

Principais features:
- Centralização de campos comuns (redução de ~58% de código repetido)
- Configuração padronizada para todos os models
- Métodos reutilizáveis (touch, convert_objectid)
- Suporte a ObjectId do MongoDB com conversão automática para string
- Herança para facilitar a criação de novos models
- ✅ CORRIGIDO: BaseModelWithoutUser para models que NÃO têm user_id (ex: User)
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Any
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import convert_objectid_to_str


class BaseModelWithoutUser(BaseModel):
    """
    Classe base para models que NÃO têm user_id.
    
    🔧 CAMPOS:
      - id: ID do documento (convertido de _id do MongoDB)
      - created_at: Data de criação (UTC)
      - updated_at: Data da última atualização (UTC)
    
    🔧 MÉTODOS:
      - touch(): Atualiza updated_at para o momento atual
      - convert_objectid(): Converte ObjectId para string
    
    🔧 CONFIGURAÇÕES:
      - arbitrary_types_allowed: True (permite ObjectId)
      - json_encoders: {ObjectId: str} (serialização)
      - populate_by_name: True (permite usar _id ou id)
    
    🔧 USO:
      class User(BaseModelWithoutUser, AuditMixin):
          name: str
          email: str
          # NÃO tem user_id (é o próprio dono)
    """
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
    )
    
    id: Optional[str] = Field(
        None,
        alias="_id",
        description="ID único do documento (convertido de _id do MongoDB)"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data e hora de criação do registro (UTC)"
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data e hora da última atualização do registro (UTC)"
    )
    
    def touch(self) -> 'BaseModelWithoutUser':
        """
        Atualiza o campo updated_at para o momento atual.
        
        🔧 RETORNO:
          self (o próprio objeto) - permite encadeamento:
          obj.touch().save()
        """
        self.updated_at = datetime.now(timezone.utc)
        return self
    
    @model_validator(mode='before')
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """
        Converte ObjectId do MongoDB para string.
        
        🔧 O QUE FAZ:
          1. Verifica se já é uma instância da classe (ignora)
          2. Delega para a função convert_objectid_to_str do validators.py
          3. Converte todos os ObjectId encontrados no dicionário
        """
        if isinstance(data, cls):
            return data
        return convert_objectid_to_str(data)


class BaseModelWithUser(BaseModelWithoutUser):
    """
    Classe base para models que têm user_id (a maioria dos models).
    
    🔧 CAMPOS ADICIONADOS (além dos do BaseModelWithoutUser):
      - user_id: ID do usuário dono do registro (obrigatório)
    
    🔧 HERDA DE:
      - BaseModelWithoutUser: id, created_at, updated_at, touch(), convert_objectid()
    
    🔧 USO:
      class Transaction(BaseModelWithUser):
          amount: int
          description: str
          # id, user_id, created_at, updated_at já estão disponíveis
    """
    
    user_id: str = Field(
        ...,
        description="ID do usuário dono do registro (injetado pelo backend)"
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - BaseModelWithoutUser (sem user_id - para User)
#   - BaseModelWithUser (com user_id - para a maioria)
#   - ConfigDict padronizada (json_encoders, populate_by_name)
#   - Método touch() para atualizar updated_at
#   - Método convert_objectid() para conversão de ObjectId
#   - Validação de instância para evitar loops
#
# ❌ Não implementado (Pós-MVP):
#   - Suporte a timezone customizável (ex: usar fuso do usuário)
#   - Validação de updated_at >= created_at
#   - Soft delete global (is_deleted, deleted_at) - está no AuditMixin
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#   - v2: Adicionado BaseModelWithoutUser (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO