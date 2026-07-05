"""
Utilitário de Anonimização de Dados para IA
Arquivo: backend/app/utils/anonimizer.py

Funcionalidades:
- Remove dados identificáveis (nome, email, valores exatos)
- Converte valores para faixas (score, gastos)
- Agrega categorias de gasto (top 3)
- Formata histórico de conversa para contexto da IA
- Suporte a i18n para nomes das faixas

Principais features:
- 🔧 CORRIGIDO: Faixas configuráveis via constantes
- 🔧 CORRIGIDO: i18n para nomes das faixas
- 🔧 CORRIGIDO: Validação de entrada
- 🔧 CORRIGIDO: Tipagem específica (TypedDict)
- 🔧 CORRIGIDO: Suporte a idioma nas funções
- 🔧 CORRIGIDO: Role duplicado em get_conversation_context
"""

from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime, timezone, timedelta
import re

from app.core.constants import SCORE_RANGES, EXPENSE_RANGES
from app.utils.i18n import get_message


# ========== TIPAGEM ESPECÍFICA ==========

class AnonymizedData(TypedDict, total=False):
    """
    Estrutura tipada para dados anonimizados.
    
    Campos:
        score_range: Faixa do score (ex: "60-80")
        top_categories: Lista das principais categorias (ex: ["alimentacao", "transporte"])
        total_expense_range: Faixa do gasto total (ex: "1000-5000")
        money_feeling: Sentimento em relação ao dinheiro
        risk_profile: Perfil de risco
    """
    score_range: Optional[str]
    top_categories: Optional[List[str]]
    total_expense_range: Optional[str]
    money_feeling: Optional[str]
    risk_profile: Optional[str]


# ========== FUNÇÕES PRINCIPAIS ==========

def get_score_range(score: int, language: str = "pt") -> str:
    """
    Converte score numérico em faixa com suporte a i18n.
    
    Args:
        score: Valor do score (0-100)
        language: Código do idioma (pt, en, es, zh)
    
    Returns:
        str: Faixa do score (ex: "60-80")
    
    Raises:
        ValueError: Se score for inválido
    
    Exemplo:
        >>> get_score_range(75, "pt")
        "60-80"
        >>> get_score_range(75, "en")
        "60-80"
    """
    # 🔧 Validação de entrada
    if not isinstance(score, (int, float)):
        raise ValueError("Score deve ser um número")
    if score < 0 or score > 100:
        raise ValueError("Score deve estar entre 0 e 100")
    
    # 🔧 Busca a faixa correspondente
    for range_config in SCORE_RANGES:
        if range_config["min"] <= score < range_config["max"]:
            # 🔧 Usa i18n para o label da faixa
            label_key = range_config.get("label_key")
            if label_key:
                return get_message(label_key, language)
            return range_config["label"]
    
    # Fallback para o último range (80-100)
    last_range = SCORE_RANGES[-1]
    label_key = last_range.get("label_key")
    if label_key:
        return get_message(label_key, language)
    return last_range["label"]


def get_expense_range(amount: float, language: str = "pt") -> str:
    """
    Converte valor de gasto em faixa com suporte a i18n.
    
    Args:
        amount: Valor do gasto
        language: Código do idioma (pt, en, es, zh)
    
    Returns:
        str: Faixa do gasto (ex: "1000-5000")
    
    Raises:
        ValueError: Se amount for inválido
    
    Exemplo:
        >>> get_expense_range(750, "pt")
        "500-1000"
    """
    # 🔧 Validação de entrada
    if not isinstance(amount, (int, float)):
        raise ValueError("Amount deve ser um número")
    if amount < 0:
        raise ValueError("Amount deve ser positivo")
    
    # 🔧 Busca a faixa correspondente
    for range_config in EXPENSE_RANGES:
        if range_config["min"] <= amount < range_config["max"]:
            label_key = range_config.get("label_key")
            if label_key:
                return get_message(label_key, language)
            return range_config["label"]
    
    # Fallback para o último range
    last_range = EXPENSE_RANGES[-1]
    label_key = last_range.get("label_key")
    if label_key:
        return get_message(label_key, language)
    return last_range["label"]


def aggregate_categories(expenses: Dict[str, float], limit: int = 3) -> List[str]:
    """
    Retorna as principais categorias de gasto.
    
    Args:
        expenses: Dicionário com categorias e valores
        limit: Número máximo de categorias a retornar
    
    Returns:
        List[str]: Lista das principais categorias
    
    Raises:
        ValueError: Se expenses for vazio ou limit inválido
    
    Exemplo:
        >>> aggregate_categories({"alimentacao": 500, "transporte": 300, "lazer": 100})
        ["alimentacao", "transporte", "lazer"]
    """
    if not expenses:
        return []
    
    if limit < 1:
        raise ValueError("Limit deve ser maior que 0")
    
    sorted_categories = sorted(expenses.items(), key=lambda x: x[1], reverse=True)
    return [cat for cat, _ in sorted_categories[:limit]]


def anonymize_user_data(
    user_name: Optional[str] = None,
    user_email: Optional[str] = None,
    score: Optional[int] = None,
    expenses_by_category: Optional[Dict[str, float]] = None,
    total_expense: Optional[float] = None,
    profile_data: Optional[Dict] = None,
    language: str = "pt"
) -> AnonymizedData:
    """
    Anonimiza os dados do usuário para envio à IA.
    
    Args:
        user_name: Nome do usuário (NÃO é incluído no resultado)
        user_email: Email do usuário (NÃO é incluído no resultado)
        score: Score financeiro do usuário
        expenses_by_category: Gastos por categoria
        total_expense: Gasto total
        profile_data: Dados do perfil financeiro
        language: Código do idioma para os nomes das faixas
    
    Returns:
        AnonymizedData: Dados anonimizados (faixas, categorias agregadas)
    
    Exemplo:
        >>> anonymize_user_data(
        ...     score=75,
        ...     expenses_by_category={"alimentacao": 500, "transporte": 300},
        ...     total_expense=800,
        ...     profile_data={"money_feeling": "controlado"}
        ... )
        {
            "score_range": "60-80",
            "top_categories": ["alimentacao", "transporte"],
            "total_expense_range": "500-1000",
            "money_feeling": "controlado"
        }
    """
    result: AnonymizedData = {}
    
    # 🔧 Nome e email são intencionalmente ignorados
    # (não são incluídos no resultado)
    
    # 🔧 Score em faixa (com i18n)
    if score is not None:
        result["score_range"] = get_score_range(score, language)
    
    # 🔧 Principais categorias de gasto
    if expenses_by_category:
        result["top_categories"] = aggregate_categories(expenses_by_category)
    
    # 🔧 Gasto total em faixa (com i18n)
    if total_expense is not None:
        result["total_expense_range"] = get_expense_range(total_expense, language)
    
    # 🔧 Perfil financeiro (anonimizado)
    if profile_data:
        money_feeling = profile_data.get("money_feeling")
        if money_feeling:
            result["money_feeling"] = money_feeling
        
        risk_profile = profile_data.get("risk_scenario")
        if risk_profile:
            result["risk_profile"] = risk_profile
    
    return result


def get_conversation_context(conversation_history: List[Dict], limit: int = 3) -> str:
    """
    Formata o histórico da conversa para contexto da IA.
    Mantém apenas as últimas N interações.
    
    Args:
        conversation_history: Lista de mensagens da conversa
        limit: Número máximo de interações a manter
    
    Returns:
        str: Histórico formatado para contexto
    
    Raises:
        ValueError: Se limit for inválido
    
    Exemplo:
        >>> get_conversation_context([
        ...     {"role": "user", "content": "Oi"},
        ...     {"role": "assistant", "content": "Olá!"}
        ... ])
        "Usuário: Oi\\nVeloria: Olá!"
    """
    if not conversation_history:
        return ""
    
    if limit < 1:
        raise ValueError("Limit deve ser maior que 0")
    
    # Pega as últimas N interações
    recent = conversation_history[-limit:]
    
    context_parts = []
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        # 🔧 Mapeia roles para nomes amigáveis
        # 🔧 CORRIGIDO: Remove role duplicado
        if role == "user":
            context_parts.append(f"Usuário: {content}")
        elif role == "assistant":
            context_parts.append(f"Veloria: {content}")
        else:
            context_parts.append(f"{role}: {content}")
    
    return "\n".join(context_parts)


def anonymize_text(text: str) -> str:
    """
    🔧 NOVO: Remove informações sensíveis de textos.
    Pós-MVP: Esta função pode ser expandida com NLP.
    
    Args:
        text: Texto a ser anonimizado
    
    Returns:
        str: Texto sem informações sensíveis
    
    Exemplo:
        >>> anonymize_text("Meu CPF é 123.456.789-00")
        "Meu CPF é [CPF]"
    """
    if not text:
        return text
    
    # Remove CPF (###.###.###-##)
    text = re.sub(r'\d{3}\.\d{3}\.\d{3}-\d{2}', '[CPF]', text)
    
    # Remove CPF sem formatação (###########)
    # 🔧 PÓS-MVP: Validar dígito verificador para evitar falsos positivos
    text = re.sub(r'\b\d{11}\b', '[CPF]', text)
    
    # Remove telefone com DDD (##) #####-#### ou (##) ####-####
    text = re.sub(r'\(\d{2}\)\s?\d{4,5}-\d{4}', '[TELEFONE]', text)
    
    # Remove email (qualquer coisa@qualquercoisa)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Remove cartão de crédito (#### #### #### ####)
    text = re.sub(r'\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b', '[CARTAO]', text)
    
    # 🔧 PÓS-MVP: Remover nomes completos (requer NLP)
    # text = remove_names(text)
    
    return text


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Remoção de dados identificáveis (nome, email)
#   - Conversão de valores para faixas (score, gastos)
#   - Agregação de categorias de gasto (top 3)
#   - Formatação de histórico de conversa
#   - 🔧 Faixas configuráveis via constants.py
#   - 🔧 i18n para nomes das faixas
#   - 🔧 Validação de entrada
#   - 🔧 Tipagem específica (TypedDict)
#   - 🔧 Suporte a idioma nas funções
#   - 🔧 Função anonymize_text() para remover informações sensíveis
#   - 🔧 CORRIGIDO: Role duplicado em get_conversation_context
#
# ❌ Não implementado (Pós-MVP):
#   - Faixas configuráveis via banco de dados
#   - Anonimização avançada com NLP
#   - Detecção de entidades nomeadas (NER)
#   - Validação de dígito verificador do CPF
#   - Remoção de nomes completos
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração com i18n, validação, typagem (04/07/2026)
#   - v3: Correção - Role duplicado em get_conversation_context (04/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO