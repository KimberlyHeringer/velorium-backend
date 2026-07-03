"""
Funções de Validação de Data
Arquivo: backend/app/utils/date_utils.py

Funcionalidade: Centraliza validações de data para reutilização
em diferentes rotas (bills, bill_installments, credit_card_purchases, etc).

🔧 USO:
    from app.utils.date_utils import (
        validate_date_not_past,
        validate_date_range,
        validate_due_day,
        parse_installments_dates,
        get_month_range
    )
    
    validate_date_not_past(first_due, request)
    validate_date_range(start_date, end_date, request)
    validate_due_day(due_day, reference_date, request)
    get_month_range()  # Retorna (inicio_mes, fim_mes)

📋 ESTRUTURA:
    - get_month_range(): Retorna início e fim do mês atual (UTC)
    - validate_date_not_past(): Valida que data não é passada
    - validate_date_range(): Valida que start_date <= end_date
    - validate_due_day(): Valida que due_day é válido para o mês
    - parse_installments_dates(): Converte string para datetime
"""

from datetime import datetime, timezone
from calendar import monthrange
from typing import Optional, Tuple
from fastapi import Request

from app.utils.exceptions import ValidationException


# ================================================================
# GET MONTH RANGE (NOVO - necessário para transactions.py)
# ================================================================

def get_month_range() -> Tuple[datetime, datetime]:
    """
    Retorna o início e fim do mês atual (UTC).
    
    Returns:
        Tuple[datetime, datetime]: (início_do_mês, fim_do_mês)
    
    Exemplo:
        >>> start, end = get_month_range()
        >>> start  # datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        >>> end    # datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    """
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    if now.month == 12:
        end_of_month = now.replace(
            year=now.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
    else:
        end_of_month = now.replace(
            month=now.month + 1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
    
    return start_of_month, end_of_month


# ================================================================
# VALIDAÇÕES DE DATA
# ================================================================

def validate_date_not_past(
    date: datetime,
    request: Request,
    message_key: str = "ERROR_DATE_PAST"
) -> None:
    """
    Valida que uma data não seja no passado.
    
    Args:
        date: Data a ser validada
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro
    
    Raises:
        ValidationException: Se a data for no passado
    
    Exemplo:
        validate_date_not_past(first_due_date, request)
    """
    if date < datetime.now(timezone.utc):
        raise ValidationException(
            message_key=message_key,
            request=request
        )


def validate_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    request: Request,
    message_key: str = "ERROR_INVALID_DATE_RANGE"
) -> None:
    """
    Valida que start_date <= end_date.
    
    Args:
        start_date: Data inicial
        end_date: Data final
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro
    
    Raises:
        ValidationException: Se start_date > end_date
    
    Exemplo:
        validate_date_range(start_date, end_date, request)
    """
    if start_date and end_date and start_date > end_date:
        raise ValidationException(
            message_key=message_key,
            request=request
        )


def validate_due_day(
    due_day: int,
    reference_date: datetime,
    request: Request,
    message_key: str = "ERROR_INVALID_DUE_DAY"
) -> None:
    """
    Valida que due_day é válido para o mês.
    
    Args:
        due_day: Dia de vencimento
        reference_date: Data de referência (mês/ano)
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro
    
    Raises:
        ValidationException: Se due_day > último dia do mês
    
    Exemplo:
        validate_due_day(31, start_date, request)  # Válido apenas se mês tem 31
    """
    _, last_day = monthrange(reference_date.year, reference_date.month)
    if due_day > last_day:
        raise ValidationException(
            message_key=message_key,
            request=request
        )


def parse_installments_dates(
    installments: dict,
    request: Request = None
) -> dict:
    """
    Converte start_date de string para datetime se necessário.
    Cria uma cópia antes de modificar (evita efeitos colaterais).
    Valida se start_date não é uma data passada.
    
    Args:
        installments: Dicionário com dados de parcelamento
        request: Objeto Request (para i18n)
    
    Returns:
        dict: Dicionário com start_date convertido (cópia)
    
    Exemplo:
        installments = {"total": 12, "start_date": "2025-01-01"}
        parsed = parse_installments_dates(installments, request)
        # parsed["start_date"] = datetime(2025, 1, 1)
    """
    if not installments or not isinstance(installments, dict):
        return installments
    
    # Cria uma cópia antes de modificar
    result = installments.copy()
    start_date = result.get("start_date")
    
    if start_date and isinstance(start_date, str):
        try:
            dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            # Valida se não é data passada
            if dt < datetime.now(timezone.utc):
                raise ValidationException(
                    message_key="ERROR_START_DATE_PAST",
                    request=request
                )
            result["start_date"] = dt
        except (ValueError, TypeError):
            # Se não conseguir converter, mantém o original
            pass
    
    return result


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ get_month_range(): Retorna início e fim do mês atual (UTC)
# ✅ Funções reutilizáveis para validação de data
# ✅ Suporte a i18n via Request
# ✅ Mensagens de erro customizáveis
# ✅ Cópia antes de modificar (evita efeitos colaterais)
# ✅ Validação de data passada
# ✅ Validação de intervalo de datas
# ✅ Validação de dia de vencimento
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO