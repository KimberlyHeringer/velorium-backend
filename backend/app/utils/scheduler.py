"""
Configuração do Scheduler para Workers
Arquivo: backend/app/utils/scheduler.py

Funcionalidades:
- Agendamento de workers diários (score e notificações)
- Importação segura dos workers com fallback
- Verificação de ambiente (não roda workers em desenvolvimento)
- Internacionalização (i18n) nos logs
- Funções para monitoramento do scheduler

🔧 CORRIGIDO:
- Adicionado tratamento seguro para importação dos workers
- Adicionado fallback quando workers não estão disponíveis
- Adicionada verificação de ambiente (não roda workers em desenvolvimento)
- Melhorado logging
- 🔧 NOVO: Internacionalização (i18n) nos logs
- 🔧 NOVO: Função get_scheduler_status() para monitoramento

🔧 REGRA 3.1: Score Financeiro - Worker Diário (03:00)
🔧 REGRA 4.1: Notificações Proativas - Worker Diário (09:00)

📌 PENDÊNCIAS (PÓS-MVP):
- Dashboard de monitoramento dos workers
- Alertas quando worker falha consecutivamente
- Persistência de jobs (para não perder agendamentos ao reiniciar)
- Health check dos workers
- Métricas de execução (tempo médio, taxa de sucesso)
- Fila para notificações (Redis Queue)
- Retry automático para notificações falhas
- Worker incremental (apenas usuários com mudanças)
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
import os
from datetime import datetime

from app.utils.logger import setup_logger
from app.utils.i18n import get_message

logger = setup_logger(__name__)

# Scheduler global
_scheduler = None

# Verifica se está em produção (workers só rodam em produção)
PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def _safe_import_workers():
    """
    Importa os workers de forma segura.
    Se não estiverem disponíveis, retorna None.
    """
    run_score_worker = None
    run_notifications_worker = None
    
    # Tenta importar worker de score
    try:
        from app.workers.score_worker import run_score_worker_sync
        run_score_worker = run_score_worker_sync
        # 🔧 NOVO: i18n no log
        logger.info(get_message("SCHEDULER_WORKER_SCORE_LOADED", "pt"))
    except ImportError as e:
        logger.warning(get_message("SCHEDULER_WORKER_SCORE_NOT_AVAILABLE", "pt", error=str(e)))
    except Exception as e:
        logger.error(get_message("SCHEDULER_WORKER_SCORE_ERROR", "pt", error=str(e)))
    
    # Tenta importar worker de notificações
    try:
        from app.workers.daily_notifications import run_daily_notifications_sync
        run_notifications_worker = run_daily_notifications_sync
        # 🔧 NOVO: i18n no log
        logger.info(get_message("SCHEDULER_WORKER_NOTIFICATIONS_LOADED", "pt"))
    except ImportError as e:
        logger.warning(get_message("SCHEDULER_WORKER_NOTIFICATIONS_NOT_AVAILABLE", "pt", error=str(e)))
    except Exception as e:
        logger.error(get_message("SCHEDULER_WORKER_NOTIFICATIONS_ERROR", "pt", error=str(e)))
    
    return run_score_worker, run_notifications_worker


def init_scheduler():
    """
    Inicializa o scheduler com todos os workers.
    Em desenvolvimento, os workers não são agendados (apenas em produção).
    """
    global _scheduler
    
    if _scheduler is not None:
        logger.warning(get_message("SCHEDULER_ALREADY_INITIALIZED", "pt"))
        return _scheduler
    
    # Verifica se deve rodar workers
    if not PRODUCTION:
        # 🔧 NOVO: i18n no log
        logger.info(get_message("SCHEDULER_DEV_MODE", "pt"))
        logger.info("   Para testar workers, use os endpoints manuais (/notifications/trigger-daily)")
        return None
    
    # Importa workers de forma segura
    run_score_worker, run_notifications_worker = _safe_import_workers()
    
    # Verifica se pelo menos um worker está disponível
    if not run_score_worker and not run_notifications_worker:
        logger.error(get_message("SCHEDULER_NO_WORKERS", "pt"))
        return None
    
    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    
    # Agenda worker de score (03:00)
    if run_score_worker:
        _scheduler.add_job(
            func=run_score_worker,
            trigger=CronTrigger(hour=3, minute=0),
            id="score_daily_worker",
            replace_existing=True,
            misfire_grace_time=3600  # 1 hora de tolerância
        )
        logger.info(get_message("SCHEDULER_SCORE_SCHEDULED", "pt"))
    else:
        logger.warning(get_message("SCHEDULER_SCORE_NOT_SCHEDULED", "pt"))
    
    # Agenda worker de notificações proativas (09:00)
    if run_notifications_worker:
        _scheduler.add_job(
            func=run_notifications_worker,
            trigger=CronTrigger(hour=9, minute=0),
            id="daily_notifications_worker",
            replace_existing=True,
            misfire_grace_time=1800  # 30 minutos de tolerância
        )
        logger.info(get_message("SCHEDULER_NOTIFICATIONS_SCHEDULED", "pt"))
    else:
        logger.warning(get_message("SCHEDULER_NOTIFICATIONS_NOT_SCHEDULED", "pt"))
    
    # Só inicia o scheduler se pelo menos um worker foi agendado
    if _scheduler.get_jobs():
        _scheduler.start()
        logger.info(get_message("SCHEDULER_STARTED", "pt"))
        
        # Garante que o scheduler será desligado ao final do processo
        atexit.register(lambda: shutdown_scheduler())
    else:
        logger.warning(get_message("SCHEDULER_NO_JOBS", "pt"))
        _scheduler = None
    
    return _scheduler


def shutdown_scheduler():
    """
    Desliga o scheduler de forma segura
    """
    global _scheduler
    if _scheduler:
        try:
            _scheduler.shutdown()
            logger.info(get_message("SCHEDULER_SHUTDOWN", "pt"))
        except Exception as e:
            logger.error(get_message("SCHEDULER_SHUTDOWN_ERROR", "pt", error=str(e)))
        finally:
            _scheduler = None


def get_scheduler():
    """
    Retorna a instância do scheduler
    """
    return _scheduler


def is_scheduler_running() -> bool:
    """
    Verifica se o scheduler está rodando
    """
    return _scheduler is not None and _scheduler.running


# ============================================================
# 🔧 NOVO: FUNÇÃO DE STATUS PARA MONITORAMENTO
# ============================================================

def get_scheduler_status() -> dict:
    """
    🔧 NOVO: Retorna o status atual do scheduler para monitoramento.
    
    🔧 USO:
        status = get_scheduler_status()
        print(status["running"])  # True/False
        print(status["jobs"])     # Lista de jobs agendados
    
    Returns:
        dict: Status do scheduler com jobs e informações
    """
    if not _scheduler:
        return {
            "running": False,
            "jobs": [],
            "message": "Scheduler não inicializado"
        }
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    
    return {
        "running": _scheduler.running,
        "jobs": jobs,
        "job_count": len(jobs),
        "message": "Scheduler rodando" if _scheduler.running else "Scheduler parado"
    }


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Inicializar o scheduler (no startup do app):
   from app.utils.scheduler import init_scheduler
   scheduler = init_scheduler()

2. Verificar se o scheduler está rodando:
   from app.utils.scheduler import is_scheduler_running
   if is_scheduler_running():
       print("Scheduler ativo")

3. Obter status para monitoramento:
   from app.utils.scheduler import get_scheduler_status
   status = get_scheduler_status()
   print(status["jobs"])

4. Desligar o scheduler (no shutdown):
   from app.utils.scheduler import shutdown_scheduler
   shutdown_scheduler()

5. Executar workers manualmente (para testes):
   # Score worker
   from app.workers.score_worker import run_score_worker_sync
   run_score_worker_sync()
   
   # Notifications worker
   from app.workers.daily_notifications import run_daily_notifications_sync
   run_daily_notifications_sync()
"""


# ============================================================
# DECISÕES DOCUMENTADAS
# ============================================================
#
# ✅ Importação segura dos workers com try/except
# ✅ Scheduler só roda em produção (PRODUCTION=true)
# ✅ Fallback quando workers não estão disponíveis
# ✅ Verificação de ambiente (desenvolvimento vs produção)
# ✅ Função is_scheduler_running() para monitoramento
# ✅ Função get_scheduler_status() para monitoramento
# ✅ 🔧 NOVO: Internacionalização (i18n) nos logs
# ✅ Misfire grace time para workers atrasados
# ✅ atexit para shutdown seguro
# ✅ Documentação completa com pendências
#
# ❌ Não implementado (Pós-MVP):
#   - Dashboard de monitoramento dos workers
#   - Alertas quando worker falha consecutivamente
#   - Persistência de jobs (para não perder agendamentos ao reiniciar)
#   - Health check dos workers
#   - Métricas de execução (tempo médio, taxa de sucesso)
#   - Fila para notificações (Redis Queue)
#   - Retry automático para notificações falhas
#   - Worker incremental (apenas usuários com mudanças)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial com agendamento básico
#   - v2: Adicionado importação segura, fallback, ambiente (05/07/2026)
#   - v3: Adicionado i18n, get_scheduler_status() (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO