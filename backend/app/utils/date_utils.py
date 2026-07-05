"""
Funções de Validação de Data
Arquivo: backend/app/utils/date_utils.py

Funcionalidades:
- get_month_range(): Retorna início e fim do mês atual (UTC)
- get_next_month(): Retorna o primeiro dia do próximo mês
- get_previous_month(): Retorna o primeiro dia do mês anterior
- validate_date_not_past(): Valida que data não é passada
- validate_date_not_future(): Valida que data não é futura
- validate_date_range(): Valida que start_date <= end_date
- validate_due_day(): Valida que due_day é válido para o mês
- parse_installments_dates(): Converte string para datetime e valida due_day

Principais features:
- 🔧 CORRIGIDO: Documentação completa
- 🔧 CORRIGIDO: setup_logger configurado
- 🔧 CORRIGIDO: Validações simplificadas (sempre passam request)
- 🔧 CORRIGIDO: Logs de debug
- 🔧 CORRIGIDO: Suporte a validação de data futura
- 🔧 CORRIGIDO: i18n com fallback
- 🆕 NOVO: get_next_month() e get_previous_month()
- 🆕 NOVO: parse_installments_dates valida due_day

🔧 USO:
    from app.utils.date_utils import (
        get_month_range,
        get_next_month,
        get_previous_month,
        validate_date_not_past,
        validate_date_not_future,
        validate_date_range,
        validate_due_day,
        parse_installments_dates
    )
    
    # Mês atual
    start, end = get_month_range()
    
    # Próximo mês
    next_month = get_next_month(start)
    
    # Validações
    validate_date_not_past(first_due, request)
    validate_date_range(start_date, end_date, request)
    
    # Parse e validação de parcelas
    installments = parse_installments_dates({
        "total": 12,
        "start_date": "2025-01-01",
        "due_day": 15
    }, request)
"""

from datetime import datetime, timezone
from calendar import monthrange
from typing import Optional, Tuple
from fastapi import Request

from app.utils.logger import setup_logger
from app.utils.exceptions import ValidationException

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)


# ================================================================
# GET MONTH RANGE
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
    
    logger.debug(f"📅 Mês atual: {start_of_month.strftime('%Y-%m')}")
    return start_of_month, end_of_month


# ================================================================
# GET NEXT / PREVIOUS MONTH
# ================================================================

def get_next_month(reference_date: datetime) -> datetime:
    """
    🆕 NOVO: Retorna o primeiro dia do próximo mês.
    
    Args:
        reference_date: Data de referência
    
    Returns:
        datetime: Primeiro dia do próximo mês
    
    Exemplo:
        >>> get_next_month(datetime(2026, 7, 15))
        datetime(2026, 8, 1)
    """
    if reference_date.month == 12:
        return reference_date.replace(year=reference_date.year + 1, month=1, day=1)
    return reference_date.replace(month=reference_date.month + 1, day=1)


def get_previous_month(reference_date: datetime) -> datetime:
    """
    🆕 NOVO: Retorna o primeiro dia do mês anterior.
    
    Args:
        reference_date: Data de referência
    
    Returns:
        datetime: Primeiro dia do mês anterior
    
    Exemplo:
        >>> get_previous_month(datetime(2026, 7, 15))
        datetime(2026, 6, 1)
    """
    if reference_date.month == 1:
        return reference_date.replace(year=reference_date.year - 1, month=12, day=1)
    return reference_date.replace(month=reference_date.month - 1, day=1)


# ================================================================
# VALIDAÇÕES DE DATA
# ================================================================

def validate_date_not_past(
    date: datetime,
    request: Optional[Request] = None,
    message_key: str = "ERROR_DATE_PAST",
    field_name: str = "data"
) -> None:
    """
    Valida que uma data não seja no passado.
    
    Args:
        date: Data a ser validada
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro
        field_name: Nome do campo para a mensagem
    
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
    
    logger.debug(f"✅ {field_name} validada (não é passada): {date.isoformat()}")


def validate_date_not_future(
    date: datetime,
    request: Optional[Request] = None,
    message_key: str = "ERROR_DATE_FUTURE",
    field_name: str = "data"
) -> None:
    """
    Valida que uma data não seja no futuro.
    
    Args:
        date: Data a ser validada
        request: Objeto Request (para i18n)
        message_key: Chave da mensagem de erro
        field_name: Nome do campo para a mensagem
    
    Raises:
        ValidationException: Se a data for no futuro
    
    Exemplo:
        validate_date_not_future(date, request)
    """
    if date > datetime.now(timezone.utc):
        raise ValidationException(
            message_key=message_key,
            request=request
        )
    
    logger.debug(f"✅ {field_name} validada (não é futura): {date.isoformat()}")


def validate_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    request: Optional[Request] = None,
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
    
    if start_date and end_date:
        logger.debug(f"✅ Intervalo válido: {start_date.isoformat()} → {end_date.isoformat()}")


def validate_due_day(
    due_day: int,
    reference_date: datetime,
    request: Optional[Request] = None,
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
    
    logger.debug(f"✅ due_day {due_day} válido para {reference_date.strftime('%Y-%m')} (último dia: {last_day})")


def parse_installments_dates(
    installments: dict,
    request: Optional[Request] = None
) -> dict:
    """
    Converte start_date de string para datetime se necessário.
    Cria uma cópia antes de modificar (evita efeitos colaterais).
    Valida se start_date não é uma data passada.
    
    🆕 NOVO: Valida due_day com a start_date.
    
    Args:
        installments: Dicionário com dados de parcelamento
        request: Objeto Request (para i18n)
    
    Returns:
        dict: Dicionário com start_date convertido (cópia)
    
    Raises:
        ValidationException: Se start_date for no passado ou due_day inválido
    
    Exemplo:
        installments = {"total": 12, "start_date": "2025-01-01", "due_day": 15}
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
            
            if dt < datetime.now(timezone.utc):
                raise ValidationException(
                    message_key="ERROR_START_DATE_PAST",
                    request=request
                )
            
            result["start_date"] = dt
            
            # 🆕 NOVO: Valida due_day com a start_date
            due_day = result.get("due_day")
            if due_day is not None:
                validate_due_day(due_day, dt, request)
            
            logger.debug(f"✅ start_date convertida: {start_date} → {dt.isoformat()}")
            
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Erro ao converter start_date: {e}")
            # Se não conseguir converter, mantém o original
    
    return result


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ get_month_range(): Retorna início e fim do mês atual (UTC)
# ✅ get_next_month(): Retorna o primeiro dia do próximo mês
# ✅ get_previous_month(): Retorna o primeiro dia do mês anterior
# ✅ Funções reutilizáveis para validação de data
# ✅ Suporte a i18n via Request (com fallback)
# ✅ Mensagens de erro customizáveis
# ✅ Cópia antes de modificar (evita efeitos colaterais)
# ✅ Validação de data passada
# ✅ Validação de data futura
# ✅ Validação de intervalo de datas
# ✅ Validação de dia de vencimento
# ✅ 🔧 CORRIGIDO: Documentação completa
# ✅ 🔧 CORRIGIDO: setup_logger configurado
# ✅ 🔧 CORRIGIDO: Validações simplificadas (sempre passam request)
# ✅ 🔧 CORRIGIDO: Logs de debug
# ✅ 🔧 CORRIGIDO: i18n com fallback
# ✅ 🆕 NOVO: get_next_month() e get_previous_month()
# ✅ 🆕 NOVO: parse_installments_dates valida due_day
#
# ❌ Não implementado (Pós-MVP):
#   - get_business_days() (dias úteis com feriados)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração com i18n, logs, validações (05/07/2026)
#   - v3: Correção - Validações simplificadas com request=None (05/07/2026)
#   - v4: Novas funções - get_next_month, get_previous_month, validação due_day (05/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO