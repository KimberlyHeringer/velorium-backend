"""
Utilitários de Conversão de Moeda para Centavos
Arquivo: backend/app/utils/currency.py

Funcionalidades:
- to_cents(): Converte valor em reais (float) para centavos (int)
- from_cents(): Converte valor em centavos (int) para reais (float)
- format_currency(): Formata valor para exibição com símbolo da moeda

Principais features:
- 🔧 CORRIGIDO: Validação de valor negativo
- 🔧 CORRIGIDO: i18n nas mensagens de log
- 🔧 CORRIGIDO: Suporte a múltiplas moedas (BRL, USD, EUR, CNY)
- 🔧 CORRIGIDO: Função format_currency() para exibição no frontend
- 🔧 CORRIGIDO: Documentação completa

⚠️ IMPORTANTE: Esta implementação é segura e não quebra o banco existente.
As funções serão usadas APENAS para novos registros e respostas da API.
"""

from typing import Optional
from app.utils.logger import setup_logger
from app.utils.i18n import get_message

logger = setup_logger(__name__)


# ========== CONSTANTES ==========

# Símbolos das moedas suportadas
CURRENCY_SYMBOLS = {
    "BRL": "R$",
    "USD": "US$",
    "EUR": "€",
    "CNY": "¥",
}

# Locales para formatação (opcional, usado como fallback)
CURRENCY_LOCALES = {
    "BRL": "pt-BR",
    "USD": "en-US",
    "EUR": "de-DE",
    "CNY": "zh-CN",
}


# ========== FUNÇÕES DE CONVERSÃO ==========

def to_cents(value: Optional[float], currency: str = "BRL") -> int:
    """
    Converte um valor float (reais) para inteiro (centavos).
    
    🔧 CORRIGIDO: Validação de valor negativo.
    🔧 CORRIGIDO: Suporte a múltiplas moedas.
    🔧 CORRIGIDO: i18n nos logs.
    
    Args:
        value: Valor em reais (ex: 10.99)
        currency: Código da moeda (BRL, USD, EUR, CNY)
    
    Returns:
        int: Valor em centavos (ex: 1099)
    
    Raises:
        ValueError: Se value for negativo
    
    Exemplo:
        to_cents(10.99, "BRL") → 1099
        to_cents(10.99, "USD") → 1099
        to_cents(10.99, "EUR") → 1099
        to_cents(10.99, "CNY") → 1099
    """
    language = "pt"  # 🔧 FUTURO: Detectar idioma do usuário
    
    if value is None:
        return 0
    
    # 🔧 CORRIGIDO: Validação de valor negativo
    if value < 0:
        raise ValueError(get_message("CURRENCY_NEGATIVE_VALUE", language))
    
    # 🔧 CORRIGIDO: Log com i18n
    cents = int(round(value * 100))
    logger.debug(f"{get_message('CURRENCY_TO_CENTS', language)}: {currency} {value} → {cents}")
    return cents


def from_cents(value: Optional[int], currency: str = "BRL") -> float:
    """
    Converte um valor inteiro (centavos) para float (reais).
    
    🔧 CORRIGIDO: Validação de valor negativo.
    🔧 CORRIGIDO: Suporte a múltiplas moedas.
    🔧 CORRIGIDO: i18n nos logs.
    
    Args:
        value: Valor em centavos (ex: 1099)
        currency: Código da moeda (BRL, USD, EUR, CNY)
    
    Returns:
        float: Valor em reais (ex: 10.99)
    
    Raises:
        ValueError: Se value for negativo
    
    Exemplo:
        from_cents(1099, "BRL") → 10.99
        from_cents(1099, "USD") → 10.99
        from_cents(1099, "EUR") → 10.99
        from_cents(1099, "CNY") → 10.99
    """
    language = "pt"  # 🔧 FUTURO: Detectar idioma do usuário
    
    if value is None:
        return 0.0
    
    # 🔧 CORRIGIDO: Validação de valor negativo
    if value < 0:
        raise ValueError(get_message("CURRENCY_NEGATIVE_VALUE", language))
    
    reais = round(value / 100, 2)
    logger.debug(f"{get_message('CURRENCY_FROM_CENTS', language)}: {value} → {currency} {reais}")
    return reais


# ========== FORMATAÇÃO PARA EXIBIÇÃO ==========

def format_currency(value: int, currency: str = "BRL", include_symbol: bool = True) -> str:
    """
    🔧 NOVO: Formata um valor em centavos para exibição no frontend.
    
    Args:
        value: Valor em centavos (ex: 1099)
        currency: Código da moeda (BRL, USD, EUR, CNY)
        include_symbol: Se deve incluir o símbolo da moeda
    
    Returns:
        str: Valor formatado (ex: "R$ 10,99")
    
    Exemplo:
        format_currency(1099, "BRL") → "R$ 10,99"
        format_currency(1099, "USD") → "US$ 10.99"
        format_currency(1099, "EUR") → "€ 10.99"
        format_currency(1099, "CNY") → "¥ 10.99"
        format_currency(1099, "BRL", False) → "10,99"
    """
    if value is None:
        return "0,00" if currency == "BRL" else "0.00"
    
    if value < 0:
        raise ValueError(get_message("CURRENCY_NEGATIVE_VALUE", "pt"))
    
    reais = from_cents(value, currency)
    
    # 🔧 Formata com base na moeda
    if currency == "BRL":
        formatted = f"{reais:.2f}".replace(".", ",")
    else:
        formatted = f"{reais:.2f}"
    
    if include_symbol:
        symbol = CURRENCY_SYMBOLS.get(currency, "R$")
        # Espaço entre símbolo e valor (para BRL e USD, sem espaço para EUR e CNY)
        if currency in ["EUR", "CNY"]:
            return f"{symbol}{formatted}"
        else:
            return f"{symbol} {formatted}"
    
    return formatted


def format_currency_from_cents(value: int, currency: str = "BRL") -> str:
    """
    🔧 NOVO: Alias para format_currency com include_symbol=True.
    """
    return format_currency(value, currency, include_symbol=True)


def get_currency_symbol(currency: str) -> str:
    """
    🔧 NOVO: Retorna o símbolo da moeda.
    
    Args:
        currency: Código da moeda (BRL, USD, EUR, CNY)
    
    Returns:
        str: Símbolo da moeda (ex: "R$")
    
    Exemplo:
        get_currency_symbol("BRL") → "R$"
        get_currency_symbol("USD") → "US$"
    """
    return CURRENCY_SYMBOLS.get(currency, "R$")


def get_currency_locale(currency: str) -> str:
    """
    🔧 NOVO: Retorna o locale para formatação.
    
    Args:
        currency: Código da moeda (BRL, USD, EUR, CNY)
    
    Returns:
        str: Locale (ex: "pt-BR")
    
    Exemplo:
        get_currency_locale("BRL") → "pt-BR"
        get_currency_locale("USD") → "en-US"
    """
    return CURRENCY_LOCALES.get(currency, "pt-BR")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - to_cents() e from_cents() com validação
#   - 🔧 Validação de valor negativo
#   - 🔧 i18n nas mensagens de log
#   - 🔧 Suporte a múltiplas moedas (BRL, USD, EUR, CNY)
#   - 🔧 Função format_currency() para exibição
#   - 🔧 Função get_currency_symbol()
#   - 🔧 Função get_currency_locale()
#   - 🔧 Documentação completa
#
# ❌ Não implementado (Pós-MVP):
#   - Conversão entre moedas (taxa de câmbio)
#   - Cache de taxas de câmbio
#   - Atualização automática de taxas
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração com i18n, validação, múltiplas moedas, formatação (05/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO