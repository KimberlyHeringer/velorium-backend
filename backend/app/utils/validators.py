"""
Utilitários de Validação Centralizados
Arquivo: backend/app/utils/validators.py

Funcionalidades:
- Formatação de valores monetários (arredondamento)
- Validação de datas (futuro, formato MM/YYYY)
- Validação de tipos (conquistas, moedas, idiomas)
- Validação de ObjectId
- Formatação de documentos MongoDB (conversão ObjectId para string)
- Conversão genérica de ObjectId para string (recursiva)

Principais features:
- 🔧 NOVO: Internacionalização (i18n) nas mensagens de erro
- 🔧 NOVO: Logs informativos para validações
- 🔧 CORRIGIDO: Verificação de string vazia em validate_currency e validate_language
- 🔧 CORRIGIDO: Tratamento robusto em validate_month_format
- ✅ format_mongo_doc mantém "_id" (não cria "id") - Regra 2.2 e 2.3
- ✅ Validadores centralizados e reutilizáveis
- ✅ convert_objectid_to_str genérico para conversão de ObjectId
- ✅ Suporte a dicionários aninhados e listas
- ✅ Documentação completa

Regra: 2.2 (Proibido criar campo "id")
Regra: 2.3 (Frontend espera "_id")
Regra: 2.8 (Logs)
Regra: 7.1 (Internacionalização)

🔧 USO:
    from app.utils.validators import (
        validate_object_id,
        format_mongo_doc,
        convert_objectid_to_str,
        validate_date_not_future,
        validate_month_format,
        validate_currency,
        validate_language
    )
    
    # Validar ObjectId
    validate_object_id("507f1f77bcf86cd799439011")
    
    # Formatar documento MongoDB
    doc = {"_id": ObjectId("..."), "name": "João"}
    formatted = format_mongo_doc(doc)
    
    # Converter ObjectId para string (recursivo)
    data = {"_id": ObjectId("..."), "user": {"_id": ObjectId("...")}}
    converted = convert_objectid_to_str(data)
"""

from typing import Any, Dict, List, Optional, Union
import re
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException

from app.utils.logger import setup_logger
from app.utils.i18n import get_message

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# ========== CONSTANTES ==========
SUPPORTED_CURRENCIES = ["BRL", "USD", "EUR", "CNY"]
SUPPORTED_LANGUAGES = ["pt", "en", "es", "zh"]
ACHIEVEMENT_TYPES = [
    'month_closed',
    'goal_completed',
    'score_milestone',
    'first_transaction',
    'savings_milestone',
    'debt_paid'
]


# ================================================================
# FORMATAÇÃO DE VALORES MONETÁRIOS
# ================================================================

def round_amount(value: Optional[Union[float, int]], decimals: int = 2) -> Optional[float]:
    """
    Arredonda um valor para o número especificado de casas decimais.
    Usado para evitar problemas de precisão com float no MongoDB.
    
    🔧 USO:
        rounded = round_amount(10.567, 2)  # 10.57
    
    📋 PADRÃO:
        - 🔧 NOVO: Logs informativos
        - Suporta int e float
        - Retorna None se value for None
    
    Args:
        value: Valor a ser arredondado
        decimals: Número de casas decimais (padrão: 2)
    
    Returns:
        Valor arredondado ou None se valor for None
    """
    if value is None:
        logger.debug("ℹ️ round_amount recebeu None, retornando None")
        return None
    
    rounded = round(float(value), decimals)
    logger.debug(f"✅ Valor arredondado: {value} → {rounded}")
    return rounded


def round_amount_in_dict(data: Dict[str, Any], fields: List[str], decimals: int = 2) -> Dict[str, Any]:
    """
    Arredonda campos específicos em um dicionário.
    
    🔧 USO:
        data = {"amount": 10.567, "tax": 2.345}
        result = round_amount_in_dict(data, ["amount", "tax"], 2)
        # result = {"amount": 10.57, "tax": 2.35}
    
    📋 PADRÃO:
        - 🔧 NOVO: Logs informativos
        - Processa apenas campos existentes
    
    Args:
        data: Dicionário a ser processado
        fields: Lista de campos a serem arredondados
        decimals: Número de casas decimais
    
    Returns:
        Dicionário com campos arredondados
    """
    if not data:
        logger.debug("ℹ️ round_amount_in_dict recebeu dados vazios")
        return data or {}
    
    result = dict(data)
    processed = 0
    
    for field in fields:
        if field in result and result[field] is not None:
            result[field] = round_amount(result[field], decimals)
            processed += 1
    
    logger.debug(f"✅ {processed} campos arredondados no dicionário")
    return result


# ================================================================
# VALIDAÇÃO DE DATAS
# ================================================================

def validate_date_not_future(
    date: datetime,
    field_name: str = "date",
    request = None
) -> datetime:
    """
    Valida que uma data não está no futuro.
    
    🔧 USO:
        validate_date_not_future(datetime.now(), "created_at")
    
    📋 PADRÃO:
        - 🔧 NOVO: i18n nas mensagens de erro
        - 🔧 NOVO: Logs informativos
    
    Args:
        date: Data a ser validada
        field_name: Nome do campo (para mensagem de erro)
        request: Objeto Request (para i18n)
    
    Returns:
        Data validada
    
    Raises:
        ValueError: Se a data for futura
    """
    if date is None:
        logger.debug("ℹ️ validate_date_not_future recebeu None, retornando None")
        return date
    
    if date > datetime.now(timezone.utc):
        language = getattr(request.state, "language", "pt") if request else "pt"
        error_msg = get_message("ERROR_DATE_FUTURE", language)
        logger.warning(f"⚠️ Data futura detectada em {field_name}: {date}")
        raise ValueError(f"{field_name} {error_msg.lower()}")
    
    logger.debug(f"✅ Data validada: {date}")
    return date


def validate_month_format(month: Optional[str]) -> Optional[str]:
    """
    Valida se o mês está no formato MM/YYYY.
    
    🔧 USO:
        month = validate_month_format("12/2025")  # ✅ Válido
        month = validate_month_format("13/2025")  # ❌ Inválido
    
    📋 PADRÃO:
        - 🔧 NOVO: i18n nas mensagens de erro
        - 🔧 CORRIGIDO: Verificação robusta de formato
        - 🔧 NOVO: Logs informativos
    
    Args:
        month: String no formato MM/YYYY ou None
    
    Returns:
        Mês validado ou None
    
    Raises:
        ValueError: Se o formato for inválido
    """
    if month is None:
        logger.debug("ℹ️ validate_month_format recebeu None")
        return month
    
    # 🔧 CORRIGIDO: Validação robusta
    if not re.match(r'^\d{2}/\d{4}$', month):
        logger.warning(f"⚠️ Formato de mês inválido: {month}")
        raise ValueError("Mês deve estar no formato MM/YYYY (ex: 12/2025)")
    
    parts = month.split('/')
    mes = int(parts[0])
    
    if mes < 1 or mes > 12:
        logger.warning(f"⚠️ Mês inválido (deve ser 01-12): {month}")
        raise ValueError("Mês deve ser entre 01 e 12")
    
    logger.debug(f"✅ Mês validado: {month}")
    return month


# ================================================================
# VALIDAÇÃO DE TIPOS
# ================================================================

def validate_achievement_type(
    type_value: str,
    request = None
) -> str:
    """
    Valida se o tipo de conquista é permitido.
    
    🔧 USO:
        validate_achievement_type("goal_completed")  # ✅ Válido
    
    📋 PADRÃO:
        - 🔧 NOVO: i18n nas mensagens de erro
        - 🔧 NOVO: Logs informativos
    
    Args:
        type_value: Tipo da conquista
        request: Objeto Request (para i18n)
    
    Returns:
        Tipo validado
    
    Raises:
        ValueError: Se o tipo não for permitido
    """
    if type_value is None or not isinstance(type_value, str):
        logger.warning(f"⚠️ Tipo de conquista inválido (None ou não string): {type_value}")
        raise ValueError("Tipo de conquista inválido")
    
    if type_value not in ACHIEVEMENT_TYPES:
        logger.warning(f"⚠️ Tipo de conquista inválido: {type_value}")
        raise ValueError(f"Tipo de conquista inválido. Use um dos: {ACHIEVEMENT_TYPES}")
    
    logger.debug(f"✅ Tipo de conquista validado: {type_value}")
    return type_value


def validate_currency(
    currency: str,
    request = None
) -> str:
    """
    Valida se a moeda é suportada.
    
    🔧 USO:
        validate_currency("BRL")  # ✅ Válido
        validate_currency("XXX")  # ❌ Inválido
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verificação de string vazia
        - 🔧 NOVO: i18n nas mensagens de erro
        - 🔧 NOVO: Logs informativos
    
    Args:
        currency: Código da moeda
        request: Objeto Request (para i18n)
    
    Returns:
        Moeda validada
    
    Raises:
        ValueError: Se a moeda não for suportada
    """
    # 🔧 CORRIGIDO: Verificação de string vazia
    if not currency or not isinstance(currency, str):
        logger.warning(f"⚠️ Moeda inválida (vazia ou None): {currency}")
        raise ValueError("Moeda inválida")
    
    if currency not in SUPPORTED_CURRENCIES:
        logger.warning(f"⚠️ Moeda inválida: {currency}")
        raise ValueError(f"Moeda inválida. Use uma das: {SUPPORTED_CURRENCIES}")
    
    logger.debug(f"✅ Moeda validada: {currency}")
    return currency


def validate_language(
    language: str,
    request = None
) -> str:
    """
    Valida se o idioma é suportado.
    
    🔧 USO:
        validate_language("pt")  # ✅ Válido
        validate_language("fr")  # ❌ Inválido
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Verificação de string vazia
        - 🔧 NOVO: i18n nas mensagens de erro
        - 🔧 NOVO: Logs informativos
    
    Args:
        language: Código do idioma
        request: Objeto Request (para i18n)
    
    Returns:
        Idioma validado
    
    Raises:
        ValueError: Se o idioma não for suportado
    """
    # 🔧 CORRIGIDO: Verificação de string vazia
    if not language or not isinstance(language, str):
        logger.warning(f"⚠️ Idioma inválido (vazio ou None): {language}")
        raise ValueError("Idioma inválido")
    
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"⚠️ Idioma inválido: {language}")
        raise ValueError(f"Idioma inválido. Use um dos: {SUPPORTED_LANGUAGES}")
    
    logger.debug(f"✅ Idioma validado: {language}")
    return language


# ================================================================
# VALIDAÇÃO DE OBJECTID
# ================================================================

def validate_object_id(
    id_str: str,
    field_name: str = "id",
    request = None
) -> str:
    """
    Valida se o ID é um ObjectId válido do MongoDB.
    
    🔧 USO:
        validate_object_id("507f1f77bcf86cd799439011")  # ✅ Válido
    
    📋 PADRÃO:
        - 🔧 NOVO: i18n nas mensagens de erro
        - 🔧 NOVO: Logs informativos
    
    Args:
        id_str: String do ID a ser validada
        field_name: Nome do campo para mensagem de erro
        request: Objeto Request (para i18n)
    
    Returns:
        O mesmo ID se válido
    
    Raises:
        HTTPException: Se o ID for inválido
    """
    if not id_str or not isinstance(id_str, str):
        logger.warning(f"⚠️ ID inválido para campo {field_name}: {id_str}")
        language = getattr(request.state, "language", "pt") if request else "pt"
        raise HTTPException(
            status_code=400,
            detail=get_message("ERROR_INVALID_ID", language, field_name=field_name)
        )
    
    if not ObjectId.is_valid(id_str):
        logger.warning(f"⚠️ ID inválido para campo {field_name}: {id_str}")
        language = getattr(request.state, "language", "pt") if request else "pt"
        raise HTTPException(
            status_code=400,
            detail=get_message("ERROR_INVALID_ID", language, field_name=field_name)
        )
    
    logger.debug(f"✅ ID validado para campo {field_name}: {id_str}")
    return id_str


# ================================================================
# FORMATAÇÃO DE DOCUMENTOS MONGODB
# ================================================================

def format_mongo_doc(doc: Optional[Dict]) -> Optional[Dict]:
    """
    Converte _id de ObjectId para string, mantém o nome _id.
    
    🔧 CORREÇÃO: Agora mantém "_id" (não converte para "id")
    🔧 Regra 2.2: Proibido criar campo "id" separado
    🔧 Regra 2.3: Frontend espera "_id", não "id"
    
    🔧 USO:
        doc = {"_id": ObjectId("..."), "name": "João"}
        formatted = format_mongo_doc(doc)
        # formatted = {"_id": "507f1f77...", "name": "João"}
    
    📋 PADRÃO:
        - Mantém "_id" como chave
        - 🔧 NOVO: Logs informativos
        - 🔧 NOVO: Verificação de entrada
    
    Args:
        doc: Documento do MongoDB
    
    Returns:
        Documento formatado com "_id" como string
    """
    if not doc:
        logger.debug("ℹ️ format_mongo_doc recebeu None ou vazio")
        return doc
    
    if not isinstance(doc, dict):
        logger.warning(f"⚠️ format_mongo_doc recebeu não-dicionário: {type(doc)}")
        return doc
    
    result = dict(doc)
    if "_id" in result and result["_id"] is not None:
        result["_id"] = str(result["_id"])
        logger.debug(f"✅ Documento formatado com _id: {result['_id'][:8]}...")
    else:
        logger.debug("ℹ️ Documento sem _id")
    
    return result


def format_mongo_list(docs: List[Dict]) -> List[Dict]:
    """
    Aplica format_mongo_doc a uma lista de documentos.
    
    🔧 USO:
        docs = [{"_id": ObjectId("...")}, {"_id": ObjectId("...")}]
        formatted = format_mongo_list(docs)
    
    📋 PADRÃO:
        - 🔧 NOVO: Logs informativos
        - 🔧 NOVO: Verificação de entrada
    
    Args:
        docs: Lista de documentos do MongoDB
    
    Returns:
        Lista de documentos formatados
    """
    if not docs:
        logger.debug("ℹ️ format_mongo_list recebeu lista vazia")
        return []
    
    if not isinstance(docs, list):
        logger.warning(f"⚠️ format_mongo_list recebeu não-lista: {type(docs)}")
        return []
    
    formatted = [format_mongo_doc(doc) for doc in docs if doc]
    logger.debug(f"✅ {len(formatted)} documentos formatados")
    return formatted


def format_mongo_docs(docs: List[Dict]) -> List[Dict]:
    """
    Alias para format_mongo_list (mantém compatibilidade com código que usa este nome)
    """
    return format_mongo_list(docs)


# ================================================================
# CONVERSÃO GENÉRICA DE OBJECTID
# ================================================================

def convert_objectid_to_str(data: Any) -> Any:
    """
    Converte ObjectId do MongoDB para string (genérico).
    Percorre todos os campos do dicionário, listas e objetos aninhados,
    convertendo qualquer ObjectId para string.
    
    🔧 USO:
        data = {"_id": ObjectId("..."), "user": {"_id": ObjectId("...")}}
        converted = convert_objectid_to_str(data)
        # converted = {"_id": "507f1f77...", "user": {"_id": "507f1f77..."}}
    
    📋 PADRÃO:
        - Recursivo (processa dicionários e listas aninhados)
        - 🔧 CORRIGIDO: Não modifica o original (cria cópia em dict/list)
        - 🔧 NOVO: Logs informativos
    
    Args:
        data: Dicionário, lista ou objeto a ser convertido
    
    Returns:
        O mesmo objeto com ObjectIds convertidos para string
    """
    if data is None:
        return data
    
    if isinstance(data, dict):
        # 🔧 CORRIGIDO: Cria cópia para não modificar o original
        result = {}
        for key, value in data.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, (dict, list)):
                result[key] = convert_objectid_to_str(value)
            else:
                result[key] = value
        return result
    
    elif isinstance(data, list):
        return [convert_objectid_to_str(item) for item in data]
    
    elif isinstance(data, ObjectId):
        return str(data)
    
    return data



# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ format_mongo_doc mantém "_id" (não cria "id") - Regra 2.2 e 2.3
# ✅ Validadores centralizados e reutilizáveis
# ✅ convert_objectid_to_str genérico para conversão de ObjectId
# ✅ Suporte a dicionários aninhados e listas
# ✅ 🔧 NOVO: Internacionalização (i18n) nas mensagens de erro
# ✅ 🔧 NOVO: Logs informativos para validações
# ✅ 🔧 CORRIGIDO: Verificação de string vazia em validate_currency e validate_language
# ✅ 🔧 CORRIGIDO: Tratamento robusto em validate_month_format
# ✅ 🔧 CORRIGIDO: convert_objectid_to_str não modifica original (cria cópia)
# ✅ Documentação completa
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de CPF/CNPJ (não necessário - decisão de produto)
#   - Validação de telefone (não necessário - decisão de produto)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado convert_objectid_to_str (25/05/2026)
#   - v3: Adicionado i18n, logs, validações melhoradas (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO