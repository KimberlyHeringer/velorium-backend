"""
Utilitário de Anonimização de Dados para IA
Arquivo: backend/app/utils/anonimizer.py

🔧 REGRA 3.4: IA e Dados do Usuário
- Remove dados identificáveis (nome, email, valores exatos)
- Converte valores para faixas
- Agrega categorias de gasto
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta


def get_score_range(score: int) -> str:
    """Converte score numérico em faixa"""
    if score < 20:
        return "0-20"
    elif score < 40:
        return "20-40"
    elif score < 60:
        return "40-60"
    elif score < 80:
        return "60-80"
    else:
        return "80-100"


def get_expense_range(amount: float) -> str:
    """Converte valor de gasto em faixa"""
    if amount < 100:
        return "0-100"
    elif amount < 500:
        return "100-500"
    elif amount < 1000:
        return "500-1000"
    elif amount < 5000:
        return "1000-5000"
    else:
        return "5000+"


def aggregate_categories(expenses: Dict[str, float], limit: int = 3) -> List[str]:
    """Retorna as principais categorias de gasto"""
    sorted_categories = sorted(expenses.items(), key=lambda x: x[1], reverse=True)
    return [cat for cat, _ in sorted_categories[:limit]]


def anonymize_user_data(
    user_name: str = None,
    user_email: str = None,
    score: int = None,
    expenses_by_category: Dict[str, float] = None,
    total_expense: float = None,
    profile_data: Dict = None
) -> Dict[str, Any]:
    """
    Anonimiza os dados do usuário para envio à IA.
    
    Returns:
        Dict com dados anonimizados (faixas, categorias agregadas)
    """
    result = {}
    
    # 🔧 Remove nome e email (não envia)
    # (intencionalmente não inclui name/email no resultado)
    
    # 🔧 Score em faixa
    if score is not None:
        result["score_range"] = get_score_range(score)
    
    # 🔧 Principais categorias de gasto
    if expenses_by_category:
        result["top_categories"] = aggregate_categories(expenses_by_category)
    
    # 🔧 Gasto total em faixa
    if total_expense is not None:
        result["total_expense_range"] = get_expense_range(total_expense)
    
    # 🔧 Perfil financeiro (anonimizado)
    if profile_data:
        money_feeling = profile_data.get("money_feeling")
        if money_feeling:
            result["money_feeling"] = money_feeling
        
        risk_profile = profile_data.get("risk_scenario")
        if risk_profile:
            result["risk_profile"] = risk_profile
    
    return result


def get_conversation_context(conversation_history: List[Dict]) -> str:
    """
    Formata o histórico da conversa para contexto da IA.
    Mantém apenas as últimas 3 interações.
    """
    if not conversation_history:
        return ""
    
    # Pega as últimas 3 interações
    recent = conversation_history[-3:]
    
    context_parts = []
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            context_parts.append(f"Usuário: {content}")
        else:
            context_parts.append(f"Veloria: {content}")
    
    return "\n".join(context_parts)