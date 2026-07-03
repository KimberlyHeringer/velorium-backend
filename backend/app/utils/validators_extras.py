"""
Validações Extras para Rotas
Arquivo: backend/app/utils/validators_extras.py

Funcionalidade: Centraliza validações e funções auxiliares usadas em múltiplas rotas
(parcelas, valores, taxas de juros, metas, investimentos, etc).

🔧 USO:
    from app.utils.validators_extras import (
        validate_installments,
        validate_amount,
        validate_interest_rate,
        validate_quantity,
        validate_price,
        validate_password_strength,
        add_calculated_fields,
        prepare_investment_response,
        prepare_investment_for_db
    )
    
    validate_installments(installments, request)
    validate_amount(amount, request)
    validate_interest_rate(rate, request)
    validate_password_strength(password)
    add_calculated_fields(goal)
    prepare_investment_response(investment)
    prepare_investment_for_db(data)

📋 ESTRUTURA:
    - validate_installments(): Valida número de parcelas (1-360)
    - validate_amount(): Valida que amount > 0
    - validate_interest_rate(): Valida que interest_rate está entre 0-100%
    - validate_quantity(): Valida que quantity > 0
    - validate_price(): Valida que price > 0
    - validate_password_strength(): Valida força da senha (3/4 critérios)
    - add_calculated_fields(): Adiciona campos calculados à meta
    - prepare_investment_response(): Prepara investimento para resposta
    - prepare_investment_for_db(): Prepara investimento para banco de dados
"""

from fastapi import Request
from decimal import Decimal
import re

from app.core.constants import MAX_INSTALLMENTS, MIN_INTEREST_RATE, MAX_INTEREST_RATE
from app.utils.exceptions import ValidationException
from app.utils.currency import to_cents, from_cents


# ================================================================
# VALIDAÇÕES DE INSTALLMENTS (PARCELAS)
# ================================================================

def validate_installments(
    installments: int,
    request: Request,
    message_key: str = "ERROR_INVALID_INSTALLMENTS"
) -> None:
    """
    Valida número de parcelas (1-360).
    
    Args:
        installments: Número de parcelas
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_INSTALLMENTS)
    
    Raises:
        ValidationException: Se installments <= 0 ou > MAX_INSTALLMENTS
    
    Exemplo:
        validate_installments(12, request)  # ✅ Válido
        validate_installments(400, request) # ❌ Inválido (> 360)
    """
    if installments <= 0:
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    if installments > MAX_INSTALLMENTS:
        raise ValidationException(
            message_key="ERROR_MAX_INSTALLMENTS_EXCEEDED",
            request=request
        )


# ================================================================
# VALIDAÇÕES DE VALORES MONETÁRIOS
# ================================================================

def validate_amount(
    amount: int,
    request: Request,
    message_key: str = "ERROR_AMOUNT_INVALID"
) -> None:
    """
    Valida que amount > 0.
    
    Args:
        amount: Valor em centavos
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_AMOUNT_INVALID)
    
    Raises:
        ValidationException: Se amount <= 0
    
    Exemplo:
        validate_amount(10000, request)  # ✅ Válido (R$ 100,00)
        validate_amount(0, request)      # ❌ Inválido
    """
    if amount <= 0:
        raise ValidationException(
            message_key=message_key,
            request=request
        )


# ================================================================
# VALIDAÇÕES DE TAXA DE JUROS
# ================================================================

def validate_interest_rate(
    rate: float,
    request: Request,
    message_key: str = "ERROR_INVALID_INTEREST_RATE"
) -> None:
    """
    Valida que interest_rate esteja entre 0% e 100%.
    
    Args:
        rate: Taxa de juros mensal (%)
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_INTEREST_RATE)
    
    Raises:
        ValidationException: Se rate < 0 ou rate > 100
    
    Exemplo:
        validate_interest_rate(2.5, request)  # ✅ Válido (2.5%)
        validate_interest_rate(150, request)  # ❌ Inválido (> 100%)
    """
    if rate < MIN_INTEREST_RATE or rate > MAX_INTEREST_RATE:
        raise ValidationException(
            message_key=message_key,
            request=request
        )


# ================================================================
# VALIDAÇÕES DE QUANTIDADE (INVESTIMENTOS)
# ================================================================

def validate_quantity(
    quantity: float,
    request: Request,
    message_key: str = "ERROR_INVALID_QUANTITY"
) -> None:
    """
    Valida que quantity > 0.
    
    Args:
        quantity: Quantidade (ex: ações, cotas)
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_QUANTITY)
    
    Raises:
        ValidationException: Se quantity <= 0
    
    Exemplo:
        validate_quantity(10.5, request)  # ✅ Válido
        validate_quantity(0, request)     # ❌ Inválido
    """
    if quantity <= 0:
        raise ValidationException(
            message_key=message_key,
            request=request
        )


# ================================================================
# VALIDAÇÕES DE PREÇO (INVESTIMENTOS)
# ================================================================

def validate_price(
    price: float,
    request: Request,
    message_key: str = "ERROR_INVALID_PRICE"
) -> None:
    """
    Valida que price > 0.
    
    Args:
        price: Preço por unidade
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_PRICE)
    
    Raises:
        ValidationException: Se price <= 0
    
    Exemplo:
        validate_price(15.50, request)  # ✅ Válido
        validate_price(0, request)      # ❌ Inválido
    """
    if price <= 0:
        raise ValidationException(
            message_key=message_key,
            request=request
        )


# ================================================================
# VALIDAÇÃO DE SENHA
# ================================================================

def validate_password_strength(password: str) -> None:
    """
    Valida a força da senha (pelo menos 3 dos 4 critérios).
    
    Critérios:
    - Mínimo 8 caracteres
    - Letra maiúscula
    - Letra minúscula
    - Número
    - Caractere especial
    
    Args:
        password: Senha a ser validada
    
    Raises:
        ValueError: Se a senha não atender aos critérios
    
    Exemplo:
        >>> validate_password_strength("Senha@123")  # ✅ Válido
        >>> validate_password_strength("senha123")   # ❌ Inválido (sem maiúscula e especial)
    """
    if len(password) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres")
    
    criteria = 0
    if re.search(r"[A-Z]", password):
        criteria += 1
    if re.search(r"[a-z]", password):
        criteria += 1
    if re.search(r"\d", password):
        criteria += 1
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        criteria += 1
    
    if criteria < 3:
        raise ValueError(
            'A senha deve conter pelo menos 3 dos seguintes: '
            'letra maiúscula, letra minúscula, número, caractere especial'
        )


# ================================================================
# FUNÇÕES AUXILIARES PARA METAS
# ================================================================

def add_calculated_fields(goal: dict) -> dict:
    """
    Adiciona campos calculados à meta.
    - progress_percentage: Percentual concluído (0-100)
    - remaining_amount: Valor restante para atingir a meta
    
    Args:
        goal: Dicionário da meta
    
    Returns:
        dict: Dicionário com campos calculados adicionados
    
    Exemplo:
        >>> goal = {"target": 10000, "current": 7500}
        >>> add_calculated_fields(goal)
        {"target": 10000, "current": 7500, "progress_percentage": 75.0, "remaining_amount": 2500}
    """
    if not goal:
        return goal
    
    result = goal.copy()
    
    target = result.get("target", 0)
    current = result.get("current", 0)
    
    if target > 0:
        result["progress_percentage"] = min((current / target) * 100, 100)
    else:
        result["progress_percentage"] = 0
    
    result["remaining_amount"] = max(target - current, 0)
    
    return result


# ================================================================
# FUNÇÕES PARA INVESTIMENTOS
# ================================================================

def prepare_investment_response(investment: dict) -> dict:
    """
    Prepara o investimento para resposta (converte centavos para reais).
    
    Args:
        investment: Dicionário do investimento
    
    Returns:
        dict: Dicionário com valores convertidos
    
    Exemplo:
        >>> investment = {"amount": 15050, "quantity": 150}
        >>> prepare_investment_response(investment)
        {"amount": 150.50, "quantity": 1.5}
    """
    if not investment:
        return investment
    
    result = investment.copy()
    
    if "amount" in result:
        result["amount"] = from_cents(result["amount"])
    if "current_value" in result and result["current_value"] is not None:
        result["current_value"] = from_cents(result["current_value"])
    if "purchase_price_per_unit" in result and result["purchase_price_per_unit"] is not None:
        result["purchase_price_per_unit"] = from_cents(result["purchase_price_per_unit"])
    if "current_price_per_unit" in result and result["current_price_per_unit"] is not None:
        result["current_price_per_unit"] = from_cents(result["current_price_per_unit"])
    if "profit_loss" in result and result["profit_loss"] is not None:
        result["profit_loss"] = from_cents(result["profit_loss"])
    if "sold_value" in result and result["sold_value"] is not None:
        result["sold_value"] = from_cents(result["sold_value"])
    if "dividends_received" in result and result["dividends_received"] is not None:
        result["dividends_received"] = from_cents(result["dividends_received"])
    if "fees" in result and result["fees"] is not None:
        result["fees"] = from_cents(result["fees"])
    
    if "quantity" in result and result["quantity"] is not None:
        result["quantity"] = result["quantity"] / 100
    
    return result


def prepare_investment_for_db(data: dict) -> dict:
    """
    Prepara os dados para salvar no banco (converte reais para centavos).
    Usa Decimal para precisão em quantity.
    
    Args:
        data: Dicionário com dados do investimento
    
    Returns:
        dict: Dicionário com valores convertidos para centavos
    
    Exemplo:
        >>> data = {"amount": 150.50, "quantity": 1.5}
        >>> prepare_investment_for_db(data)
        {"amount": 15050, "quantity": 150}
    """
    result = {}
    
    for key, value in data.items():
        if value is None:
            result[key] = None
        elif key in ["amount", "current_value", "purchase_price_per_unit", "current_price_per_unit", 
                     "profit_loss", "sold_value", "dividends_received", "fees"]:
            if isinstance(value, (int, float)):
                result[key] = to_cents(float(value))
            else:
                result[key] = value
        elif key == "quantity":
            if value is None:
                result[key] = None
            elif isinstance(value, (int, float)):
                result[key] = int(Decimal(str(value)) * 100)
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ Funções reutilizáveis para validações comuns
# ✅ Suporte a i18n via Request
# ✅ Mensagens de erro customizáveis
# ✅ Validação de parcelas (1-360)
# ✅ Validação de valores (> 0)
# ✅ Validação de taxas de juros (0-100%)
# ✅ Validação de quantidade (> 0)
# ✅ Validação de preço (> 0)
# ✅ Validação de senha (3/4 critérios)
# ✅ Campos calculados para metas (progress_percentage, remaining_amount)
# ✅ Preparação de investimentos para resposta (centavos → reais)
# ✅ Preparação de investimentos para banco (reais → centavos com Decimal)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO