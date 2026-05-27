"""
Utilitários de Validação Centralizados
Arquivo: backend/app/utils/validators.py

Este módulo centraliza funções de validação e formatação
para evitar duplicação de código entre os models.
"""

from typing import Any, Dict, List, Optional, Union
import re
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException


# ========== FORMATAÇÃO DE VALORES MONETÁRIOS ==========

def round_amount(value: Optional[float], decimals: int = 2) -> Optional[float]:
    """
    Arredonda um valor para o número especificado de casas decimais.
    Usado para evitar problemas de precisão com float no MongoDB.
    
    Args:
        value: Valor a ser arredondado
        decimals: Número de casas decimais (padrão: 2)
    
    Returns:
        Valor arredondado ou None se valor for None
    """
    if value is not None:
        return round(value, decimals)
    return value


def round_amount_in_dict(data: Dict[str, Any], fields: List[str], decimals: int = 2) -> Dict[str, Any]:
    """
    Arredonda campos específicos em um dicionário.
    
    Args:
        data: Dicionário a ser processado
        fields: Lista de campos a serem arredondados
        decimals: Número de casas decimais
    
    Returns:
        Dicionário com campos arredondados
    """
    result = dict(data)
    for field in fields:
        if field in result and result[field] is not None:
            result[field] = round_amount(result[field], decimals)
    return result


# ========== VALIDAÇÃO DE DATAS ==========

def validate_date_not_future(date: datetime, field_name: str = "date") -> datetime:
    """
    Valida que uma data não está no futuro.
    
    Args:
        date: Data a ser validada
        field_name: Nome do campo (para mensagem de erro)
    
    Returns:
        Data validada
    
    Raises:
        ValueError: Se a data for futura
    """
    if date and date > datetime.now(timezone.utc):
        raise ValueError(f"{field_name} não pode ser uma data futura")
    return date


def validate_month_format(month: Optional[str]) -> Optional[str]:
    """
    Valida se o mês está no formato MM/YYYY.
    
    Args:
        month: String no formato MM/YYYY ou None
    
    Returns:
        Mês validado ou None
    
    Raises:
        ValueError: Se o formato for inválido
    """
    if month is None:
        return month
    
    if not re.match(r'^\d{2}/\d{4}$', month):
        raise ValueError('Mês deve estar no formato MM/YYYY (ex: 12/2025)')
    
    mes = int(month.split('/')[0])
    if mes < 1 or mes > 12:
        raise ValueError('Mês deve ser entre 01 e 12')
    
    return month


# ========== VALIDAÇÃO DE TIPOS ==========

def validate_achievement_type(type_value: str) -> str:
    """
    Valida se o tipo de conquista é permitido.
    
    Args:
        type_value: Tipo da conquista
    
    Returns:
        Tipo validado
    
    Raises:
        ValueError: Se o tipo não for permitido
    """
    tipos_validos = [
        'month_closed',
        'goal_completed',
        'score_milestone',
        'first_transaction',
        'savings_milestone',
        'debt_paid'
    ]
    if type_value not in tipos_validos:
        raise ValueError(f'Tipo de conquista inválido. Use um dos: {tipos_validos}')
    return type_value


def validate_currency(currency: str) -> str:
    """
    Valida se a moeda é suportada.
    
    Args:
        currency: Código da moeda
    
    Returns:
        Moeda validada
    
    Raises:
        ValueError: Se a moeda não for suportada
    """
    moedas_validas = ["BRL", "USD", "EUR", "CNY"]
    if currency not in moedas_validas:
        raise ValueError(f'Moeda inválida. Use uma das: {moedas_validas}')
    return currency


def validate_language(language: str) -> str:
    """
    Valida se o idioma é suportado.
    
    Args:
        language: Código do idioma
    
    Returns:
        Idioma validado
    
    Raises:
        ValueError: Se o idioma não for suportado
    """
    idiomas_validos = ["pt", "en", "es", "zh"]
    if language not in idiomas_validos:
        raise ValueError(f'Idioma inválido. Use um dos: {idiomas_validos}')
    return language


# ========== VALIDAÇÃO DE OBJECTID ==========

def validate_object_id(id_str: str, field_name: str = "id") -> str:
    """
    Valida se o ID é um ObjectId válido do MongoDB.
    
    Args:
        id_str: String do ID a ser validada
        field_name: Nome do campo para mensagem de erro
    
    Returns:
        O mesmo ID se válido
    
    Raises:
        HTTPException: Se o ID for inválido
    """
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=400, detail=f"{field_name} inválido")
    return id_str


# ========== FORMATAÇÃO DE DOCUMENTOS MONGODB ==========

def format_mongo_doc(doc: Optional[Dict]) -> Optional[Dict]:
    """
    Converte _id para id em documentos do MongoDB.
    Remove o _id original para evitar duplicação.
    
    Args:
        doc: Documento do MongoDB
    
    Returns:
        Documento formatado com campo 'id' (sem '_id')
    """
    if not doc:
        return doc
    
    result = dict(doc)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    return result


def format_mongo_list(docs: List[Dict]) -> List[Dict]:
    """
    Aplica format_mongo_doc a uma lista de documentos.
    
    Args:
        docs: Lista de documentos do MongoDB
    
    Returns:
        Lista de documentos formatados
    """
    return [format_mongo_doc(doc) for doc in docs]


def format_mongo_docs(docs: List[Dict]) -> List[Dict]:
    """
    Alias para format_mongo_list (mantém compatibilidade com código que usa este nome)
    """
    return format_mongo_list(docs)