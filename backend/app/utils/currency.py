"""
Utilitários de Conversão de Moeda para Centavos
Arquivo: backend/app/utils/currency.py

🔧 REGRA 2.11: Conversão de moeda para centavos
- to_cents: float → int (ex: 10.99 → 1099)
- from_cents: int → float (ex: 1099 → 10.99)

⚠️ IMPORTANTE: Esta implementação é segura e não quebra o banco existente.
As funções serão usadas APENAS para novos registros e respostas da API.
"""

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def to_cents(value: float) -> int:
    """
    Converte um valor float (reais) para inteiro (centavos).
    
    Args:
        value: Valor em reais (ex: 10.99)
    
    Returns:
        int: Valor em centavos (ex: 1099)
    
    Exemplo:
        to_cents(10.99) → 1099
        to_cents(0.50) → 50
        to_cents(100.00) → 10000
    """
    if value is None:
        return 0
    
    cents = int(round(value * 100))
    logger.debug(f"Conversão to_cents: R$ {value} → {cents} centavos")
    return cents


def from_cents(value: int) -> float:
    """
    Converte um valor inteiro (centavos) para float (reais).
    
    Args:
        value: Valor em centavos (ex: 1099)
    
    Returns:
        float: Valor em reais (ex: 10.99)
    
    Exemplo:
        from_cents(1099) → 10.99
        from_cents(50) → 0.50
        from_cents(10000) → 100.00
    """
    if value is None:
        return 0.0
    
    reais = round(value / 100, 2)
    logger.debug(f"Conversão from_cents: {value} centavos → R$ {reais}")
    return reais