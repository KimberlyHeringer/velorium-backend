"""
Categorias Centralizadas do Sistema
Arquivo: backend/app/constants/categories.py

Funcionalidade: Centraliza todas as categorias usadas no sistema para
reutilização em diferentes rotas e módulos.

🔧 USO:
    from app.constants.categories import CATEGORIAS_VALIDAS
    
    if category not in CATEGORIAS_VALIDAS:
        raise ValidationException(...)

📋 ESTRUTURA:
    CATEGORIAS_VALIDAS = ["categoria1", "categoria2", ...]
"""

# ========== CATEGORIAS DE TRANSAÇÕES ==========
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

# ========== CATEGORIAS DE METAS ==========
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

# ========== CATEGORIAS DE INVESTIMENTOS ==========
CATEGORIAS_INVESTIMENTOS = [
    "renda_fixa",
    "acoes",
    "fiis",
    "cripto",
    "outros"
]

# ========== CATEGORIAS DE CARTÃO DE CRÉDITO ==========
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

# ========== ALIAS PARA COMPATIBILIDADE ==========
# Mantém o nome antigo para não quebrar código existente
CATEGORIAS_VALIDAS = CATEGORIAS_TRANSACOES
VALID_CATEGORIES = CATEGORIAS_TRANSACOES  # Para compatibilidade com transactions.py


# ========== FUNÇÕES AUXILIARES ==========

def get_categories_by_type(category_type: str) -> list:
    """
    Retorna a lista de categorias por tipo.
    
    Args:
        category_type: "transacoes", "metas", "investimentos", "compras"
    
    Returns:
        list: Lista de categorias válidas
    
    Exemplo:
        >>> get_categories_by_type("transacoes")
        ["alimentacao", "transporte", ...]
    """
    mapping = {
        "transacoes": CATEGORIAS_TRANSACOES,
        "metas": CATEGORIAS_METAS,
        "investimentos": CATEGORIAS_INVESTIMENTOS,
        "compras": CATEGORIAS_COMPRAS
    }
    return mapping.get(category_type, [])


def is_valid_category(category: str, category_type: str = "transacoes") -> bool:
    """
    Verifica se uma categoria é válida para um determinado tipo.
    
    Args:
        category: Categoria a ser verificada
        category_type: "transacoes", "metas", "investimentos", "compras"
    
    Returns:
        bool: True se a categoria for válida
    
    Exemplo:
        >>> is_valid_category("alimentacao", "transacoes")
        True
        
        >>> is_valid_category("invalida", "transacoes")
        False
    """
    valid_categories = get_categories_by_type(category_type)
    return category in valid_categories


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Centraliza todas as categorias do sistema
# ✅ Reutilizável em todas as rotas
# ✅ Fácil manutenção (alterar em um lugar)
# ✅ Compatibilidade com código existente (aliases)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO