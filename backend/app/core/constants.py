"""
Constantes Globais do Sistema
Arquivo: backend/app/core/constants.py

Funcionalidade: Centraliza todas as constantes usadas em múltiplos arquivos.
Facilita manutenção e evita duplicação.

🔧 USO:
    from app.core.constants import MAX_HISTORY_ENTRIES, MAX_INSTALLMENTS, PAYMENT_METHOD_CREDIT_CARD, CATEGORIA_BILLS
    
    if installments > MAX_INSTALLMENTS:
        raise ValidationException(...)

📋 ESTRUTURA:
    - Configurações de histórico (MAX_HISTORY_ENTRIES, HISTORY_TTL_DAYS)
    - Configurações de parcelas (MAX_INSTALLMENTS)
    - Rate limits (RATE_LIMIT_CREATE, RATE_LIMIT_UPDATE, etc.)
    - Paginação (DEFAULT_PAGE, DEFAULT_LIMIT, MAX_LIMIT, PAGINATION_CACHE_TTL)
    - Juros (MIN_INTEREST_RATE, MAX_INTEREST_RATE)
    - Notificações (INACTIVE_TOKEN_DAYS, EXPO_API_URL, MAX_INSTALLMENTS_DAYS_WARNING)
    - Score (SCORE_CACHE_TTL_SECONDS, SLOW_THRESHOLD, MAX_RETRIES)
    - Balance (BALANCE_CACHE_TTL_SECONDS)
    - CSV Export (CSV_MAX_EXPORT)
    - Delete Token (DELETE_TOKEN_EXPIRY_HOURS)
    - Transações (PAYMENT_METHOD_CREDIT_CARD)
    - Categorias de contas a pagar (CATEGORIA_BILLS)
    - IA (GROQ_DEFAULT_MODEL, IA_TIMEOUT_SECONDS, IA_MAX_TOKENS, IA_TEMPERATURE, IA_CACHE_MAX_SIZE)
    - Anonimizer (SCORE_RANGES, EXPENSE_RANGES)
    - 🔧 NOVO: Pagination (PAGINATION_CACHE_TTL, PAGINATION_CACHE_TTL_DEFAULT)
"""

import os
import logging
from typing import Literal

# ========== CONFIGURAÇÃO DE LOG ==========
logger = logging.getLogger(__name__)


# ================================================================
# HISTÓRICO / AUDITORIA
# ================================================================

MAX_HISTORY_ENTRIES = int(os.getenv("MAX_HISTORY_ENTRIES", "1000"))
"""Número máximo de entradas no histórico por documento."""

HISTORY_TTL_DAYS = int(os.getenv("HISTORY_TTL_DAYS", "365"))
"""Tempo de vida das entradas do histórico em dias."""

# Validação dos valores
if MAX_HISTORY_ENTRIES < 10 or MAX_HISTORY_ENTRIES > 10000:
    logger.warning(f"⚠️ MAX_HISTORY_ENTRIES inválido: {MAX_HISTORY_ENTRIES}, usando 1000")
    MAX_HISTORY_ENTRIES = 1000

if HISTORY_TTL_DAYS < 7 or HISTORY_TTL_DAYS > 730:
    logger.warning(f"⚠️ HISTORY_TTL_DAYS inválido: {HISTORY_TTL_DAYS}, usando 365")
    HISTORY_TTL_DAYS = 365


# ================================================================
# INSTALLMENTS (PARCELAS)
# ================================================================

MAX_INSTALLMENTS = 360
"""Número máximo de parcelas permitido (30 anos)."""


# ================================================================
# PAGINATION
# ================================================================

DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# 🔧 NOVO: Cache de Paginação por Coleção
# TTL diferente para cada coleção baseado na frequência de mudança
PAGINATION_CACHE_TTL = {
    "transactions": 60,      # 1 minuto - mudam com frequência
    "bills": 120,            # 2 minutos - mudam moderadamente
    "goals": 300,            # 5 minutos - mudam raramente
    "credit_cards": 300,     # 5 minutos - mudam raramente
    "credit_card_purchases": 120,  # 2 minutos - mudam moderadamente
    "investments": 120,      # 2 minutos - mudam moderadamente
    "achievements": 600,     # 10 minutos - mudam muito raramente
    "score_history": 300,    # 5 minutos
    "notifications": 60,     # 1 minuto - mudam com frequência
    "debts": 300,            # 5 minutos - mudam raramente
}

# TTL padrão se a coleção não estiver na lista
PAGINATION_CACHE_TTL_DEFAULT = 60  # 1 minuto


# ================================================================
# RATE LIMITING
# ================================================================

RATE_LIMIT_CREATE = "30/minute"
RATE_LIMIT_UPDATE = "20/minute"
RATE_LIMIT_DELETE = "10/minute"
RATE_LIMIT_PAY = "30/minute"
RATE_LIMIT_UNPAY = "10/minute"
RATE_LIMIT_GET = "30/minute"


# ================================================================
# INTEREST (JUROS)
# ================================================================

MIN_INTEREST_RATE = 0.0
MAX_INTEREST_RATE = 100.0


# ================================================================
# NOTIFICATIONS
# ================================================================

INACTIVE_TOKEN_DAYS = 30
"""Dias de inatividade para remover tokens de push."""

EXPO_API_URL = "https://exp.host/--/api/v2/push/send"
"""URL da API do Expo para envio de notificações push."""

MAX_INSTALLMENTS_DAYS_WARNING = 3
"""Dias antes do vencimento para alertar sobre parcelas."""


# ================================================================
# SCORE
# ================================================================

SCORE_CACHE_TTL_SECONDS = 3600  # 1 hora
SLOW_THRESHOLD = 2.0  # Segundos para considerar cálculo lento
MAX_RETRIES = 3  # Número máximo de tentativas no worker


# ================================================================
# BALANCE (SALDO)
# ================================================================

BALANCE_CACHE_TTL_SECONDS = 300  # 5 minutos


# ================================================================
# CACHE (IA)
# ================================================================

CACHE_TTL_SECONDS = 3600  # 1 hora
IA_CACHE_MAX_SIZE = 1000  # Número máximo de entradas no cache


# ================================================================
# IA (Groq)
# ================================================================

GROQ_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
"""Modelo padrão da Groq. Pode ser sobrescrito via .env."""

IA_TIMEOUT_SECONDS = int(os.getenv("IA_TIMEOUT_SECONDS", "30"))
"""Timeout para chamadas à API da Groq em segundos."""

IA_MAX_TOKENS = int(os.getenv("IA_MAX_TOKENS", "300"))
"""Número máximo de tokens na resposta da IA."""

IA_TEMPERATURE = float(os.getenv("IA_TEMPERATURE", "0.3"))
"""Temperatura para respostas da IA (0.0 = mais direta, 1.0 = mais criativa)."""


# ================================================================
# ANONIMIZER - FAIXAS
# ================================================================

SCORE_RANGES = [
    {"min": 0, "max": 20, "label": "0-20", "label_key": "SCORE_RANGE_0_20"},
    {"min": 20, "max": 40, "label": "20-40", "label_key": "SCORE_RANGE_20_40"},
    {"min": 40, "max": 60, "label": "40-60", "label_key": "SCORE_RANGE_40_60"},
    {"min": 60, "max": 80, "label": "60-80", "label_key": "SCORE_RANGE_60_80"},
    {"min": 80, "max": 101, "label": "80-100", "label_key": "SCORE_RANGE_80_100"},
]
"""Faixas para conversão de score numérico em categoria."""

EXPENSE_RANGES = [
    {"min": 0, "max": 100, "label": "0-100", "label_key": "EXPENSE_RANGE_0_100"},
    {"min": 100, "max": 500, "label": "100-500", "label_key": "EXPENSE_RANGE_100_500"},
    {"min": 500, "max": 1000, "label": "500-1000", "label_key": "EXPENSE_RANGE_500_1000"},
    {"min": 1000, "max": 5000, "label": "1000-5000", "label_key": "EXPENSE_RANGE_1000_5000"},
    {"min": 5000, "max": float('inf'), "label": "5000+", "label_key": "EXPENSE_RANGE_5000_PLUS"},
]
"""Faixas para conversão de gasto em categoria."""


# ================================================================
# CSV EXPORT
# ================================================================

CSV_MAX_EXPORT = 10000  # Máximo de registros para exportação


# ================================================================
# DELETE TOKEN
# ================================================================

DELETE_TOKEN_EXPIRY_HOURS = 24


# ================================================================
# SYNC BATCH
# ================================================================

MAX_SYNC_BATCH = 100
"""Número máximo de conquistas permitidas por requisição de sync."""


# ================================================================
# TRANSAÇÕES E PAGAMENTOS
# ================================================================

PAYMENT_METHOD_CREDIT_CARD = "cartao_credito"
"""Valor padronizado para método de pagamento com cartão de crédito."""


# ================================================================
# CATEGORIAS DE CONTAS A PAGAR (BILLS)
# ================================================================

CATEGORIA_BILLS = Literal[
    "aluguel", "condominio", "agua", "luz", "internet", "telefone",
    "supermercado", "educacao", "saude", "transporte", "lazer", "outros"
]
"""Categorias válidas para contas a pagar (Literal)."""

# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ Configurações centralizadas
# ✅ Validação de valores de ambiente
# ✅ Fallback para valores padrão
# ✅ Documentação de cada constante
# ✅ Fácil manutenção (alterar em um lugar)
# ✅ INACTIVE_TOKEN_DAYS adicionado
# ✅ EXPO_API_URL adicionado
# ✅ MAX_INSTALLMENTS_DAYS_WARNING adicionado
# ✅ PAYMENT_METHOD_CREDIT_CARD adicionado (corrige ImportError)
# ✅ CATEGORIA_BILLS adicionado (corrige ImportError no bill.py)
# ✅ BALANCE_CACHE_TTL_SECONDS já existente
# ✅ CACHE_TTL_SECONDS já existente
# ✅ GROQ_DEFAULT_MODEL adicionado (configurável via .env)
# ✅ IA_TIMEOUT_SECONDS adicionado (configurável via .env)
# ✅ IA_MAX_TOKENS adicionado (configurável via .env)
# ✅ IA_TEMPERATURE adicionado (configurável via .env)
# ✅ IA_CACHE_MAX_SIZE adicionado
# ✅ SCORE_RANGES adicionado (faixas de score para anonimização)
# ✅ EXPENSE_RANGES adicionado (faixas de gasto para anonimização)
# ✅ 🔧 NOVO: PAGINATION_CACHE_TTL por coleção
# ✅ 🔧 NOVO: PAGINATION_CACHE_TTL_DEFAULT
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado SCORE_RANGES, EXPENSE_RANGES (05/07/2026)
#   - v3: Adicionado PAGINATION_CACHE_TTL, PAGINATION_CACHE_TTL_DEFAULT (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO