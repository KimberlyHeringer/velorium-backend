"""
Configuração do Scheduler para Workers
Arquivo: backend/app/utils/scheduler.py

🔧 REGRA 3.1: Score Financeiro - Worker Diário (03:00)
🔧 REGRA 4.1: Notificações Proativas - Worker Diário (09:00)
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Scheduler global
_scheduler = None


def init_scheduler():
    """
    Inicializa o scheduler com todos os workers
    """
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("Scheduler já foi inicializado")
        return _scheduler
    
    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    
    # Importa as funções dos workers
    from workers.score_worker import run_score_worker_sync
    from workers.daily_notifications import run_daily_notifications_sync
    
    # Agenda worker de score (03:00)
    _scheduler.add_job(
        func=run_score_worker_sync,
        trigger=CronTrigger(hour=3, minute=0),
        id="score_daily_worker",
        replace_existing=True,
        misfire_grace_time=3600
    )
    logger.info("⏰ Worker de score agendado para 03:00")
    
    # Agenda worker de notificações proativas (09:00)
    _scheduler.add_job(
        func=run_daily_notifications_sync,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_notifications_worker",
        replace_existing=True,
        misfire_grace_time=1800
    )
    logger.info("⏰ Worker de notificações proativas agendado para 09:00")
    
    _scheduler.start()
    logger.info("✅ Scheduler iniciado com sucesso!")
    
    # Garante que o scheduler será desligado ao final do processo
    atexit.register(lambda: shutdown_scheduler())
    
    return _scheduler


def shutdown_scheduler():
    """
    Desliga o scheduler
    """
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        logger.info("🛑 Scheduler desligado")
        _scheduler = None


def get_scheduler():
    """
    Retorna a instância do scheduler
    """
    return _scheduler