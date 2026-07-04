"""
Arquivo: backend/app/models/mixins/amount.py
Objetivo: Fornecer validação para valores monetários em centavos

Funcionalidades:
- Define o mixin AmountMixin com validação de valores monetários
- Valida que o valor é um inteiro positivo
- Converte strings para inteiros quando possível

Principais features:
- Campo amount como int (centavos)
- Validação gt=0 (maior que zero)
- Validação automática do Pydantic
"""

from pydantic import Field


class AmountMixin:
    """
    Mixin que adiciona campo amount com validação de valor monetário.
    
    🔧 CAMPOS ADICIONADOS:
      - amount: int (valor em centavos, sempre positivo)
    
    🔧 VALIDAÇÕES:
      1. amount deve ser maior que zero (gt=0)
      2. amount deve ser um inteiro (centavos)
    """
    
    amount: int = Field(
        ...,
        gt=0,
        description="Valor monetário em CENTAVOS (ex: 15050 = R$ 150,50)"
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Campo amount como int (centavos)
#   - Validação gt=0 (maior que zero)
#
# ❌ Não implementado (Pós-MVP):
#   - Formatação de moeda (feito no frontend)
#   - Conversão entre moedas
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO
