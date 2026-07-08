"""
Validações Extras para Rotas
Arquivo: backend/app/utils/validators_extras.py

Funcionalidade: Centraliza validações e funções auxiliares usadas em múltiplas rotas
(parcelas, valores, taxas de juros, metas, investimentos, etc).

Funcionalidades:
- Validação de parcelas (1-360)
- Validação de valores monetários (> 0)
- Validação de taxas de juros (0-100%)
- Validação de quantidade (> 0)
- Validação de preço (> 0)
- Validação de força de senha (3/4 critérios)
- Campos calculados para metas (progress_percentage, remaining_amount)
- Preparação de investimentos para resposta (centavos → reais)
- Preparação de investimentos para banco (reais → centavos com Decimal)

Principais features:
- 🔧 NOVO: Internacionalização (i18n) nas mensagens de erro
- 🔧 NOVO: Logs informativos para validações
- 🔧 CORRIGIDO: Verificação de None em todas as validações
- 🔧 CORRIGIDO: Verificação de tipo (isinstance) para robustez
- 🔧 CORRIGIDO: validate_password_strength com i18n
- 🔧 CORRIGIDO: prepare_investment_response com verificação de None e tipo
- 🔧 CORRIGIDO: prepare_investment_for_db com verificação de None e tipo
- ✅ Funções reutilizáveis para validações comuns
- ✅ Suporte a i18n via Request
- ✅ Mensagens de erro customizáveis
- ✅ Validação de parcelas (1-360)
- ✅ Validação de valores (> 0)
- ✅ Validação de taxas de juros (0-100%)
- ✅ Validação de quantidade (> 0)
- ✅ Validação de preço (> 0)
- ✅ Validação de senha (3/4 critérios)
- ✅ Campos calculados para metas
- ✅ Preparação de investimentos para resposta
- ✅ Preparação de investimentos para banco com Decimal

Regra: 2.8 (Logs)
Regra: 5.1 (Tratamento de erros)
Regra: 7.1 (Internacionalização)

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
    
    # Validar parcelas
    validate_installments(12, request)
    
    # Validar senha
    validate_password_strength("Senha@123")
    
    # Preparar meta com campos calculados
    goal = add_calculated_fields(goal_data)
    
    # Preparar investimento para resposta
    response = prepare_investment_response(investment)
"""

from fastapi import Request
from decimal import Decimal
import re
from typing import Optional, Any, Dict

from app.core.constants import MAX_INSTALLMENTS, MIN_INTEREST_RATE, MAX_INTEREST_RATE
from app.utils.exceptions import ValidationException
from app.utils.currency import to_cents, from_cents
from app.utils.logger import setup_logger
from app.utils.i18n import get_message

logger = setup_logger(__name__)


# ================================================================
# VALIDAÇÕES DE INSTALLMENTS (PARCELAS)
# ================================================================

def validate_installments(
    installments: Optional[int],
    request: Request,
    message_key: str = "ERROR_INVALID_INSTALLMENTS"
) -> None:
    """
    Valida número de parcelas (1-360).
    
    🔧 USO:
        validate_installments(12, request)  # ✅ Válido
        validate_installments(400, request) # ❌ Inválido (> 360)
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verifica se installments não é None
        - 🔧 CORRIGIDO: Verifica se é inteiro
        - Verifica se installments > 0
        - Verifica se installments <= MAX_INSTALLMENTS
        - Logs com i18n
        - Mensagens de erro com i18n
    
    Args:
        installments: Número de parcelas
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_INSTALLMENTS)
    
    Raises:
        ValidationException: Se installments for None, não for int, <= 0 ou > MAX_INSTALLMENTS
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 CORRIGIDO: Verificação de None
    if installments is None:
        logger.warning(get_message("VALIDATION_INSTALLMENTS_NONE", language))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(installments, int):
        logger.warning(get_message("VALIDATION_INSTALLMENTS_TYPE", language, type=type(installments).__name__))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    if installments <= 0:
        logger.warning(get_message("VALIDATION_INSTALLMENTS_ZERO", language, installments=installments))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    if installments > MAX_INSTALLMENTS:
        logger.warning(get_message("VALIDATION_INSTALLMENTS_MAX", language, installments=installments, max=MAX_INSTALLMENTS))
        raise ValidationException(
            message_key="ERROR_MAX_INSTALLMENTS_EXCEEDED",
            request=request
        )
    
    logger.debug(get_message("VALIDATION_INSTALLMENTS_OK", language, installments=installments))


# ================================================================
# VALIDAÇÕES DE VALORES MONETÁRIOS
# ================================================================

def validate_amount(
    amount: Optional[int],
    request: Request,
    message_key: str = "ERROR_AMOUNT_INVALID"
) -> None:
    """
    Valida que amount > 0.
    
    🔧 USO:
        validate_amount(10000, request)  # ✅ Válido (R$ 100,00)
        validate_amount(0, request)      # ❌ Inválido
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verifica se amount não é None
        - 🔧 CORRIGIDO: Verifica se é inteiro
        - Verifica se amount > 0
        - Logs com i18n
        - Mensagens de erro com i18n
    
    Args:
        amount: Valor em centavos
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_AMOUNT_INVALID)
    
    Raises:
        ValidationException: Se amount for None, não for int ou <= 0
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 CORRIGIDO: Verificação de None
    if amount is None:
        logger.warning(get_message("VALIDATION_AMOUNT_NONE", language))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(amount, int):
        logger.warning(get_message("VALIDATION_AMOUNT_TYPE", language, type=type(amount).__name__))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    if amount <= 0:
        logger.warning(get_message("VALIDATION_AMOUNT_ZERO", language, amount=amount))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    logger.debug(get_message("VALIDATION_AMOUNT_OK", language, amount=amount))


# ================================================================
# VALIDAÇÕES DE TAXA DE JUROS
# ================================================================

def validate_interest_rate(
    rate: Optional[float],
    request: Request,
    message_key: str = "ERROR_INVALID_INTEREST_RATE"
) -> None:
    """
    Valida que interest_rate esteja entre 0% e 100%.
    
    🔧 USO:
        validate_interest_rate(2.5, request)  # ✅ Válido (2.5%)
        validate_interest_rate(150, request)  # ❌ Inválido (> 100%)
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verifica se rate não é None
        - 🔧 CORRIGIDO: Verifica se é número
        - Verifica se rate >= MIN_INTEREST_RATE
        - Verifica se rate <= MAX_INTEREST_RATE
        - Logs com i18n
        - Mensagens de erro com i18n
    
    Args:
        rate: Taxa de juros mensal (%)
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_INTEREST_RATE)
    
    Raises:
        ValidationException: Se rate for None, não for número, < 0 ou > 100
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 CORRIGIDO: Verificação de None
    if rate is None:
        logger.warning(get_message("VALIDATION_INTEREST_RATE_NONE", language))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(rate, (int, float)):
        logger.warning(get_message("VALIDATION_INTEREST_RATE_TYPE", language, type=type(rate).__name__))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    if rate < MIN_INTEREST_RATE or rate > MAX_INTEREST_RATE:
        logger.warning(get_message("VALIDATION_INTEREST_RATE_INVALID", language, rate=rate))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    logger.debug(get_message("VALIDATION_INTEREST_RATE_OK", language, rate=rate))


# ================================================================
# VALIDAÇÕES DE QUANTIDADE (INVESTIMENTOS)
# ================================================================

def validate_quantity(
    quantity: Optional[float],
    request: Request,
    message_key: str = "ERROR_INVALID_QUANTITY"
) -> None:
    """
    Valida que quantity > 0.
    
    🔧 USO:
        validate_quantity(10.5, request)  # ✅ Válido
        validate_quantity(0, request)     # ❌ Inválido
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verifica se quantity não é None
        - 🔧 CORRIGIDO: Verifica se é número
        - Verifica se quantity > 0
        - Logs com i18n
        - Mensagens de erro com i18n
    
    Args:
        quantity: Quantidade (ex: ações, cotas)
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_QUANTITY)
    
    Raises:
        ValidationException: Se quantity for None, não for número ou <= 0
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 CORRIGIDO: Verificação de None
    if quantity is None:
        logger.warning(get_message("VALIDATION_QUANTITY_NONE", language))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(quantity, (int, float)):
        logger.warning(get_message("VALIDATION_QUANTITY_TYPE", language, type=type(quantity).__name__))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    if quantity <= 0:
        logger.warning(get_message("VALIDATION_QUANTITY_ZERO", language, quantity=quantity))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    logger.debug(get_message("VALIDATION_QUANTITY_OK", language, quantity=quantity))


# ================================================================
# VALIDAÇÕES DE PREÇO (INVESTIMENTOS)
# ================================================================

def validate_price(
    price: Optional[float],
    request: Request,
    message_key: str = "ERROR_INVALID_PRICE"
) -> None:
    """
    Valida que price > 0.
    
    🔧 USO:
        validate_price(15.50, request)  # ✅ Válido
        validate_price(0, request)      # ❌ Inválido
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verifica se price não é None
        - 🔧 CORRIGIDO: Verifica se é número
        - Verifica se price > 0
        - Logs com i18n
        - Mensagens de erro com i18n
    
    Args:
        price: Preço por unidade
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro (padrão: ERROR_INVALID_PRICE)
    
    Raises:
        ValidationException: Se price for None, não for número ou <= 0
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 CORRIGIDO: Verificação de None
    if price is None:
        logger.warning(get_message("VALIDATION_PRICE_NONE", language))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(price, (int, float)):
        logger.warning(get_message("VALIDATION_PRICE_TYPE", language, type=type(price).__name__))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    if price <= 0:
        logger.warning(get_message("VALIDATION_PRICE_ZERO", language, price=price))
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    logger.debug(get_message("VALIDATION_PRICE_OK", language, price=price))


# ================================================================
# VALIDAÇÃO DE SENHA
# ================================================================

def validate_password_strength(password: str) -> None:
    """
    🔧 CORRIGIDO: Valida a força da senha (pelo menos 3 dos 4 critérios).
    
    Critérios:
    - Mínimo 8 caracteres
    - Letra maiúscula
    - Letra minúscula
    - Número
    - Caractere especial
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verifica se password não é None
        - 🔧 CORRIGIDO: Verifica se é string
        - 🔧 CORRIGIDO: Mensagens com i18n
        - Logs com i18n
        - ⚠️ Idioma fixo em "pt" (não recebe request)
    
    Args:
        password: Senha a ser validada
    
    Raises:
        ValueError: Se a senha não atender aos critérios
    
    Exemplo:
        >>> validate_password_strength("Senha@123")  # ✅ Válido
        >>> validate_password_strength("senha123")   # ❌ Inválido (sem maiúscula e especial)
    """
    # ⚠️ Idioma fixo em "pt" - função não recebe request
    language = "pt"
    
    # 🔧 CORRIGIDO: Verificação de None
    if password is None:
        logger.warning(get_message("VALIDATION_PASSWORD_NONE", language))
        raise ValueError(get_message("VALIDATION_PASSWORD_NONE", language))
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(password, str):
        logger.warning(get_message("VALIDATION_PASSWORD_TYPE", language, type=type(password).__name__))
        raise ValueError(get_message("VALIDATION_PASSWORD_TYPE", language))
    
    if len(password) < 8:
        logger.warning(get_message("VALIDATION_PASSWORD_LENGTH", language))
        raise ValueError(get_message("VALIDATION_PASSWORD_LENGTH", language))
    
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
        logger.warning(get_message("VALIDATION_PASSWORD_CRITERIA", language))
        raise ValueError(get_message("VALIDATION_PASSWORD_CRITERIA", language))
    
    logger.debug(get_message("VALIDATION_PASSWORD_OK", language))


# ================================================================
# FUNÇÕES AUXILIARES PARA METAS
# ================================================================

def add_calculated_fields(goal: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Adiciona campos calculados à meta.
    - progress_percentage: Percentual concluído (0-100)
    - remaining_amount: Valor restante para atingir a meta
    
    🔧 USO:
        goal = {"target": 10000, "current": 7500}
        result = add_calculated_fields(goal)
        # result = {"target": 10000, "current": 7500, "progress_percentage": 75.0, "remaining_amount": 2500}
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verificação explícita de None
        - 🔧 CORRIGIDO: Verificação de tipo (isinstance)
        - 🔧 CORRIGIDO: Logs apropriados para cada caso
        - Calcula progress_percentage com base em target e current
        - Calcula remaining_amount como target - current
        - Logs de debug
    
    Args:
        goal: Dicionário da meta
    
    Returns:
        dict: Dicionário com campos calculados adicionados
    """
    # 🔧 CORRIGIDO: Verificação explícita de None
    if goal is None:
        logger.debug("ℹ️ goal é None, retornando dicionário vazio")
        return {}
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(goal, dict):
        logger.error(f"❌ goal não é um dicionário: {type(goal)}")
        return {}
    
    # 🔧 CORRIGIDO: Verificação de vazio com log apropriado
    if not goal:
        logger.debug("ℹ️ goal é um dicionário vazio")
        return {}
    
    result = goal.copy()
    
    target = result.get("target", 0)
    current = result.get("current", 0)
    
    if target > 0:
        result["progress_percentage"] = min((current / target) * 100, 100)
    else:
        result["progress_percentage"] = 0
    
    result["remaining_amount"] = max(target - current, 0)
    
    logger.debug(f"✅ Campos calculados adicionados: progress={result['progress_percentage']:.1f}%, remaining=R${result['remaining_amount']:.2f}")
    
    return result


# ================================================================
# FUNÇÕES PARA INVESTIMENTOS
# ================================================================

def prepare_investment_response(investment: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    🔧 CORRIGIDO: Prepara o investimento para resposta (converte centavos para reais).
    
    🔧 USO:
        investment = {"amount": 15050, "quantity": 150}
        result = prepare_investment_response(investment)
        # result = {"amount": 150.50, "quantity": 1.5}
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verificação explícita de None
        - 🔧 CORRIGIDO: Verificação de tipo (isinstance)
        - 🔧 CORRIGIDO: Logs apropriados para cada caso
        - Converte campos monetários de centavos para reais
        - Converte quantity para decimal
        - Logs de debug
    
    Args:
        investment: Dicionário do investimento
    
    Returns:
        dict: Dicionário com valores convertidos
    """
    # 🔧 CORRIGIDO: Verificação explícita de None
    if investment is None:
        logger.debug("ℹ️ investment é None, retornando dicionário vazio")
        return {}
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(investment, dict):
        logger.error(f"❌ investment não é um dicionário: {type(investment)}")
        return {}
    
    # 🔧 CORRIGIDO: Verificação de vazio com log apropriado
    if not investment:
        logger.debug("ℹ️ investment é um dicionário vazio")
        return {}
    
    result = investment.copy()
    
    monetary_fields = [
        "amount", "current_value", "purchase_price_per_unit", "current_price_per_unit",
        "profit_loss", "sold_value", "dividends_received", "fees"
    ]
    
    for field in monetary_fields:
        if field in result and result[field] is not None:
            result[field] = from_cents(result[field])
    
    if "quantity" in result and result["quantity"] is not None:
        result["quantity"] = result["quantity"] / 100
    
    logger.debug(f"✅ Investimento preparado para resposta: {len(result)} campos")
    
    return result


def prepare_investment_for_db(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    🔧 CORRIGIDO: Prepara os dados para salvar no banco (converte reais para centavos).
    Usa Decimal para precisão em quantity.
    
    🔧 USO:
        data = {"amount": 150.50, "quantity": 1.5}
        result = prepare_investment_for_db(data)
        # result = {"amount": 15050, "quantity": 150}
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verificação explícita de None
        - 🔧 CORRIGIDO: Verificação de tipo (isinstance)
        - 🔧 CORRIGIDO: Logs apropriados para cada caso
        - Converte campos monetários de reais para centavos
        - Converte quantity usando Decimal para precisão
        - Logs de debug
    
    Args:
        data: Dicionário com dados do investimento
    
    Returns:
        dict: Dicionário com valores convertidos para centavos
    """
    # 🔧 CORRIGIDO: Verificação explícita de None
    if data is None:
        logger.warning("⚠️ data é None, retornando dicionário vazio")
        return {}
    
    # 🔧 CORRIGIDO: Verificação de tipo
    if not isinstance(data, dict):
        logger.error(f"❌ data não é um dicionário: {type(data)}")
        return {}
    
    # 🔧 CORRIGIDO: Verificação de vazio com log apropriado
    if not data:
        logger.debug("ℹ️ data é um dicionário vazio")
        return {}
    
    result = {}
    
    monetary_fields = [
        "amount", "current_value", "purchase_price_per_unit", "current_price_per_unit",
        "profit_loss", "sold_value", "dividends_received", "fees"
    ]
    
    for key, value in data.items():
        if value is None:
            result[key] = None
        elif key in monetary_fields:
            if isinstance(value, (int, float)):
                result[key] = to_cents(float(value))
            else:
                logger.warning(f"⚠️ Campo '{key}' com valor não numérico: {value}")
                result[key] = value
        elif key == "quantity":
            if value is None:
                result[key] = None
            elif isinstance(value, (int, float)):
                result[key] = int(Decimal(str(value)) * 100)
            else:
                logger.warning(f"⚠️ Campo 'quantity' com valor não numérico: {value}")
                result[key] = value
        else:
            result[key] = value
    
    logger.debug(f"✅ Investimento preparado para banco: {len(result)} campos")
    
    return result


# ================================================================
# NOTAS DE IMPLEMENTAÇÃO
# ================================================================

"""
📌 COMO USAR:

1. Validar parcelas:
   from app.utils.validators_extras import validate_installments
   validate_installments(12, request)

2. Validar valor monetário:
   from app.utils.validators_extras import validate_amount
   validate_amount(10000, request)  # R$ 100,00

3. Validar taxa de juros:
   from app.utils.validators_extras import validate_interest_rate
   validate_interest_rate(2.5, request)

4. Validar senha:
   from app.utils.validators_extras import validate_password_strength
   validate_password_strength("Senha@123")

5. Adicionar campos calculados à meta:
   from app.utils.validators_extras import add_calculated_fields
   goal = add_calculated_fields(goal_data)

6. Preparar investimento para resposta:
   from app.utils.validators_extras import prepare_investment_response
   response = prepare_investment_response(investment)

7. Preparar investimento para banco:
   from app.utils.validators_extras import prepare_investment_for_db
   db_data = prepare_investment_for_db(data)
"""


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
# ✅ Campos calculados para metas
# ✅ Preparação de investimentos para resposta (centavos → reais)
# ✅ Preparação de investimentos para banco (reais → centavos com Decimal)
# ✅ 🔧 NOVO: Internacionalização (i18n) nas mensagens
# ✅ 🔧 NOVO: Logs informativos para validações
# ✅ 🔧 CORRIGIDO: Verificação de None em todas as validações
# ✅ 🔧 CORRIGIDO: Verificação de tipo (isinstance) para robustez
# ✅ 🔧 CORRIGIDO: validate_password_strength com i18n (idioma fixo pt)
# ✅ 🔧 CORRIGIDO: prepare_investment_response com verificação de None e tipo
# ✅ 🔧 CORRIGIDO: prepare_investment_for_db com verificação de None e tipo
# ✅ 🔧 CORRIGIDO: add_calculated_fields com verificação de None e tipo
#
# ❌ Não implementado:
#   - Validação de CPF/CNPJ (não necessário para o MVP - decisão de produto)
#   - Validação de telefone (não necessário para o MVP - decisão de produto)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado i18n, logs, verificação de None em todas as funções (06/07/2026)
#   - v3: Removido CPF/CNPJ e telefone (decisão de produto - 06/07/2026)
#   - v4: Adicionado verificação de tipo (isinstance) para robustez (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO