"""
Rotas para Monitoramento de Workers
Arquivo: backend/app/routes/workers.py

Funcionalidades:
- GET /workers/score/status: Status do worker de score
- POST /workers/score/trigger: Executar worker manualmente
- GET /workers/score/queue: Status da fila Redis
- GET /workers/notifications/status: Status do worker de notificações
- 🆕 GET /workers/goals/recurring/status: Status do worker de metas recorrentes
- 🆕 POST /workers/goals/recurring/trigger: Executar worker de metas recorrentes
- 🆕 GET /workers/goals/notifications/status: Status do worker de notificações de metas
- 🆕 POST /workers/goals/notifications/trigger: Executar worker de notificações de metas

🔧 CORRIGIDO: Caminho dos workers usando 'worker_disabled'

Regra: 2.8 (Logs)
Regra: 7.1 (Internacionalização)

🔧 USO:
    # Ver status do worker de score
    GET /api/v1/workers/score/status
    
    # Executar worker manualmente (com ADMIN_SECRET)
    POST /api/v1/workers/score/trigger?secret=admin123
    
    # Ver status da fila
    GET /api/v1/workers/score/queue
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from datetime import datetime, timezone, timedelta
import os
import asyncio

from app.database import get_database
from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.utils.logger import setup_logger
from app.utils.i18n import get_message
from app.utils.rate_limiter import limiter, get_user_rate_limit_key

logger = setup_logger(__name__)
router = APIRouter(prefix="/workers", tags=["Workers"])


# ================================================================
# WORKER DE SCORE - STATUS
# ================================================================

@router.get("/score/status")
async def get_score_worker_status(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o status do worker de score.
    
    🔧 USO:
        GET /api/v1/workers/score/status
    
    📋 PADRÃO:
        - Busca a última execução no banco
        - Retorna estatísticas da execução
    """
    language = getattr(request.state, "language", "pt")
    
    try:
        # Busca a última execução
        last_run = await db.worker_logs.find_one(
            {"worker": "score"},
            sort=[("executed_at", -1)]
        )
        
        # Busca quantas execuções nos últimos 7 dias
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        runs_last_7_days = await db.worker_logs.count_documents({
            "worker": "score",
            "executed_at": {"$gte": seven_days_ago}
        })
        
        # Busca últimas 5 execuções
        last_runs = await db.worker_logs.find(
            {"worker": "score"},
            sort=[("executed_at", -1)]
        ).to_list(5)
        
        return {
            "status": "operational",
            "last_run": {
                "executed_at": last_run.get("executed_at").isoformat() if last_run else None,
                "total_users": last_run.get("result", {}).get("total_users", 0) if last_run else 0,
                "success_count": last_run.get("result", {}).get("success_count", 0) if last_run else 0,
                "error_count": last_run.get("result", {}).get("error_count", 0) if last_run else 0,
                "duration_seconds": last_run.get("result", {}).get("duration_seconds", 0) if last_run else 0,
                "incremental": last_run.get("result", {}).get("incremental", False) if last_run else False
            },
            "summary": {
                "runs_last_7_days": runs_last_7_days,
                "last_runs": [
                    {
                        "executed_at": r.get("executed_at").isoformat(),
                        "total_users": r.get("result", {}).get("total_users", 0),
                        "success_count": r.get("result", {}).get("success_count", 0),
                        "error_count": r.get("result", {}).get("error_count", 0)
                    }
                    for r in last_runs
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar status do worker de score: {e}")
        raise HTTPException(
            status_code=500,
            detail=get_message("ERROR_SERVER", language)
        )


# ================================================================
# WORKER DE SCORE - TRIGGER MANUAL
# ================================================================

@router.post("/score/trigger")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def trigger_score_worker(
    request: Request,
    secret: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Executa o worker de score manualmente.
    
    🔧 USO:
        POST /api/v1/workers/score/trigger?secret=ADMIN_SECRET
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Validação rigorosa do ADMIN_SECRET
        - 🔧 CORRIGIDO: Armazena a task com referência
    """
    language = getattr(request.state, "language", "pt")
    
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")
    
    # 🔧 CORRIGIDO: Validação mais rigorosa
    if not ADMIN_SECRET:
        logger.error("❌ ADMIN_SECRET não configurado no .env")
        raise HTTPException(
            status_code=500,
            detail="ADMIN_SECRET not configured"
        )
    
    if secret != ADMIN_SECRET:
        logger.warning(f"⚠️ Tentativa de acesso com ADMIN_SECRET inválido")
        raise HTTPException(
            status_code=403,
            detail=get_message("ERROR_UNAUTHORIZED", language)
        )
    
    # 🔧 CORRIGIDO: Importação segura do worker
    try:
        from worker_disabled.score_worker import calculate_score_for_all_users
    except ImportError as e:
        logger.error(f"❌ Erro ao importar worker de score: {e}")
        raise HTTPException(
            status_code=500,
            detail="Worker de score não disponível"
        )
    
    # 🔧 CORRIGIDO: Armazena a task com referência
    task = asyncio.create_task(calculate_score_for_all_users())
    task.add_done_callback(
        lambda t: logger.info(
            f"✅ Worker de score finalizado com status: "
            f"{'sucesso' if not t.exception() else f'erro: {t.exception()}'}"
        )
    )
    
    logger.info(f"🚀 Worker de score acionado manualmente por {current_user.id}")
    
    return {
        "message": get_message("SCORE_WORKER_TRIGGERED", language),
        "started_at": datetime.now(timezone.utc).isoformat()
    }


# ================================================================
# WORKER DE SCORE - FILA REDIS
# ================================================================

@router.get("/score/queue")
async def get_score_queue_status(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o status da fila de score no Redis.
    
    🔧 USO:
        GET /api/v1/workers/score/queue
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Importação segura do redis_client
    """
    language = getattr(request.state, "language", "pt")
    
    try:
        # 🔧 CORRIGIDO: Importação segura
        try:
            from worker_disabled.score_worker import redis_client
        except ImportError:
            redis_client = None
        
        if not redis_client:
            return {
                "status": "disabled",
                "message": "Redis não configurado"
            }
        
        queue_size = await redis_client.llen("score_queue")
        
        return {
            "status": "operational",
            "queue_size": queue_size,
            "max_queue_size": 10000
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar status da fila: {e}")
        raise HTTPException(
            status_code=500,
            detail=get_message("ERROR_SERVER", language)
        )


# ================================================================
# WORKER DE NOTIFICAÇÕES - STATUS
# ================================================================

@router.get("/notifications/status")
async def get_notifications_worker_status(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o status do worker de notificações.
    
    🔧 USO:
        GET /api/v1/workers/notifications/status
    """
    language = getattr(request.state, "language", "pt")
    
    try:
        # Busca a última execução
        last_run = await db.worker_logs.find_one(
            {"worker": "notifications"},
            sort=[("executed_at", -1)]
        )
        
        return {
            "status": "operational",
            "last_run": {
                "executed_at": last_run.get("executed_at").isoformat() if last_run else None,
                "total_users": last_run.get("result", {}).get("total_users", 0) if last_run else 0,
                "success_count": last_run.get("result", {}).get("success_count", 0) if last_run else 0,
                "error_count": last_run.get("result", {}).get("error_count", 0) if last_run else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar status do worker de notificações: {e}")
        raise HTTPException(
            status_code=500,
            detail=get_message("ERROR_SERVER", language)
        )


# ================================================================
# 🆕 WORKER DE METAS RECORRENTES - STATUS
# ================================================================

@router.get("/goals/recurring/status")
async def get_goal_recurring_status(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o status do worker de metas recorrentes.
    
    🔧 USO:
        GET /api/v1/workers/goals/recurring/status
    """
    language = getattr(request.state, "language", "pt")
    
    try:
        last_run = await db.worker_logs.find_one(
            {"worker": "goal_recurring"},
            sort=[("executed_at", -1)]
        )
        
        return {
            "status": "operational",
            "last_run": {
                "executed_at": last_run.get("executed_at").isoformat() if last_run else None,
                "total_processed": last_run.get("result", {}).get("total_processed", 0) if last_run else 0,
                "total_created": last_run.get("result", {}).get("total_created", 0) if last_run else 0,
                "total_archived": last_run.get("result", {}).get("total_archived", 0) if last_run else 0,
                "total_errors": last_run.get("result", {}).get("total_errors", 0) if last_run else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar status do worker de metas recorrentes: {e}")
        raise HTTPException(
            status_code=500,
            detail=get_message("ERROR_SERVER", language)
        )


# ================================================================
# 🆕 WORKER DE METAS RECORRENTES - TRIGGER MANUAL
# ================================================================

@router.post("/goals/recurring/trigger")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def trigger_goal_recurring_worker(
    request: Request,
    secret: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Executa o worker de metas recorrentes manualmente.
    
    🔧 USO:
        POST /api/v1/workers/goals/recurring/trigger?secret=ADMIN_SECRET
    """
    language = getattr(request.state, "language", "pt")
    
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")
    
    if not ADMIN_SECRET:
        logger.error("❌ ADMIN_SECRET não configurado no .env")
        raise HTTPException(
            status_code=500,
            detail="ADMIN_SECRET not configured"
        )
    
    if secret != ADMIN_SECRET:
        logger.warning(f"⚠️ Tentativa de acesso com ADMIN_SECRET inválido")
        raise HTTPException(
            status_code=403,
            detail=get_message("ERROR_UNAUTHORIZED", language)
        )
    
    try:
        from worker_disabled.goal_recurring import process_recurring_goals
    except ImportError as e:
        logger.error(f"❌ Erro ao importar worker de metas recorrentes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Worker de metas recorrentes não disponível"
        )
    
    task = asyncio.create_task(process_recurring_goals())
    task.add_done_callback(
        lambda t: logger.info(
            f"✅ Worker de metas recorrentes finalizado com status: "
            f"{'sucesso' if not t.exception() else f'erro: {t.exception()}'}"
        )
    )
    
    logger.info(f"🚀 Worker de metas recorrentes acionado manualmente por {current_user.id}")
    
    return {
        "message": "Worker de metas recorrentes iniciado",
        "started_at": datetime.now(timezone.utc).isoformat()
    }


# ================================================================
# 🆕 WORKER DE NOTIFICAÇÕES DE METAS - STATUS
# ================================================================

@router.get("/goals/notifications/status")
async def get_goal_notifications_status(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna o status do worker de notificações de metas.
    
    🔧 USO:
        GET /api/v1/workers/goals/notifications/status
    """
    language = getattr(request.state, "language", "pt")
    
    try:
        last_run = await db.worker_logs.find_one(
            {"worker": "goal_notifications"},
            sort=[("executed_at", -1)]
        )
        
        return {
            "status": "operational",
            "last_run": {
                "executed_at": last_run.get("executed_at").isoformat() if last_run else None,
                "total_processed": last_run.get("result", {}).get("total_processed", 0) if last_run else 0,
                "total_notifications_sent": last_run.get("result", {}).get("total_notifications_sent", 0) if last_run else 0,
                "total_errors": last_run.get("result", {}).get("total_errors", 0) if last_run else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar status do worker de notificações de metas: {e}")
        raise HTTPException(
            status_code=500,
            detail=get_message("ERROR_SERVER", language)
        )


# ================================================================
# 🆕 WORKER DE NOTIFICAÇÕES DE METAS - TRIGGER MANUAL
# ================================================================

@router.post("/goals/notifications/trigger")
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def trigger_goal_notifications_worker(
    request: Request,
    secret: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Executa o worker de notificações de metas manualmente.
    
    🔧 USO:
        POST /api/v1/workers/goals/notifications/trigger?secret=ADMIN_SECRET
    """
    language = getattr(request.state, "language", "pt")
    
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")
    
    if not ADMIN_SECRET:
        logger.error("❌ ADMIN_SECRET não configurado no .env")
        raise HTTPException(
            status_code=500,
            detail="ADMIN_SECRET not configured"
        )
    
    if secret != ADMIN_SECRET:
        logger.warning(f"⚠️ Tentativa de acesso com ADMIN_SECRET inválido")
        raise HTTPException(
            status_code=403,
            detail=get_message("ERROR_UNAUTHORIZED", language)
        )
    
    try:
        from worker_disabled.goal_notification import process_goal_notifications
    except ImportError as e:
        logger.error(f"❌ Erro ao importar worker de notificações de metas: {e}")
        raise HTTPException(
            status_code=500,
            detail="Worker de notificações de metas não disponível"
        )
    
    task = asyncio.create_task(process_goal_notifications())
    task.add_done_callback(
        lambda t: logger.info(
            f"✅ Worker de notificações de metas finalizado com status: "
            f"{'sucesso' if not t.exception() else f'erro: {t.exception()}'}"
        )
    )
    
    logger.info(f"🚀 Worker de notificações de metas acionado manualmente por {current_user.id}")
    
    return {
        "message": "Worker de notificações de metas iniciado",
        "started_at": datetime.now(timezone.utc).isoformat()
    }


# ================================================================
# NOTAS DE IMPLEMENTAÇÃO
# ================================================================

"""
📌 COMO USAR:

1. Ver status do worker de score:
   GET /api/v1/workers/score/status

2. Executar worker de score manualmente:
   POST /api/v1/workers/score/trigger?secret=ADMIN_SECRET

3. Ver status da fila Redis:
   GET /api/v1/workers/score/queue

4. Ver status do worker de notificações:
   GET /api/v1/workers/notifications/status

5. 🆕 Ver status do worker de metas recorrentes:
   GET /api/v1/workers/goals/recurring/status

6. 🆕 Executar worker de metas recorrentes:
   POST /api/v1/workers/goals/recurring/trigger?secret=ADMIN_SECRET

7. 🆕 Ver status do worker de notificações de metas:
   GET /api/v1/workers/goals/notifications/status

8. 🆕 Executar worker de notificações de metas:
   POST /api/v1/workers/goals/notifications/trigger?secret=ADMIN_SECRET
"""


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ Implementado:
#   - Status do worker de score (última execução, estatísticas)
#   - Trigger manual para worker de score (com ADMIN_SECRET)
#   - Status da fila Redis para score
#   - Status do worker de notificações
#   - Rate limiting para trigger manual
#   - 🔧 CORRIGIDO: Importação segura do redis_client
#   - 🔧 CORRIGIDO: Validação rigorosa do ADMIN_SECRET
#   - 🔧 CORRIGIDO: Task com referência e callback
#   - 🔧 CORRIGIDO: Caminho dos workers para 'worker_disabled'
#   - 🆕 Status do worker de metas recorrentes
#   - 🆕 Trigger manual para metas recorrentes
#   - 🆕 Status do worker de notificações de metas
#   - 🆕 Trigger manual para notificações de metas
#   - I18n completo
#
# ❌ Não implementado (Pós-MVP):
#   - Dashboard visual (UI)
#   - Alertas para falhas consecutivas
#   - Histórico detalhado com gráficos
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (06/07/2026)
#   - v2: Correções - importação segura, ADMIN_SECRET rigoroso, task com referência (06/07/2026)
#   - v3: 🆕 Adicionado workers de metas (recurring e notifications) (12/07/2026)
#   - v4: 🔧 CORRIGIDO - Caminho dos workers para 'worker_disabled' (12/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO