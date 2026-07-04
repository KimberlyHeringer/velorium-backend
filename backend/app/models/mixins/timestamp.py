"""
Arquivo: backend/app/models/mixins/timestamp.py
Objetivo: Fornecer campos de timestamp (created_at e updated_at) e método touch()

Funcionalidades:
- Adiciona os campos created_at e updated_at
- Fornece o método touch() para atualizar updated_at
- Fornece o método to_dict_with_timestamps() para debugging

Principais features:
- Campos created_at e updated_at com preenchimento automático
- Método touch() para atualizar updated_at manualmente
- Uso de timezone.utc (padrão do projeto)
- Método to_dict_with_timestamps() para debugging
"""

from pydantic import Field
from datetime import datetime, timezone


class TimestampMixin:
    """
    Mixin que adiciona campos de timestamp a um modelo Pydantic.
    
    🔧 CAMPOS ADICIONADOS:
      - created_at: Data/hora de criação (preenchido automaticamente)
      - updated_at: Data/hora da última atualização
    
    🔧 MÉTODOS ADICIONADOS:
      - touch(): Atualiza updated_at para o momento atual
      - to_dict_with_timestamps(): Retorna dicionário com timestamps
    """
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data e hora de criação do registro (UTC)"
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data e hora da última atualização do registro (UTC)"
    )
    
    def touch(self) -> 'TimestampMixin':
        """
        Atualiza o campo updated_at para o momento atual.
        
        🔧 RETORNO:
          self (o próprio objeto) - permite encadeamento:
          obj.touch().save()
        """
        self.updated_at = datetime.now(timezone.utc)
        return self
    
    def to_dict_with_timestamps(self) -> dict:
        """
        Retorna um dicionário com os campos de timestamp.
        Útil para debugging e logs.
        """
        return {
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Campos created_at e updated_at com default automático (timezone.utc)
#   - Método touch() para atualizar updated_at
#   - Método to_dict_with_timestamps() para debugging
#
# ❌ Não implementado (Pós-MVP):
#   - Suporte a timezone customizável (ex: usar fuso do usuário)
#   - Validação de updated_at >= created_at
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO