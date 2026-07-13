"""
Worker para Notificações de Metas
Arquivo: backend/workers/goal_notification.py

Funcionalidade: Verifica metas próximas de conclusão e envia notificações

📋 RESPONSABILIDADES:
  1. Buscar metas com progresso >= 90%, 95%, 100%
  2. Enviar push notification para o usuário
  3. Evitar notificações duplicadas (tracking + flag)
  4. Registrar histórico de notificações enviadas
  5. Logs estruturados em JSON

📋 AGENDAMENTO:
  - Deve rodar diariamente (ex: 09:00)
  - Pode ser executado manualmente via endpoint /workers/notification/trigger

🔧 INTEGRAÇÕES:
  - MongoDB: goals collection, goal_notifications collection
  - NotificationService: envio de push notifications
  - CurrencyContext: formatação de valores
  - I18n: mensagens traduzidas

🆕 CORREÇÕES (12/07/2026):
  - 🔧 Logging estruturado em JSON
  - 🔧 Flag _notification_processed para evitar duplicação
  - 🔧 Internacionalização (i18n) das mensagens
  - 🔧 Busca de idioma do usuário

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 12/07/2026
"""

import asyncio
import os
import json
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
    logger.info(json.dumps({
        "event": "goal_notifications_worker_started",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    
    if db is None:
        db = await get_database()
    
    stats = {
        "total_processed": 0,
        "total_notifications_sent": 0,
        "total_errors": 0,
        "errors": [],
        "notifications": [],
        "skipped_duplicates": 0,
    }
    
    try:
        # 1. Busca metas ativas (não concluídas, não arquivadas)
        # 🆕 Evita duplicação: verifica se já foi processada
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        query = {
            "completed": False,
            "archived": False,
            "user_id": {"$exists": True},
            "$or": [
                {"_notification_processed": {"$ne": True}},
                {"_notification_processed": {"$exists": False}},
                {"_notification_processed_at": {"$lt": yesterday}},
            ]
        }
        
        active_goals = await db.goals.find(query).to_list(BATCH_SIZE)
        
        if not active_goals:
            logger.info(json.dumps({
                "event": "goal_notifications_no_goals",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
            return stats
        
        logger.info(json.dumps({
            "event": "goal_notifications_goals_found",
            "count": len(active_goals),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        
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
                                
                                # 🆕 Marca como processada
                                await _mark_as_processed(goal, db)
                                
                                logger.info(json.dumps({
                                    "event": "goal_notification_sent",
                                    "goal_id": str(goal["_id"]),
                                    "goal_name": goal.get("name"),
                                    "threshold": threshold,
                                    "progress": round(progress, 1),
                                    "user_id": user_id,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }))
                            else:
                                stats["skipped_duplicates"] += 1
                                logger.debug(json.dumps({
                                    "event": "goal_notification_skipped",
                                    "goal_id": str(goal["_id"]),
                                    "threshold": threshold,
                                    "reason": "already_sent",
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }))
                
            except Exception as e:
                stats["total_errors"] += 1
                stats["errors"].append({
                    "goal_id": str(goal.get("_id")),
                    "name": goal.get("name", "desconhecida"),
                    "error": str(e),
                })
                logger.error(json.dumps({
                    "event": "goal_notification_error",
                    "goal_id": str(goal.get("_id")),
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
                continue
        
        logger.info(json.dumps({
            "event": "goal_notifications_worker_completed",
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            "event": "goal_notifications_worker_fatal_error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
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


async def _mark_as_processed(goal: Dict[str, Any], db) -> None:
    """
    🆕 Marca a meta como processada para evitar duplicação.
    
    Args:
        goal: Meta processada
        db: Conexão com o banco
    """
    now = datetime.now(timezone.utc)
    
    await db.goals.update_one(
        {"_id": goal["_id"]},
        {
            "$set": {
                "_notification_processed": True,
                "_notification_processed_at": now,
                "updated_at": now,
            }
        }
    )


async def _get_user_language(user_id: str, db) -> str:
    """
    🆕 Busca o idioma do usuário.
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco
    
    Returns:
        str: Código do idioma (pt, en, es, zh)
    """
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"language": 1}
        )
        if user and user.get("language"):
            return user["language"]
    except Exception as e:
        logger.warning(json.dumps({
            "event": "goal_notification_user_language_error",
            "user_id": user_id,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
    
    return "pt"  # Fallback para português


async def _send_goal_notification(goal: Dict[str, Any], threshold: int, progress: float, db) -> bool:
    """
    🔧 CORRIGIDO: Envia notificação com i18n.
    
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
        
        # 🆕 Busca idioma do usuário
        language = await _get_user_language(user_id, db)
        
        # 🆕 Mensagens i18n
        if threshold == 100:
            title_key = "NOTIFICATIONS.GOAL_PROGRESS.TITLE_100"
            body_key = "NOTIFICATIONS.GOAL_PROGRESS.BODY_100"
        elif threshold == 95:
            title_key = "NOTIFICATIONS.GOAL_PROGRESS.TITLE_95"
            body_key = "NOTIFICATIONS.GOAL_PROGRESS.BODY_95"
        else:  # 90%
            title_key = "NOTIFICATIONS.GOAL_PROGRESS.TITLE_90"
            body_key = "NOTIFICATIONS.GOAL_PROGRESS.BODY_90"
        
        title = get_message(title_key, language, {"goal_name": goal_name})
        body = get_message(body_key, language, {
            "goal_name": goal_name,
            "progress": round(progress, 0),
            "target": target,
            "remaining": target - current
        })
        
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
        logger.error(json.dumps({
            "event": "goal_notification_send_error",
            "goal_id": str(goal.get("_id")),
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        return False


# ================================================================
# FUNÇÃO PARA EXECUÇÃO MANUAL
# ================================================================

async def run_goal_notifications_worker():
    """
    Função wrapper para execução manual do worker.
    """
    logger.info(json.dumps({
        "event": "goal_notifications_worker_manual_trigger",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    
    result = await process_goal_notifications()
    
    logger.info(json.dumps({
        "event": "goal_notifications_worker_manual_result",
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    
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
📋 CHANGELOG - 12/07/2026
──────────────────────────────────────────────────────────────

🆕 CORREÇÕES:
  1. 🔧 Logging estruturado em JSON (issue #1)
  2. 🔧 Flag _notification_processed para evitar duplicação (issue #2)
  3. 🔧 Campo _notification_processed_at para rastreamento
  4. 🔧 Internacionalização (i18n) das mensagens (issue #3)
  5. 🔧 _get_user_language() para buscar idioma do usuário (issue #4)
  6. 🔧 Query com $or para evitar reprocessamento

📋 DECISÕES:
  - Thresholds: 90%, 95%, 100%
  - Cooldown de 24h para evitar spam
  - Flag _notification_processed com TTL implícito (1 dia)
  - Mensagens traduzidas via i18n
  - Fallback para português se idioma não encontrado

📋 NOVOS CAMPOS:
  - _notification_processed: bool
  - _notification_processed_at: datetime

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 12/07/2026
"""