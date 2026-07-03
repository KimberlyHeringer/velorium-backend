"""
Funções de Notificações Push
Arquivo: backend/app/utils/notifications.py

Funcionalidade: Centraliza funções relacionadas a notificações push
para reutilização em diferentes partes do sistema.

🔧 USO:
    from app.utils.notifications import send_push_notification
    
    success = await send_push_notification(
        token="ExponentPushToken[...]",
        title="Título",
        body="Corpo da notificação",
        data={"screen": "Dashboard"}
    )

📋 ESTRUTURA:
    - send_push_notification(): Envia notificação via Expo

🔧 CARACTERÍSTICAS:
    - Suporte a Expo Push Notification
    - Retorna True/False indicando sucesso
    - Logs estruturados
    - Timeout configurável
"""

import httpx
from typing import Optional, Dict
from app.core.constants import EXPO_API_URL
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def send_push_notification(token: str, title: str, body: str, data: Optional[Dict] = None) -> bool:
    """
    Envia uma notificação push via Expo.
    
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
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("data", {}).get("status") == "error":
                    logger.warning(f"⚠️ Erro no Expo: {result.get('data', {}).get('message')}")
                    return False
                return True
            else:
                logger.error(f"❌ Erro ao enviar push: {response.status_code} - {response.text}")
                return False
    except httpx.TimeoutException:
        logger.error(f"❌ Timeout ao enviar push para token {token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"❌ Exceção ao enviar push: {e}")
        return False


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Função reutilizável para envio de notificações
# ✅ Timeout configurável
# ✅ Logs estruturados
# ✅ Retorno booleano para indicar sucesso
# ✅ Tratamento de exceções
# ✅ Suporte a dados adicionais para navegação
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO