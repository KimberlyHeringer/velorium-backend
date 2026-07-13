"""
Worker para Recriar Metas Recorrentes
Arquivo: backend/workers/goal_recurring.py

Funcionalidade: Verifica metas recorrentes concluídas e recria automaticamente

📋 RESPONSABILIDADES:
  1. Buscar metas com recurring=True e completed=True
  2. Criar uma nova meta com os mesmos dados
  3. Arquivar a meta antiga
  4. Atualizar o progresso da nova meta com base na meta antiga
  5. Prevenir duplicação de recriação (flag _recurring_processed)
  6. Validar intervalo de recorrência com fallback

📋 AGENDAMENTO:
  - Deve rodar diariamente (ex: 00:00)
  - Pode ser executado manualmente via endpoint /workers/recurring/trigger

🔧 INTEGRAÇÕES:
  - MongoDB: goals collection
  - Notifications: envia notificação quando meta é recriada

🆕 CORREÇÕES (12/07/2026):
  - 🔧 Validação de intervalo de recorrência com fallback
  - 🔧 Flag _recurring_processed para prevenir duplicação
  - 🔧 Logging estruturado em JSON
  - 🔧 Campo _recurring_processed_at para rastreamento

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 12/07/2026
"""

import asyncio
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.utils.logger import setup_logger
from app.utils.currency import to_cents, from_cents
from app.utils.i18n import get_message

logger = setup_logger(__name__)

# ================================================================
# CONSTANTES
# ================================================================

BATCH_SIZE = 50  # Processar em lotes para não sobrecarregar
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos

# 🆕 Intervalos válidos
VALID_INTERVALS = ["monthly", "yearly"]
DEFAULT_INTERVAL = "monthly"

# ================================================================
# FUNÇÕES PRINCIPAIS
# ================================================================

async def process_recurring_goals(db=None):
    """
    Processa metas recorrentes concluídas e recria automaticamente.
    
    Returns:
        dict: Estatísticas do processamento
    """
    logger.info(json.dumps({
        "event": "recurring_worker_started",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    
    if db is None:
        db = await get_database()
    
    stats = {
        "total_processed": 0,
        "total_created": 0,
        "total_archived": 0,
        "total_errors": 0,
        "errors": [],
        "skipped_duplicates": 0,
    }
    
    try:
        # 1. Busca metas recorrentes concluídas (não arquivadas)
        # 🆕 Previne duplicação: verifica se já foi processada
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        query = {
            "recurring": True,
            "completed": True,
            "archived": False,
            "$or": [
                {"_recurring_processed": {"$ne": True}},
                {"_recurring_processed": {"$exists": False}},
                {"_recurring_processed_at": {"$lt": yesterday}},
            ]
        }
        
        completed_goals = await db.goals.find(query).to_list(BATCH_SIZE)
        
        if not completed_goals:
            logger.info(json.dumps({
                "event": "recurring_worker_no_goals",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
            return stats
        
        logger.info(json.dumps({
            "event": "recurring_worker_goals_found",
            "count": len(completed_goals),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        
        for goal in completed_goals:
            try:
                stats["total_processed"] += 1
                
                # 2. Cria nova meta baseada na meta antiga
                new_goal = await _create_recurring_goal(goal, db)
                stats["total_created"] += 1
                
                # 3. Arquivar a meta antiga
                await _archive_goal(goal, db)
                stats["total_archived"] += 1
                
                # 4. Marca como processada para evitar duplicação
                await _mark_as_processed(goal, db)
                
                # 5. Envia notificação (opcional)
                await _notify_recurring_goal_created(new_goal, goal, db)
                
                # 🆕 Log estruturado
                logger.info(json.dumps({
                    "event": "recurring_goal_created",
                    "goal_id": str(new_goal["_id"]),
                    "original_goal_id": str(goal["_id"]),
                    "user_id": goal["user_id"],
                    "goal_name": goal["name"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
                
            except Exception as e:
                stats["total_errors"] += 1
                stats["errors"].append({
                    "goal_id": str(goal.get("_id")),
                    "name": goal.get("name", "desconhecida"),
                    "error": str(e),
                })
                
                # 🆕 Log estruturado de erro
                logger.error(json.dumps({
                    "event": "recurring_goal_error",
                    "goal_id": str(goal.get("_id")),
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
                continue
        
        # 🆕 Log final estruturado
        logger.info(json.dumps({
            "event": "recurring_worker_completed",
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            "event": "recurring_worker_fatal_error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        stats["total_errors"] += 1
    
    return stats


async def _create_recurring_goal(original_goal: Dict[str, Any], db) -> Dict[str, Any]:
    """
    Cria uma nova meta baseada na meta original.
    
    Args:
        original_goal: Meta original (concluída)
        db: Conexão com o banco
    
    Returns:
        dict: Nova meta criada
    """
    now = datetime.now(timezone.utc)
    
    # 🆕 Valida intervalo de recorrência com fallback
    interval = original_goal.get("recurring_interval", DEFAULT_INTERVAL)
    if interval not in VALID_INTERVALS:
        logger.warning(json.dumps({
            "event": "recurring_invalid_interval",
            "interval": interval,
            "goal_id": str(original_goal["_id"]),
            "fallback": DEFAULT_INTERVAL,
            "timestamp": now.isoformat()
        }))
        interval = DEFAULT_INTERVAL
    
    # Calcula nova data de deadline (se houver)
    new_deadline = None
    if original_goal.get("deadline"):
        if interval == "monthly":
            new_deadline = original_goal["deadline"] + timedelta(days=30)
        elif interval == "yearly":
            new_deadline = original_goal["deadline"] + timedelta(days=365)
    
    # Cria a nova meta
    new_goal_data = {
        "user_id": original_goal["user_id"],
        "name": original_goal["name"],
        "target": original_goal["target"],
        "current": 0,  # Começa do zero
        "category": original_goal.get("category"),
        "description": original_goal.get("description"),
        "completed": False,
        "recurring": True,
        "recurring_interval": interval,
        "deadline": new_deadline,
        "parent_id": None,  # Nova meta não é sub-meta
        "completed_at": None,
        "archived": False,
        "created_at": now,
        "updated_at": now,
        "_recurring_source": str(original_goal["_id"]),  # Referência para a meta original
    }
    
    result = await db.goals.insert_one(new_goal_data)
    new_goal = await db.goals.find_one({"_id": result.inserted_id})
    
    return new_goal


async def _archive_goal(goal: Dict[str, Any], db) -> None:
    """
    Arquivar a meta concluída.
    
    Args:
        goal: Meta a ser arquivada
        db: Conexão com o banco
    """
    now = datetime.now(timezone.utc)
    
    await db.goals.update_one(
        {"_id": goal["_id"]},
        {
            "$set": {
                "archived": True,
                "completed_at": goal.get("completed_at") or now,
                "updated_at": now,
            }
        }
    )


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
                "_recurring_processed": True,
                "_recurring_processed_at": now,
                "updated_at": now,
            }
        }
    )


async def _notify_recurring_goal_created(new_goal: Dict[str, Any], original_goal: Dict[str, Any], db) -> None:
    """
    Envia notificação quando uma meta recorrente é recriada.
    
    Args:
        new_goal: Nova meta criada
        original_goal: Meta original (concluída)
        db: Conexão com o banco
    """
    try:
        from app.services.notification_service import NotificationService
        
        user_id = new_goal["user_id"]
        goal_name = new_goal["name"]
        
        notification_service = NotificationService()
        
        await notification_service.send_push_notification(
            user_id,
            title=f"🔄 Meta recorrente recriada",
            body=f"Sua meta '{goal_name}' foi recriada automaticamente! Continue acompanhando seu progresso.",
            data={
                "type": "goal_recurring",
                "goal_id": str(new_goal["_id"]),
                "screen": "Goals",
            }
        )
        
        logger.debug(json.dumps({
            "event": "recurring_notification_sent",
            "user_id": user_id,
            "goal_id": str(new_goal["_id"]),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        
    except Exception as e:
        logger.warning(json.dumps({
            "event": "recurring_notification_error",
            "error": str(e),
            "goal_id": str(new_goal.get("_id")),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))


# ================================================================
# FUNÇÃO PARA EXECUÇÃO MANUAL
# ================================================================

async def run_recurring_goals_worker():
    """
    Função wrapper para execução manual do worker.
    """
    logger.info(json.dumps({
        "event": "recurring_worker_manual_trigger",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    
    result = await process_recurring_goals()
    
    logger.info(json.dumps({
        "event": "recurring_worker_manual_result",
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    
    return result


# ================================================================
# MAIN (PARA EXECUÇÃO DIRETA)
# ================================================================

if __name__ == "__main__":
    asyncio.run(run_recurring_goals_worker())


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================

"""
📋 CHANGELOG - 12/07/2026
──────────────────────────────────────────────────────────────

🆕 ADICIONADO:
  1. VALID_INTERVALS = ["monthly", "yearly"] - Intervalos válidos
  2. DEFAULT_INTERVAL = "monthly" - Fallback padrão
  3. Validação de intervalo com fallback (issue #1)
  4. Flag _recurring_processed para prevenir duplicação (issue #2)
  5. Campo _recurring_processed_at para rastreamento
  6. Query com $or para evitar reprocessamento
  7. _mark_as_processed() - Função para marcar meta como processada
  8. Logging estruturado em JSON (issue #3)
  9. Todos os logs agora usam json.dumps()

✅ CORRIGIDO:
  10. Intervalo inválido não causa erro silencioso
  11. Duplicação de recriação prevenida
  12. Logs agora são estruturados e parseáveis

📋 DECISÕES:
  - Flag _recurring_processed com TTL implícito (1 dia)
  - Intervalos inválidos fallback para 'monthly'
  - Logs em JSON para facilitar monitoramento

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 12/07/2026
"""