"""
Configuração do Scheduler para Workers
Arquivo: backend/app/utils/scheduler.py

Funcionalidades:
- Agendamento de workers diários (score, notificações e metas)
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
- 🆕 NOVO: Worker de metas recorrentes (goal_recurring)
- 🆕 NOVO: Worker de notificações de metas (goal_notifications)
- 🔧 CORRIGIDO: Caminho dos workers mantido como 'workers_disabled'
- 🔧 ADICIONADO: stop_scheduler() para desligar o scheduler
- 🔧 ADICIONADO: Validação de timezone com fallback para UTC
- 🔧 ADICIONADO: Log dos jobs registrados no startup

🔧 REGRA 3.1: Score Financeiro - Worker Diário (03:00)
🔧 REGRA 4.1: Notificações Proativas - Worker Diário (09:00)
🆕 REGRA: Metas Recorrentes - Worker Diário (00:00)
🆕 REGRA: Notificações de Metas - Worker Diário (09:00)

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

# ================================================================
# 🔧 CORREÇÃO 2: VALIDAÇÃO DE TIMEZONE
# ================================================================

def get_timezone():
    """
    Retorna o timezone configurado com fallback para UTC.
    """
    try:
        import pytz
        tz = pytz.timezone("America/Sao_Paulo")
        logger.info("🌐 Timezone configurado: America/Sao_Paulo")
        return tz
    except ImportError:
        logger.warning("⚠️ pytz não instalado, usando UTC")
        from datetime import timezone
        return timezone.utc
    except Exception as e:
        logger.warning(f"⚠️ Erro ao configurar timezone: {e}, usando UTC")
        from datetime import timezone
        return timezone.utc


# ================================================================
# FUNÇÕES DE IMPORTAÇÃO
# ================================================================

def _safe_import_workers():
    """
    Importa os workers de forma segura.
    Se não estiverem disponíveis, retorna None.
    
    🔧 CORRIGIDO: Mantido caminho 'workers_disabled'
    """
    workers = {
        "score": None,
        "notifications": None,
        "goal_recurring": None,
        "goal_notifications": None,
    }
    
    # Tenta importar worker de score
    try:
        from app.workers_disabled.score_worker import run_score_worker_sync
        workers["score"] = run_score_worker_sync
        logger.info(get_message("SCHEDULER_WORKER_SCORE_LOADED", "pt"))
    except ImportError as e:
        logger.warning(get_message("SCHEDULER_WORKER_SCORE_NOT_AVAILABLE", "pt", error=str(e)))
    except Exception as e:
        logger.error(get_message("SCHEDULER_WORKER_SCORE_ERROR", "pt", error=str(e)))
    
    # Tenta importar worker de notificações proativas
    try:
        from app.workers_disabled.daily_notifications import run_daily_notifications_sync
        workers["notifications"] = run_daily_notifications_sync
        logger.info(get_message("SCHEDULER_WORKER_NOTIFICATIONS_LOADED", "pt"))
    except ImportError as e:
        logger.warning(get_message("SCHEDULER_WORKER_NOTIFICATIONS_NOT_AVAILABLE", "pt", error=str(e)))
    except Exception as e:
        logger.error(get_message("SCHEDULER_WORKER_NOTIFICATIONS_ERROR", "pt", error=str(e)))
    
    # 🆕 Tenta importar worker de metas recorrentes
    try:
        from app.workers_disabled.goal_recurring import process_recurring_goals
        workers["goal_recurring"] = process_recurring_goals
        logger.info("✅ Worker de metas recorrentes carregado")
    except ImportError as e:
        logger.warning(f"⚠️ Worker de metas recorrentes não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao importar worker de metas recorrentes: {e}")
    
    # 🆕 Tenta importar worker de notificações de metas
    try:
        from app.workers_disabled.goal_notification import process_goal_notifications
        workers["goal_notifications"] = process_goal_notifications
        logger.info("✅ Worker de notificações de metas carregado")
    except ImportError as e:
        logger.warning(f"⚠️ Worker de notificações de metas não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao importar worker de notificações de metas: {e}")
    
    return workers


# ================================================================
# FUNÇÕES PRINCIPAIS
# ================================================================

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
    if not PRODUCTION and ENVIRONMENT != "production":
        logger.info(get_message("SCHEDULER_DEV_MODE", "pt"))
        logger.info("   Para testar workers, use os endpoints manuais (/workers/trigger)")
        return None
    
    # Importa workers de forma segura
    workers = _safe_import_workers()
    
    # Verifica se pelo menos um worker está disponível
    available_workers = [k for k, v in workers.items() if v is not None]
    if not available_workers:
        logger.error(get_message("SCHEDULER_NO_WORKERS", "pt"))
        return None
    
    logger.info(f"📊 Workers disponíveis: {', '.join(available_workers)}")
    
    # 🔧 CORREÇÃO 2: Obtém timezone com fallback
    timezone = get_timezone()
    
    _scheduler = BackgroundScheduler(timezone=timezone)
    
    # ================================================================
    # 1. Worker de Score (03:00)
    # ================================================================
    if workers["score"]:
        _scheduler.add_job(
            func=workers["score"],
            trigger=CronTrigger(hour=3, minute=0),
            id="score_daily_worker",
            name="Score Worker",
            replace_existing=True,
            misfire_grace_time=3600  # 1 hora de tolerância
        )
        logger.info(get_message("SCHEDULER_SCORE_SCHEDULED", "pt"))
    else:
        logger.warning(get_message("SCHEDULER_SCORE_NOT_SCHEDULED", "pt"))
    
    # ================================================================
    # 2. Worker de Notificações Proativas (09:00)
    # ================================================================
    if workers["notifications"]:
        _scheduler.add_job(
            func=workers["notifications"],
            trigger=CronTrigger(hour=9, minute=0),
            id="daily_notifications_worker",
            name="Notifications Worker",
            replace_existing=True,
            misfire_grace_time=1800  # 30 minutos de tolerância
        )
        logger.info(get_message("SCHEDULER_NOTIFICATIONS_SCHEDULED", "pt"))
    else:
        logger.warning(get_message("SCHEDULER_NOTIFICATIONS_NOT_SCHEDULED", "pt"))
    
    # ================================================================
    # 3. 🆕 Worker de Metas Recorrentes (00:00)
    # ================================================================
    if workers["goal_recurring"]:
        _scheduler.add_job(
            func=workers["goal_recurring"],
            trigger=CronTrigger(hour=0, minute=0),
            id="goal_recurring_worker",
            name="Goal Recurring Worker",
            replace_existing=True,
            misfire_grace_time=3600  # 1 hora de tolerância
        )
        logger.info("✅ Worker de metas recorrentes agendado para 00:00")
    else:
        logger.warning("⚠️ Worker de metas recorrentes NÃO agendado")
    
    # ================================================================
    # 4. 🆕 Worker de Notificações de Metas (09:00)
    # ================================================================
    if workers["goal_notifications"]:
        _scheduler.add_job(
            func=workers["goal_notifications"],
            trigger=CronTrigger(hour=9, minute=0),
            id="goal_notifications_worker",
            name="Goal Notifications Worker",
            replace_existing=True,
            misfire_grace_time=1800  # 30 minutos de tolerância
        )
        logger.info("✅ Worker de notificações de metas agendado para 09:00")
    else:
        logger.warning("⚠️ Worker de notificações de metas NÃO agendado")
    
    # Só inicia o scheduler se pelo menos um worker foi agendado
    if _scheduler.get_jobs():
        _scheduler.start()
        logger.info(get_message("SCHEDULER_STARTED", "pt"))
        
        # 🔧 CORREÇÃO 3: Log dos jobs registrados
        for job in _scheduler.get_jobs():
            logger.info(f"📋 Job registrado: {job.id} - Próxima execução: {job.next_run_time}")
        
        # Garante que o scheduler será desligado ao final do processo
        atexit.register(lambda: shutdown_scheduler())
    else:
        logger.warning(get_message("SCHEDULER_NO_JOBS", "pt"))
        _scheduler = None
    
    return _scheduler


def start_scheduler():
    """
    Função wrapper para iniciar o scheduler (usada no main.py).
    """
    return init_scheduler()


def stop_scheduler():
    """
    Para o scheduler de forma segura.
    Usada no main.py para shutdown.
    """
    global _scheduler
    
    if _scheduler is None:
        logger.info("ℹ️ Scheduler já está parado")
        return True
    
    try:
        # Remove todos os jobs
        _scheduler.remove_all_jobs()
        
        # Desliga o scheduler
        _scheduler.shutdown(wait=True)
        _scheduler = None
        
        logger.info("🛑 Scheduler parado com sucesso")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao parar scheduler: {e}")
        return False


def shutdown_scheduler():
    """
    Desliga o scheduler de forma segura (alias para stop_scheduler)
    """
    return stop_scheduler()


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


def get_scheduler_status() -> dict:
    """
    Retorna o status atual do scheduler para monitoramento.
    
    Returns:
        dict: Status do scheduler com jobs e informações
    """
    if not _scheduler:
        return {
            "running": False,
            "jobs": [],
            "job_count": 0,
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
   from app.utils.scheduler import start_scheduler
   scheduler = start_scheduler()

2. Verificar se o scheduler está rodando:
   from app.utils.scheduler import is_scheduler_running
   if is_scheduler_running():
       print("Scheduler ativo")

3. Obter status para monitoramento:
   from app.utils.scheduler import get_scheduler_status
   status = get_scheduler_status()
   print(status["jobs"])

4. Desligar o scheduler (no shutdown):
   from app.utils.scheduler import stop_scheduler
   stop_scheduler()

5. Executar workers manualmente (para testes):
   from app.workers_disabled.goal_recurring import process_recurring_goals
   import asyncio
   asyncio.run(process_recurring_goals())
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
# 🆕 NOVO: Worker de metas recorrentes (00:00)
# 🆕 NOVO: Worker de notificações de metas (09:00)
# 🔧 CORRIGIDO: Caminho dos workers mantido como 'workers_disabled'
# 🔧 ADICIONADO: stop_scheduler() para desligar o scheduler
# 🔧 ADICIONADO: Validação de timezone com fallback para UTC
# 🔧 ADICIONADO: Log dos jobs registrados no startup
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
#   - v4: 🆕 Adicionado workers de metas recorrentes e notificações (11/07/2026)
#   - v5: 🔧 CORRIGIDO - Caminho dos workers mantido como 'workers_disabled' (12/07/2026)
#   - v6: 🔧 ADICIONADO - stop_scheduler(), validação timezone, log jobs (12/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO
