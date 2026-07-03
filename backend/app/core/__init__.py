"""
Módulo Core - Configurações e Funcionalidades Centrais
Arquivo: backend/app/core/__init__.py

Funcionalidade: Centraliza configurações globais, constantes e funcionalidades
base que são reutilizadas em toda a aplicação.

📋 ESTRUTURA:
    - constants.py: Constantes globais (histórico, parcelas, rate limits, etc.)
    - (futuro) base_model.py: Mixin base para models
    - (futuro) responses.py: Schemas de resposta padronizados

🔧 USO:
    from app.core.constants import MAX_INSTALLMENTS, RATE_LIMIT_CREATE
"""

from app.core.constants import *

# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Core separado de constants (categorias ficam em constants/)
# ✅ Importa tudo de constants.py para facilitar uso
# ✅ Expõe todas as constantes para importação direta
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO