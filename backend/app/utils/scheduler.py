"""
Configuração do Scheduler para Workers
Arquivo: backend/app/utils/scheduler.py

🔧 CORRIGIDO:
- Adicionado tratamento seguro para importação dos workers
- Adicionado fallback quando workers não estão disponíveis
- Adicionada verificação de ambiente (não roda workers em desenvolvimento)
- Melhorado logging

🔧 REGRA 3.1: Score Financeiro - Worker Diário (03:00)
🔧 REGRA 4.1: Notificações Proativas - Worker Diário (09:00)
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
import os

from app.utils.logger import setup_logger

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
        logger.info("✅ Worker de score carregado com sucesso")
    except ImportError as e:
        logger.warning(f"⚠️ Worker de score não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao carregar worker de score: {e}")
    
    # Tenta importar worker de notificações
    try:
        from app.workers.daily_notifications import run_daily_notifications_sync
        run_notifications_worker = run_daily_notifications_sync
        logger.info("✅ Worker de notificações carregado com sucesso")
    except ImportError as e:
        logger.warning(f"⚠️ Worker de notificações não disponível: {e}")
    except Exception as e:
        logger.error(f"❌ Erro ao carregar worker de notificações: {e}")
    
    return run_score_worker, run_notifications_worker


def init_scheduler():
    """
    Inicializa o scheduler com todos os workers.
    Em desenvolvimento, os workers não são agendados (apenas em produção).
    """
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("Scheduler já foi inicializado")
        return _scheduler
    
    # Verifica se deve rodar workers
    if not PRODUCTION:
        logger.info("ℹ️ Ambiente de desenvolvimento detectado. Workers NÃO serão agendados.")
        logger.info("   Para testar workers, use os endpoints manuais (/notifications/trigger-daily)")
        return None
    
    # Importa workers de forma segura
    run_score_worker, run_notifications_worker = _safe_import_workers()
    
    # Verifica se pelo menos um worker está disponível
    if not run_score_worker and not run_notifications_worker:
        logger.error("❌ Nenhum worker disponível. Scheduler não será iniciado.")
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
        logger.info("⏰ Worker de score agendado para 03:00")
    else:
        logger.warning("⚠️ Worker de score NÃO agendado (não disponível)")
    
    # Agenda worker de notificações proativas (09:00)
    if run_notifications_worker:
        _scheduler.add_job(
            func=run_notifications_worker,
            trigger=CronTrigger(hour=9, minute=0),
            id="daily_notifications_worker",
            replace_existing=True,
            misfire_grace_time=1800  # 30 minutos de tolerância
        )
        logger.info("⏰ Worker de notificações proativas agendado para 09:00")
    else:
        logger.warning("⚠️ Worker de notificações NÃO agendado (não disponível)")
    
    # Só inicia o scheduler se pelo menos um worker foi agendado
    if _scheduler.get_jobs():
        _scheduler.start()
        logger.info("✅ Scheduler iniciado com sucesso!")
        
        # Garante que o scheduler será desligado ao final do processo
        atexit.register(lambda: shutdown_scheduler())
    else:
        logger.warning("⚠️ Nenhum worker agendado. Scheduler não foi iniciado.")
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
            logger.info("🛑 Scheduler desligado")
        except Exception as e:
            logger.error(f"Erro ao desligar scheduler: {e}")
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


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTE ARQUIVO:
================================================================================
1. Importação segura dos workers com try/except
2. Scheduler só roda em produção (PRODUCTION=true)
3. Fallback quando workers não estão disponíveis
4. Verificação de ambiente (desenvolvimento vs produção)
5. Função is_scheduler_running() para monitoramento

⚠️ PENDÊNCIAS PARA PÓS-MVP:
================================================================================
1. Dashboard de monitoramento dos workers
2. Alertas quando worker falha consecutivamente
3. Persistência de jobs (para não perder agendamentos ao reiniciar)
4. Health check dos workers
5. Métricas de execução (tempo médio, taxa de sucesso)

================================================================================
✅ STATUS: PRONTO PARA MVP
================================================================================
"""