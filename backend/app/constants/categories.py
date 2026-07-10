"""
Categorias Centralizadas do Sistema
Arquivo: backend/app/constants/categories.py

Funcionalidade: Centraliza todas as categorias usadas no sistema para
reutilização em diferentes rotas e módulos.

🔧 USO:
    from app.constants.categories import (
        CATEGORIAS_TRANSACOES,
        CATEGORIAS_METAS,
        CATEGORIAS_INVESTIMENTOS,
        CATEGORIAS_COMPRAS,
        CATEGORIAS_BILLS,           # 🆕 NOVO
        CATEGORIAS_VALIDAS,
        VALID_CATEGORIES,
        get_categories_by_type,
        is_valid_category
    )
    
    # Validar categoria de transação
    if category not in CATEGORIAS_TRANSACOES:
        raise ValidationException(...)
    
    # Validar categoria de investimento
    if category not in CATEGORIAS_INVESTIMENTOS:
        raise ValidationException(...)
    
    # Validar categoria de conta
    if category not in CATEGORIAS_BILLS:
        raise ValidationException(...)
    
    # Usar função auxiliar
    if not is_valid_category(category, "transacoes"):
        raise ValidationException(...)

📋 ESTRUTURA:
    CATEGORIAS_TRANSACOES: Categorias para transações financeiras
    CATEGORIAS_METAS: Categorias para metas
    CATEGORIAS_INVESTIMENTOS: Categorias para investimentos
    CATEGORIAS_COMPRAS: Categorias para compras no cartão
    CATEGORIAS_BILLS: Categorias para contas a pagar (🆕 NOVO)
    CATEGORIAS_VALIDAS: Alias para CATEGORIAS_TRANSACOES (compatibilidade)
    VALID_CATEGORIES: Alias para CATEGORIAS_TRANSACOES (compatibilidade)

🆕 ATUALIZADO: 10/07/2026
✅ Adicionado CATEGORIAS_BILLS
✅ Adicionado CATEGORIAS_BILLS_LABELS
✅ Adicionado suporte a 'bills' em get_categories_by_type
✅ Adicionado suporte a 'bills' em get_categories_with_labels_by_type
"""

# ================================================================
# CATEGORIAS DE TRANSAÇÕES
# ================================================================

CATEGORIAS_TRANSACOES = [
    "alimentacao",
    "transporte",
    "moradia",
    "lazer",
    "saude",
    "educacao",
    "investimentos",
    "vestuario",
    "beleza",
    "outros"
]

# ================================================================
# CATEGORIAS DE METAS
# ================================================================

CATEGORIAS_METAS = [
    "economia",
    "investimento",
    "viagem",
    "educacao",
    "saude",
    "casa",
    "carro",
    "outros"
]

# ================================================================
# CATEGORIAS DE INVESTIMENTOS
# ================================================================

CATEGORIAS_INVESTIMENTOS = [
    "renda_fixa",
    "acoes",
    "fiis",
    "cripto",
    "outros"
]

# ================================================================
# CATEGORIAS DE CARTÃO DE CRÉDITO
# ================================================================

CATEGORIAS_COMPRAS = [
    "alimentacao",
    "transporte",
    "moradia",
    "lazer",
    "saude",
    "educacao",
    "investimentos",
    "vestuario",
    "beleza",
    "eletronicos",
    "casa",
    "outros"
]

# ================================================================
# 🆕 CATEGORIAS DE CONTAS A PAGAR (BILLS)
# ================================================================

CATEGORIAS_BILLS = [
    "moradia",
    "transporte",
    "alimentacao",
    "saude",
    "educacao",
    "lazer",
    "servicos",
    "seguros",
    "impostos",
    "outros"
]

# ================================================================
# ALIAS PARA COMPATIBILIDADE
# ================================================================

# Mantém os nomes antigos para não quebrar código existente
CATEGORIAS_VALIDAS = CATEGORIAS_TRANSACOES
VALID_CATEGORIES = CATEGORIAS_TRANSACOES

# ================================================================
# 🆕 CONSTANTES COM LABEL_KEY PARA I18N
# ================================================================

CATEGORIAS_TRANSACOES_LABELS = [
    {"value": "alimentacao", "label_key": "CATEGORY_ALIMENTACAO"},
    {"value": "transporte", "label_key": "CATEGORY_TRANSPORTE"},
    {"value": "moradia", "label_key": "CATEGORY_MORADIA"},
    {"value": "lazer", "label_key": "CATEGORY_LAZER"},
    {"value": "saude", "label_key": "CATEGORY_SAUDE"},
    {"value": "educacao", "label_key": "CATEGORY_EDUCACAO"},
    {"value": "investimentos", "label_key": "CATEGORY_INVESTIMENTOS"},
    {"value": "vestuario", "label_key": "CATEGORY_VESTUARIO"},
    {"value": "beleza", "label_key": "CATEGORY_BELEZA"},
    {"value": "outros", "label_key": "CATEGORY_OUTROS"},
]

CATEGORIAS_METAS_LABELS = [
    {"value": "economia", "label_key": "CATEGORY_ECONOMIA"},
    {"value": "investimento", "label_key": "CATEGORY_INVESTIMENTO"},
    {"value": "viagem", "label_key": "CATEGORY_VIAGEM"},
    {"value": "educacao", "label_key": "CATEGORY_EDUCACAO"},
    {"value": "saude", "label_key": "CATEGORY_SAUDE"},
    {"value": "casa", "label_key": "CATEGORY_CASA"},
    {"value": "carro", "label_key": "CATEGORY_CARRO"},
    {"value": "outros", "label_key": "CATEGORY_OUTROS"},
]

CATEGORIAS_INVESTIMENTOS_LABELS = [
    {"value": "renda_fixa", "label_key": "CATEGORY_RENDA_FIXA"},
    {"value": "acoes", "label_key": "CATEGORY_ACOES"},
    {"value": "fiis", "label_key": "CATEGORY_FIIS"},
    {"value": "cripto", "label_key": "CATEGORY_CRIPTO"},
    {"value": "outros", "label_key": "CATEGORY_OUTROS"},
]

CATEGORIAS_COMPRAS_LABELS = [
    {"value": "alimentacao", "label_key": "CATEGORY_ALIMENTACAO"},
    {"value": "transporte", "label_key": "CATEGORY_TRANSPORTE"},
    {"value": "moradia", "label_key": "CATEGORY_MORADIA"},
    {"value": "lazer", "label_key": "CATEGORY_LAZER"},
    {"value": "saude", "label_key": "CATEGORY_SAUDE"},
    {"value": "educacao", "label_key": "CATEGORY_EDUCACAO"},
    {"value": "investimentos", "label_key": "CATEGORY_INVESTIMENTOS"},
    {"value": "vestuario", "label_key": "CATEGORY_VESTUARIO"},
    {"value": "beleza", "label_key": "CATEGORY_BELEZA"},
    {"value": "eletronicos", "label_key": "CATEGORY_ELETRONICOS"},
    {"value": "casa", "label_key": "CATEGORY_CASA"},
    {"value": "outros", "label_key": "CATEGORY_OUTROS"},
]

# 🆕 CATEGORIAS_BILLS_LABELS
CATEGORIAS_BILLS_LABELS = [
    {"value": "moradia", "label_key": "CATEGORY_MORADIA"},
    {"value": "transporte", "label_key": "CATEGORY_TRANSPORTE"},
    {"value": "alimentacao", "label_key": "CATEGORY_ALIMENTACAO"},
    {"value": "saude", "label_key": "CATEGORY_SAUDE"},
    {"value": "educacao", "label_key": "CATEGORY_EDUCACAO"},
    {"value": "lazer", "label_key": "CATEGORY_LAZER"},
    {"value": "servicos", "label_key": "CATEGORY_SERVICOS"},
    {"value": "seguros", "label_key": "CATEGORY_SEGUROS"},
    {"value": "impostos", "label_key": "CATEGORY_IMPOSTOS"},
    {"value": "outros", "label_key": "CATEGORY_OUTROS"},
]

# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================

def get_categories_by_type(category_type: str) -> list:
    """
    Retorna a lista de categorias por tipo.
    
    🔧 USO:
        categories = get_categories_by_type("transacoes")
        # ["alimentacao", "transporte", ...]
    
    📋 PADRÃO:
        - Retorna lista vazia se o tipo não for encontrado
    
    🆕 SUPORTE: 'bills' adicionado
    
    Args:
        category_type: "transacoes", "metas", "investimentos", "compras", "bills"
    
    Returns:
        list: Lista de categorias válidas
    
    Exemplo:
        >>> get_categories_by_type("transacoes")
        ["alimentacao", "transporte", ...]
        
        >>> get_categories_by_type("investimentos")
        ["renda_fixa", "acoes", ...]
        
        >>> get_categories_by_type("bills")
        ["moradia", "transporte", ...]
    """
    mapping = {
        "transacoes": CATEGORIAS_TRANSACOES,
        "metas": CATEGORIAS_METAS,
        "investimentos": CATEGORIAS_INVESTIMENTOS,
        "compras": CATEGORIAS_COMPRAS,
        "bills": CATEGORIAS_BILLS,  # 🆕 NOVO
    }
    return mapping.get(category_type, [])


def get_categories_with_labels_by_type(category_type: str) -> list:
    """
    🔧 NOVO: Retorna a lista de categorias com label_key por tipo.
    
    🔧 USO:
        categories = get_categories_with_labels_by_type("transacoes")
        # [{"value": "alimentacao", "label_key": "CATEGORY_ALIMENTACAO"}, ...]
    
    🆕 SUPORTE: 'bills' adicionado
    
    Args:
        category_type: "transacoes", "metas", "investimentos", "compras", "bills"
    
    Returns:
        list: Lista de categorias com label_key
    
    Exemplo:
        >>> get_categories_with_labels_by_type("transacoes")
        [{"value": "alimentacao", "label_key": "CATEGORY_ALIMENTACAO"}, ...]
        
        >>> get_categories_with_labels_by_type("bills")
        [{"value": "moradia", "label_key": "CATEGORY_MORADIA"}, ...]
    """
    mapping = {
        "transacoes": CATEGORIAS_TRANSACOES_LABELS,
        "metas": CATEGORIAS_METAS_LABELS,
        "investimentos": CATEGORIAS_INVESTIMENTOS_LABELS,
        "compras": CATEGORIAS_COMPRAS_LABELS,
        "bills": CATEGORIAS_BILLS_LABELS,  # 🆕 NOVO
    }
    return mapping.get(category_type, [])


def is_valid_category(category: str, category_type: str = "transacoes") -> bool:
    """
    Verifica se uma categoria é válida para um determinado tipo.
    
    🔧 USO:
        if is_valid_category("alimentacao", "transacoes"):
            print("Categoria válida")
    
    🆕 SUPORTE: 'bills' adicionado
    
    Args:
        category: Categoria a ser verificada
        category_type: "transacoes", "metas", "investimentos", "compras", "bills"
    
    Returns:
        bool: True se a categoria for válida
    
    Exemplo:
        >>> is_valid_category("alimentacao", "transacoes")
        True
        
        >>> is_valid_category("invalida", "transacoes")
        False
        
        >>> is_valid_category("acoes", "investimentos")
        True
        
        >>> is_valid_category("moradia", "bills")
        True
    """
    valid_categories = get_categories_by_type(category_type)
    return category in valid_categories


# ================================================================
# NOTAS DE IMPLEMENTAÇÃO
# ================================================================

"""
📌 COMO USAR:

1. Validar categoria de transação:
   from app.constants.categories import CATEGORIAS_TRANSACOES
   
   if category not in CATEGORIAS_TRANSACOES:
       raise ValidationException(...)

2. Validar categoria de conta:
   from app.constants.categories import CATEGORIAS_BILLS
   
   if category not in CATEGORIAS_BILLS:
       raise ValidationException(...)

3. Usar função auxiliar:
   from app.constants.categories import is_valid_category
   
   if not is_valid_category(category, "bills"):
       raise ValidationException(...)

4. Usar com i18n (Frontend):
   from app.constants.categories import get_categories_with_labels_by_type
   
   categories = get_categories_with_labels_by_type("bills")
   # [{"value": "moradia", "label_key": "CATEGORY_MORADIA"}, ...]
"""


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ Centraliza todas as categorias do sistema
# ✅ Reutilizável em todas as rotas
# ✅ Fácil manutenção (alterar em um lugar)
# ✅ Compatibilidade com código existente (aliases)
# ✅ Funções auxiliares para validação
# ✅ CATEGORIAS_TRANSACOES_LABELS com label_key para i18n
# ✅ CATEGORIAS_METAS_LABELS com label_key para i18n
# ✅ CATEGORIAS_INVESTIMENTOS_LABELS com label_key para i18n
# ✅ CATEGORIAS_COMPRAS_LABELS com label_key para i18n
#
# 🆕 ATUALIZADO: 10/07/2026
# ✅ CATEGORIAS_BILLS (10 categorias: moradia, transporte, alimentacao, saude, educacao, lazer, servicos, seguros, impostos, outros)
# ✅ CATEGORIAS_BILLS_LABELS com label_key para i18n
# ✅ Suporte a 'bills' em get_categories_by_type()
# ✅ Suporte a 'bills' em get_categories_with_labels_by_type()
# ✅ Exemplos de uso adicionados
#
# ❌ Não implementado (Pós-MVP):
#   - Categorias personalizadas pelo usuário
#   - Categorias com ícones
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado CATEGORIAS_INVESTIMENTOS (05/07/2026)
#   - v3: Adicionado labels para i18n, get_categories_with_labels_by_type (06/07/2026)
#   - v4: Adicionado CATEGORIAS_BILLS e suporte a 'bills' (10/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO
# 📅 ÚLTIMA ATUALIZAÇÃO: 10/07/2026