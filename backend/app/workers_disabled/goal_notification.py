"""
Worker para Notificações de Metas
Arquivo: backend/workers/goal_notification.py

Funcionalidade: Verifica metas próximas de conclusão e envia notificações

📋 RESPONSABILIDADES:
  1. Buscar metas com progresso >= 90%, 95%, 100%
  2. Enviar push notification para o usuário
  3. Evitar notificações duplicadas (tracking)
  4. Registrar histórico de notificações enviadas

📋 AGENDAMENTO:
  - Deve rodar diariamente (ex: 09:00)
  - Pode ser executado manualmente via endpoint /workers/notification/trigger

🔧 INTEGRAÇÕES:
  - MongoDB: goals collection, goal_notifications collection
  - NotificationService: envio de push notifications
  - CurrencyContext: formatação de valores

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 CRIADO EM: 11/07/2026
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.database import get_database
from app.utils.logger import setup_logger
from app.utils.currency import from_cents
from app.utils.i18n import get_message

logger = setup_logger(__name__)

# ================================================================
# CONSTANTES
# ================================================================

NOTIFICATION_THRESHOLDS = [90, 95, 100]
BATCH_SIZE = 50
MAX_RETRIES = 3
NOTIFICATION_COOLDOWN_HOURS = 24  # Não enviar mesma notificação por 24h

# ================================================================
# FUNÇÕES PRINCIPAIS
# ================================================================

async def process_goal_notifications(db=None):
    """
    Processa notificações de metas próximas de conclusão.
    
    Returns:
        dict: Estatísticas do processamento
    """
    logger.info("🔔 Iniciando processamento de notificações de metas...")
    
    if db is None:
        db = await get_database()
    
    stats = {
        "total_processed": 0,
        "total_notifications_sent": 0,
        "total_errors": 0,
        "errors": [],
        "notifications": [],
    }
    
    try:
        # 1. Busca metas ativas (não concluídas, não arquivadas)
        query = {
            "completed": False,
            "archived": False,
            "user_id": {"$exists": True},
        }
        
        active_goals = await db.goals.find(query).to_list(BATCH_SIZE)
        
        if not active_goals:
            logger.info("ℹ️ Nenhuma meta ativa para processar")
            return stats
        
        logger.info(f"📊 Verificando {len(active_goals)} metas ativas")
        
        for goal in active_goals:
            try:
                stats["total_processed"] += 1
                
                user_id = goal.get("user_id")
                if not user_id:
                    continue
                
                target = goal.get("target", 0)
                current = goal.get("current", 0)
                
                if target <= 0:
                    continue
                
                progress = (current / target) * 100
                
                # 2. Verifica cada threshold
                for threshold in NOTIFICATION_THRESHOLDS:
                    if progress >= threshold:
                        # Verifica se já enviou notificação para este threshold
                        already_sent = await _check_notification_sent(
                            str(goal["_id"]), 
                            threshold, 
                            db
                        )
                        
                        if not already_sent:
                            # 3. Envia notificação
                            sent = await _send_goal_notification(
                                goal, 
                                threshold, 
                                progress, 
                                db
                            )
                            
                            if sent:
                                stats["total_notifications_sent"] += 1
                                stats["notifications"].append({
                                    "goal_id": str(goal["_id"]),
                                    "goal_name": goal.get("name", "desconhecida"),
                                    "threshold": threshold,
                                    "progress": round(progress, 1),
                                })
                                
                                # 4. Registra notificação enviada
                                await _record_notification_sent(
                                    str(goal["_id"]),
                                    threshold,
                                    user_id,
                                    db
                                )
                                
                                logger.info(f"✅ Notificação enviada: '{goal['name']}' - {threshold}%")
                
            except Exception as e:
                stats["total_errors"] += 1
                stats["errors"].append({
                    "goal_id": str(goal.get("_id")),
                    "name": goal.get("name", "desconhecida"),
                    "error": str(e),
                })
                logger.error(f"❌ Erro ao processar meta {goal.get('_id')}: {e}")
                continue
        
        logger.info(f"✅ Processamento concluído: {stats['total_notifications_sent']} notificações enviadas, {stats['total_errors']} erros")
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de notificações: {e}")
        stats["total_errors"] += 1
    
    return stats


async def _check_notification_sent(goal_id: str, threshold: int, db) -> bool:
    """
    Verifica se já foi enviada notificação para este threshold.
    
    Args:
        goal_id: ID da meta
        threshold: Threshold (90, 95, 100)
        db: Conexão com o banco
    
    Returns:
        bool: True se já foi enviada
    """
    cooldown_time = datetime.now(timezone.utc) - timedelta(hours=NOTIFICATION_COOLDOWN_HOURS)
    
    existing = await db.goal_notifications.find_one({
        "goal_id": goal_id,
        "threshold": threshold,
        "sent_at": {"$gte": cooldown_time},
    })
    
    return existing is not None


async def _record_notification_sent(goal_id: str, threshold: int, user_id: str, db) -> None:
    """
    Registra que uma notificação foi enviada.
    
    Args:
        goal_id: ID da meta
        threshold: Threshold (90, 95, 100)
        user_id: ID do usuário
        db: Conexão com o banco
    """
    now = datetime.now(timezone.utc)
    
    await db.goal_notifications.insert_one({
        "goal_id": goal_id,
        "user_id": user_id,
        "threshold": threshold,
        "sent_at": now,
        "created_at": now,
    })


async def _send_goal_notification(goal: Dict[str, Any], threshold: int, progress: float, db) -> bool:
    """
    Envia notificação para o usuário.
    
    Args:
        goal: Meta
        threshold: Threshold (90, 95, 100)
        progress: Progresso atual (%)
        db: Conexão com o banco
    
    Returns:
        bool: True se enviado com sucesso
    """
    try:
        from app.services.notification_service import NotificationService
        
        user_id = goal["user_id"]
        goal_name = goal["name"]
        target = from_cents(goal.get("target", 0))
        current = from_cents(goal.get("current", 0))
        
        # Define título e mensagem baseado no threshold
        if threshold == 100:
            title = f"🎉 Meta concluída: {goal_name}!"
            body = f"Parabéns! Você atingiu sua meta de R$ {target:.2f}! Continue assim! 🚀"
        elif threshold == 95:
            title = f"🔥 Quase lá! {goal_name} está em {progress:.0f}%"
            body = f"Você está muito perto de atingir sua meta de R$ {target:.2f}! Falta apenas R$ {(target - current):.2f} para concluir! 💪"
        else:  # 90%
            title = f"💪 Meta: {goal_name} está em {progress:.0f}%"
            body = f"Você já atingiu {progress:.0f}% da sua meta de R$ {target:.2f}! Continue firme! 🚀"
        
        notification_service = NotificationService()
        
        await notification_service.send_push_notification(
            user_id,
            title=title,
            body=body,
            data={
                "type": "goal_progress",
                "goal_id": str(goal["_id"]),
                "threshold": threshold,
                "progress": progress,
                "screen": "Goals",
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificação: {e}")
        return False


# ================================================================
# FUNÇÃO PARA EXECUÇÃO MANUAL
# ================================================================

async def run_goal_notifications_worker():
    """
    Função wrapper para execução manual do worker.
    """
    logger.info("🚀 Executando worker de notificações de metas (manual)...")
    result = await process_goal_notifications()
    logger.info(f"📊 Resultado: {result}")
    return result


# ================================================================
# MAIN (PARA EXECUÇÃO DIRETA)
# ================================================================

if __name__ == "__main__":
    asyncio.run(run_goal_notifications_worker())


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================

"""
📋 CHANGELOG - 11/07/2026
──────────────────────────────────────────────────────────────

🆕 CRIADO:
  1. process_goal_notifications() - Função principal
  2. _check_notification_sent() - Verifica notificações duplicadas
  3. _record_notification_sent() - Registra histórico
  4. _send_goal_notification() - Envia notificação
  5. run_goal_notifications_worker() - Execução manual
  6. NOTIFICATION_THRESHOLDS = [90, 95, 100]
  7. NOTIFICATION_COOLDOWN_HOURS = 24
  8. BATCH_SIZE = 50
  9. Documentação completa

📋 DECISÕES:
  - Thresholds: 90%, 95%, 100%
  - Cooldown de 24h para evitar spam
  - Mensagens personalizadas por threshold
  - Histórico de notificações enviadas
  - Fallback silencioso em caso de erro

📋 MENSAGENS:
  - 90%: "Você já atingiu X% da sua meta..."
  - 95%: "Você está muito perto de atingir..."
  - 100%: "Parabéns! Você atingiu sua meta!"

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 11/07/2026
"""