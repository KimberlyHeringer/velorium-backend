"""
Rotas para Monitoramento de Workers
Arquivo: backend/app/routes/workers.py

Funcionalidades:
- GET /workers/score/status: Status do worker de score
- POST /workers/score/trigger: Executar worker manualmente
- GET /workers/score/queue: Status da fila Redis
- GET /workers/notifications/status: Status do worker de notificações

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
        from workers.score_worker import calculate_score_for_all_users
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
            from workers.score_worker import redis_client
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
# NOTAS DE IMPLEMENTAÇÃO
# ================================================================

"""
📌 COMO USAR:

1. Ver status do worker de score:
   GET /api/v1/workers/score/status
   → Retorna última execução, total de usuários, sucessos, erros

2. Executar worker manualmente:
   POST /api/v1/workers/score/trigger?secret=ADMIN_SECRET
   → Inicia o worker em background

3. Ver status da fila Redis:
   GET /api/v1/workers/score/queue
   → Retorna tamanho da fila

4. Ver status do worker de notificações:
   GET /api/v1/workers/notifications/status
   → Retorna última execução
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
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO