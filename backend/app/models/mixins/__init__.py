"""
Arquivo: backend/app/models/mixins/__init__.py
Objetivo: Centralizar a exportação de todos os mixins

Funcionalidades:
- Importa todos os mixins da pasta mixins/
- Exporta todos para que possam ser importados de uma só vez

Principais features:
- Importação centralizada
- Exportação via __all__ para facilitar o autocomplete
"""

from .timestamp import TimestampMixin
from .objectid import ObjectIdMixin
from .payment import PaymentMixin
from .amount import AmountMixin
from .date import DateMixin
from .audit import AuditMixin

__all__ = [
    'TimestampMixin',
    'ObjectIdMixin',
    'PaymentMixin',
    'AmountMixin',
    'DateMixin',
    'AuditMixin',
]


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Exportação de todos os mixins
#   - Import centralizado (um lugar para importar tudo)
#
# ❌ Não implementado (Pós-MVP):
#   - Nenhum (arquivo simples de exportação)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO