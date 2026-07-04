"""
Arquivo: backend/app/models/mixins/audit.py
Objetivo: Fornecer campos de auditoria (quem criou, quem atualizou, exclusão lógica)

Funcionalidades:
- Define o mixin AuditMixin com campos de auditoria
- Fornece campos: created_by, updated_by, deleted_at, is_deleted
- Fornece método mark_deleted() para exclusão lógica
- Fornece método restore() para restaurar registros

Principais features:
- Campos created_by e updated_by (auditoria)
- Suporte a exclusão lógica (is_deleted, deleted_at)
- Método mark_deleted() para exclusão lógica
- Método restore() para restaurar registros
"""

from pydantic import Field
from typing import Optional
from datetime import datetime, timezone


class AuditMixin:
    """
    Mixin que adiciona campos de auditoria a um modelo.
    
    🔧 CAMPOS ADICIONADOS:
      - created_by: Quem criou o registro
      - updated_by: Quem atualizou pela última vez
      - deleted_at: Data de exclusão lógica
      - is_deleted: Flag de exclusão lógica
    
    🔧 MÉTODOS ADICIONADOS:
      - mark_deleted(): Marca como deletado logicamente
      - restore(): Restaura um registro deletado
    """
    
    created_by: Optional[str] = Field(
        default=None,
        description="ID do usuário que criou o registro"
    )
    
    updated_by: Optional[str] = Field(
        default=None,
        description="ID do usuário que atualizou pela última vez"
    )
    
    deleted_at: Optional[datetime] = Field(
        default=None,
        description="Data de exclusão lógica (preenchido quando is_deleted=True)"
    )
    
    is_deleted: bool = Field(
        default=False,
        description="Indica se o registro foi deletado logicamente"
    )
    
    def mark_deleted(self, user_id: str) -> 'AuditMixin':
        """
        Marca o registro como deletado logicamente.
        
        🔧 COMO USAR:
          obj.mark_deleted("admin")
          # obj.is_deleted = True
          # obj.deleted_at = data atual
          # obj.updated_by = "admin"
        
        🔧 RETORNO:
          self (o próprio objeto) - permite encadeamento:
          obj.mark_deleted("admin").save()
        """
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.updated_by = user_id
        return self
    
    def restore(self) -> 'AuditMixin':
        """
        Restaura um registro que foi deletado logicamente.
        
        🔧 COMO USAR:
          obj.restore()
          # obj.is_deleted = False
          # obj.deleted_at = None
        """
        self.is_deleted = False
        self.deleted_at = None
        return self


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Campos created_by e updated_by (auditoria)
#   - Campos deleted_at e is_deleted (exclusão lógica)
#   - Método mark_deleted() e restore()
#
# ❌ Não implementado (Pós-MVP):
#   - Histórico de alterações (tracking de todas as mudanças)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO