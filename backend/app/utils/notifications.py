"""
Funções de Notificações Push
Arquivo: backend/app/utils/notifications.py

Funcionalidades:
- send_push_notification(): Envia notificação via Expo para um único token
- send_bulk_notifications(): Envia notificações em lote para múltiplos tokens

Principais features:
- 🔧 CORRIGIDO: Documentação completa
- 🔧 CORRIGIDO: Validação do token (formato e vazio)
- 🔧 CORRIGIDO: Validação de título e corpo
- 🔧 CORRIGIDO: Validação de EXPO_API_URL
- 🔧 CORRIGIDO: i18n nas mensagens de log
- 🔧 CORRIGIDO: Timeout configurável via .env
- 🔧 CORRIGIDO: Tratamento de erro específico do Expo
- 🔧 CORRIGIDO: tokens pode ser None
- 🔧 CORRIGIDO: zip com tamanhos diferentes em bulk
- 🔧 CORRIGIDO: Logs estruturados
- 🆕 NOVO: send_bulk_notifications() para envio em lote
- ✅ Suporte a Expo Push Notification
- ✅ Retorno booleano para indicar sucesso
- ✅ Suporte a dados adicionais para navegação
- ✅ Uso de httpx.AsyncClient (assíncrono)

🔧 USO:
    from app.utils.notifications import send_push_notification, send_bulk_notifications
    
    # Único token
    success = await send_push_notification(
        token="ExponentPushToken[...]",
        title="Título",
        body="Corpo da notificação",
        data={"screen": "Dashboard"}
    )
    
    # Múltiplos tokens
    results = await send_bulk_notifications(
        tokens=["ExponentPushToken[...]", "ExponentPushToken[...]"],
        title="Título",
        body="Corpo da notificação",
        data={"screen": "Dashboard"}
    )
"""

import os
from typing import Optional, Dict, List
import httpx

from app.core.constants import EXPO_API_URL
from app.utils.logger import setup_logger
from app.utils.i18n import get_message

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# ========== CONFIGURAÇÕES ==========
NOTIFICATION_TIMEOUT = int(os.getenv("NOTIFICATION_TIMEOUT", 30))


async def send_push_notification(token: str, title: str, body: str, data: Optional[Dict] = None) -> bool:
    """
    Envia uma notificação push via Expo para um único token.
    
    🔧 CARACTERÍSTICAS:
    - 🔧 Validação de token (formato e vazio)
    - 🔧 Validação de título e corpo
    - 🔧 Validação de EXPO_API_URL
    - 🔧 i18n nas mensagens de log
    - 🔧 Timeout configurável via .env
    - 🔧 Tratamento de erro específico do Expo
    - Logs estruturados
    
    Args:
        token: Expo push token do dispositivo
        title: Título da notificação
        body: Corpo da notificação
        data: Dados adicionais para navegação (opcional)
    
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    
    Exemplo:
        success = await send_push_notification(
            token="ExponentPushToken[...]",
            title="💡 Veloria | Insight do Dia",
            body="Seu score financeiro subiu 5 pontos!",
            data={"screen": "Dashboard"}
        )
    """
    language = "pt"  # 🔧 FUTURO: Detectar idioma do usuário
    
    # 🔧 CORRIGIDO: Validação do token
    if not token:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_EMPTY_TOKEN', language)}")
        return False
    
    if not token.startswith("ExponentPushToken["):
        logger.warning(f"⚠️ {get_message('NOTIFICATION_INVALID_TOKEN', language)}: {token[:20]}...")
        return False
    
    # 🔧 CORRIGIDO: Validação de título e corpo
    if not title:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_EMPTY_TITLE', language)}")
        return False
    
    if not body:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_EMPTY_BODY', language)}")
        return False
    
    # 🔧 CORRIGIDO: Validação da URL
    if not EXPO_API_URL:
        logger.error(f"❌ {get_message('NOTIFICATION_EXPO_URL_MISSING', language)}")
        return False
    
    try:
        message = {
            "to": token,
            "title": title,
            "body": body,
            "sound": "default",
            "priority": "normal",
        }
        if data:
            message["data"] = data
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                EXPO_API_URL,
                json=message,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "Content-Type": "application/json",
                },
                timeout=NOTIFICATION_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("data", {}).get("status") == "error":
                    error_msg = result.get("data", {}).get("message", "")
                    # 🔧 CORRIGIDO: Tratamento específico
                    if "ExponentPushToken" in error_msg and "invalid" in error_msg:
                        logger.warning(f"⚠️ {get_message('NOTIFICATION_INVALID_TOKEN', language)}: {token[:20]}...")
                    else:
                        logger.warning(f"⚠️ {get_message('NOTIFICATION_EXPO_ERROR', language)}: {error_msg}")
                    return False
                logger.debug(f"✅ Notificação enviada para token {token[:20]}...")
                return True
            else:
                logger.error(f"❌ {get_message('NOTIFICATION_SEND_ERROR', language)}: {response.status_code} - {response.text}")
                return False
    except httpx.TimeoutException:
        logger.error(f"❌ {get_message('NOTIFICATION_TIMEOUT', language)}: {token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"❌ {get_message('NOTIFICATION_SEND_ERROR', language)}: {e}")
        return False


async def send_bulk_notifications(
    tokens: Optional[List[str]] = None,
    title: str = "",
    body: str = "",
    data: Optional[Dict] = None,
    max_tokens_per_request: int = 100
) -> Dict[str, bool]:
    """
    🆕 NOVO: Envia notificações em lote para múltiplos tokens.
    
    🔧 CARACTERÍSTICAS:
    - 🔧 tokens pode ser None
    - 🔧 Validação de tokens vazios
    - 🔧 Processa em lotes (Expo limita a 100)
    - 🔧 Garante que todos os tokens sejam processados
    - 🔧 i18n nas mensagens de log
    
    Args:
        tokens: Lista de Expo push tokens (pode ser None)
        title: Título da notificação
        body: Corpo da notificação
        data: Dados adicionais para navegação (opcional)
        max_tokens_per_request: Número máximo de tokens por requisição (Expo limita a 100)
    
    Returns:
        Dict[str, bool]: Dicionário com token -> sucesso/fracasso
    
    Exemplo:
        results = await send_bulk_notifications(
            tokens=["ExponentPushToken[...]", "ExponentPushToken[...]"],
            title="💡 Veloria | Insight do Dia",
            body="Seu score financeiro subiu 5 pontos!",
            data={"screen": "Dashboard"}
        )
    """
    language = "pt"  # 🔧 FUTURO: Detectar idioma do usuário
    results = {}
    
    # 🔧 CORRIGIDO: Verifica se tokens é None
    if tokens is None:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_EMPTY_TOKEN_LIST', language)}")
        return results
    
    if not tokens:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_EMPTY_TOKEN_LIST', language)}")
        return results
    
    if not title:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_EMPTY_TITLE', language)}")
        return results
    
    if not body:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_EMPTY_BODY', language)}")
        return results
    
    # 🔧 CORRIGIDO: Validação da URL
    if not EXPO_API_URL:
        logger.error(f"❌ {get_message('NOTIFICATION_EXPO_URL_MISSING', language)}")
        return {token: False for token in tokens}
    
    # 🔧 Filtra tokens válidos
    valid_tokens = []
    for token in tokens:
        if token and token.startswith("ExponentPushToken["):
            valid_tokens.append(token)
        else:
            results[token] = False
            logger.warning(f"⚠️ {get_message('NOTIFICATION_INVALID_TOKEN', language)}: {token[:20] if token else 'None'}...")
    
    if not valid_tokens:
        logger.warning(f"⚠️ {get_message('NOTIFICATION_NO_VALID_TOKENS', language)}")
        return results
    
    # 🔧 Envia em lotes
    for i in range(0, len(valid_tokens), max_tokens_per_request):
        batch = valid_tokens[i:i + max_tokens_per_request]
        try:
            message = {
                "to": batch,
                "title": title,
                "body": body,
                "sound": "default",
                "priority": "normal",
            }
            if data:
                message["data"] = data
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    EXPO_API_URL,
                    json=message,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip, deflate",
                        "Content-Type": "application/json",
                    },
                    timeout=NOTIFICATION_TIMEOUT
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ticket_ids = result.get("data", [])
                    # 🔧 CORRIGIDO: Garante que todos os tokens sejam processados
                    for j, token in enumerate(batch):
                        if j < len(ticket_ids):
                            ticket = ticket_ids[j]
                            if ticket.get("status") == "error":
                                error_msg = ticket.get("message", "")
                                logger.warning(f"⚠️ {get_message('NOTIFICATION_EXPO_ERROR', language)}: {error_msg}")
                                results[token] = False
                            else:
                                results[token] = True
                                logger.debug(f"✅ Notificação enviada para token {token[:20]}...")
                        else:
                            results[token] = False
                            logger.warning(f"⚠️ {get_message('NOTIFICATION_NO_TICKET', language)}: {token[:20]}...")
                else:
                    for token in batch:
                        results[token] = False
                    logger.error(f"❌ {get_message('NOTIFICATION_BULK_ERROR', language)}: {response.status_code}")
        except httpx.TimeoutException:
            for token in batch:
                results[token] = False
            logger.error(f"❌ {get_message('NOTIFICATION_TIMEOUT', language)}")
        except Exception as e:
            for token in batch:
                results[token] = False
            logger.error(f"❌ {get_message('NOTIFICATION_SEND_ERROR', language)}: {e}")
    
    success_count = sum(1 for v in results.values() if v)
    logger.info(f"📊 Notificações enviadas: {success_count}/{len(results)} com sucesso")
    return results


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - send_push_notification(): Envio para único token
#   - 🆕 send_bulk_notifications(): Envio em lote
#   - 🔧 Validação de token (formato e vazio)
#   - 🔧 Validação de título e corpo
#   - 🔧 Validação de EXPO_API_URL
#   - 🔧 tokens pode ser None
#   - 🔧 zip com tamanhos diferentes
#   - 🔧 i18n nas mensagens de log
#   - 🔧 Timeout configurável via .env
#   - 🔧 Tratamento de erro específico do Expo
#   - 🔧 Logs estruturados
#   - ✅ Suporte a Expo Push Notification
#   - ✅ Retorno booleano para indicar sucesso
#   - ✅ Suporte a dados adicionais para navegação
#   - ✅ Uso de httpx.AsyncClient (assíncrono)
#
# ❌ Não implementado (Pós-MVP):
#   - Fila de processamento para notificações em background
#   - Retry automático para notificações falhas
#   - Tracking de abertura de notificações
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração com i18n, validações, bulk, timeout (05/07/2026)
#   - v3: Correções - tokens None, EXPO_API_URL, zip fix (05/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO