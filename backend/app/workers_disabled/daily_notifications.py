"""
Worker de Notificações Proativas - VERSÃO CORRIGIDA
Arquivo: backend/workers/daily_notifications.py

🔧 CORREÇÕES (23/07/2026):
   - 🔧 CORRIGIDO: get_user_dashboard_data usa 'bills' em vez de 'bill_installments'
   - 🔧 CORRIGIDO: Busca contas a vencer usando a conta mestra (bills)
   - 🔧 CORRIGIDO: Verifica parcelas pendentes dentro da conta mestra
   - 🔧 ADICIONADO: Função _get_next_installment() para buscar próxima parcela
   - 🔧 ADICIONADO: Compatibilidade com modelo de contas do frontend

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 23/07/2026
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.database import get_database
from app.services.ia_service import obter_resposta_ia_async
from app.utils.logger import setup_logger
from app.utils.currency import from_cents
from app.utils.i18n import get_message

# Importação da rota de notificações
from app.routes.notifications import send_push_notification

logger = setup_logger(__name__)

# ================================================================
# CONSTANTES
# ================================================================

MAX_USERS_PER_BATCH = int(os.getenv("NOTIFICATION_BATCH_SIZE", "1000"))
PAUSE_INTERVAL = int(os.getenv("NOTIFICATION_PAUSE_INTERVAL", "10"))
PAUSE_DURATION = float(os.getenv("NOTIFICATION_PAUSE_DURATION", "1.0"))
DAYS_AHEAD = int(os.getenv("NOTIFICATION_DAYS_AHEAD", "3"))
DAYS_BACK = int(os.getenv("NOTIFICATION_DAYS_BACK", "30"))
MAX_RETRIES = int(os.getenv("NOTIFICATION_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = int(os.getenv("NOTIFICATION_RETRY_BACKOFF", "2"))

# ================================================================
# REDIS CLIENT
# ================================================================

try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para fila de notificações")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - fila de notificações desabilitada")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - fila de notificações desabilitada")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")

# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================

def _get_next_installment(bill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    🔧 NOVO: Busca a próxima parcela não paga de uma conta mestra.
    
    Args:
        bill: Documento da conta mestra
    
    Returns:
        dict: Dados da próxima parcela ou None
    """
    installments = bill.get("installments", {})
    
    # Verifica se há parcelas
    if not installments:
        return None
    
    # Verifica se a conta já está paga
    if bill.get("paid", False):
        return None
    
    # Busca a próxima parcela não paga
    paid = installments.get("paid", 0)
    total = installments.get("total", 0)
    
    if paid >= total:
        return None
    
    # Calcula a data da próxima parcela
    start_date = installments.get("start_date")
    if not start_date:
        return None
    
    # Se for parcela única (total = 1)
    if total == 1:
        return {
            "number": 1,
            "due_date": start_date,
            "amount": bill.get("amount", 0)
        }
    
    # Para múltiplas parcelas, calcula a data da próxima
    due_day = installments.get("due_day", 1)
    next_number = paid + 1
    
    # Calcula a data da próxima parcela
    from dateutil.relativedelta import relativedelta
    next_date = start_date + relativedelta(months=paid)
    
    # Ajusta o dia para o dia de vencimento
    try:
        next_date = next_date.replace(day=min(due_day, 28))
    except ValueError:
        # Se o dia for inválido (ex: 31 em fevereiro), usa o último dia do mês
        from calendar import monthrange
        last_day = monthrange(next_date.year, next_date.month)[1]
        next_date = next_date.replace(day=min(due_day, last_day))
    
    # Valor por parcela (em centavos)
    amount_per_installment = bill.get("amount", 0) // total if total > 0 else 0
    
    return {
        "number": next_number,
        "due_date": next_date,
        "amount": amount_per_installment
    }


async def get_user_notification_token(user_id: str, db) -> Optional[str]:
    """Busca o token de notificação push do usuário."""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            tokens = user.get("expo_push_tokens", [])
            if tokens:
                latest_token = max(tokens, key=lambda t: t.get("last_active", datetime.min))
                token = latest_token.get("token")
                if token:
                    logger.debug(get_message("NOTIFICATION_TOKEN_FOUND", "pt", user_id=user_id))
                    return token
        
        logger.debug(get_message("NOTIFICATION_TOKEN_NOT_FOUND", "pt", user_id=user_id))
        return None
    except Exception as e:
        logger.error(get_message("NOTIFICATION_TOKEN_ERROR", "pt", user_id=user_id, error=str(e)))
        return None


async def send_with_retry(
    user_id: str,
    db,
    max_retries: int = MAX_RETRIES,
    backoff_base: int = RETRY_BACKOFF_BASE
) -> bool:
    """Envia notificação com retry automático e backoff exponencial."""
    if redis_client:
        retry_key = f"notification_retry:{user_id}"
        attempts = await redis_client.get(retry_key)
        if attempts:
            attempts = int(attempts)
        else:
            attempts = 0
    else:
        attempts = 0
    
    for attempt in range(attempts, max_retries):
        try:
            success = await send_daily_notification(user_id, db)
            
            if success:
                if redis_client:
                    await redis_client.delete(retry_key)
                logger.debug(f"✅ Notificação enviada na tentativa {attempt + 1} para {user_id}")
                return True
            
            wait_time = backoff_base ** attempt
            logger.warning(f"⚠️ Falha na tentativa {attempt + 1} para {user_id}, aguardando {wait_time}s")
            
            if redis_client:
                await redis_client.setex(retry_key, 3600, attempt + 1)
            
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"❌ Erro na tentativa {attempt + 1} para {user_id}: {e}")
            wait_time = backoff_base ** attempt
            await asyncio.sleep(wait_time)
    
    logger.error(f"❌ Todas as {max_retries} tentativas falharam para {user_id}")
    return False


# ================================================================
# ✅ CORRIGIDO: get_user_dashboard_data usando 'bills'
# ================================================================

async def get_user_dashboard_data(user_id: str, db) -> Dict[str, Any]:
    """
    🔧 CORRIGIDO: Busca dados do usuário para gerar a mensagem personalizada.
    
    ✅ AGORA USA: 'bills' (conta mestra) em vez de 'bill_installments'
    ✅ Busca a próxima parcela de cada conta
    ✅ Alinhado com o frontend (BillsContext)
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
    
    Returns:
        dict: Dados do dashboard do usuário
    """
    try:
        # Busca score atual
        score_doc = await db.score_history.find_one(
            {"user_id": user_id},
            sort=[("date", -1)]
        )
        score = score_doc.get("score", 0) if score_doc else 0
        
        # ✅ CORRIGIDO: Busca contas a vencer usando a conta mestra (bills)
        today = datetime.now(timezone.utc)
        days_ahead = today + timedelta(days=DAYS_AHEAD)
        
        # Busca todas as contas não pagas do usuário
        bills_cursor = db.bills.find({
            "user_id": user_id,
            "paid": False
        })
        all_bills = await bills_cursor.to_list(100)
        
        # Filtra contas com próxima parcela dentro do período
        upcoming_bills = []
        upcoming_bills_total = 0
        
        for bill in all_bills:
            next_installment = _get_next_installment(bill)
            if next_installment:
                due_date = next_installment.get("due_date")
                if due_date and today <= due_date <= days_ahead:
                    upcoming_bills.append({
                        "bill_id": str(bill["_id"]),
                        "description": bill.get("description", "Conta"),
                        "due_date": due_date,
                        "amount": next_installment.get("amount", 0),
                        "installment_number": next_installment.get("number", 1)
                    })
                    upcoming_bills_total += next_installment.get("amount", 0)
        
        upcoming_bills_count = len(upcoming_bills)
        
        # Busca metas com progresso > 80%
        goals_cursor = db.goals.find({
            "user_id": user_id,
            "completed": False
        })
        goals = await goals_cursor.to_list(20)
        
        almost_complete_goals = []
        for goal in goals:
            target = goal.get("target", 0)
            current = goal.get("current", 0)
            if target > 0:
                progress = (current / target) * 100
                if progress >= 80:
                    almost_complete_goals.append({
                        "name": goal.get("name", "Meta"),
                        "progress": round(progress, 1)
                    })
        
        # Busca gastos dos últimos N dias para média
        days_back = today - timedelta(days=DAYS_BACK)
        transactions = await db.transactions.find({
            "user_id": user_id,
            "type": "expense",
            "date": {"$gte": days_back}
        }).to_list(100)
        
        total_expense = sum(t.get("amount", 0) for t in transactions)
        avg_daily_expense = total_expense / DAYS_BACK if transactions else 0
        
        # Busca gastos de ontem
        yesterday_start = today - timedelta(days=1)
        yesterday_end = today
        yesterday_expenses = await db.transactions.find({
            "user_id": user_id,
            "type": "expense",
            "date": {"$gte": yesterday_start, "$lt": yesterday_end}
        }).to_list(100)
        yesterday_total = sum(e.get("amount", 0) for e in yesterday_expenses)
        
        is_above_average = yesterday_total > avg_daily_expense
        
        # Converte centavos para reais (apenas para exibição na IA)
        upcoming_bills_total_reais = from_cents(upcoming_bills_total) if upcoming_bills_total else 0
        yesterday_total_reais = from_cents(yesterday_total) if yesterday_total else 0
        avg_daily_expense_reais = from_cents(avg_daily_expense) if avg_daily_expense else 0
        
        logger.debug(get_message("NOTIFICATION_USER_DATA", "pt", user_id=user_id, score=score))
        
        return {
            "score": score,
            "upcoming_bills_count": upcoming_bills_count,
            "upcoming_bills_total": upcoming_bills_total_reais,
            "upcoming_bills": upcoming_bills,
            "almost_complete_goals": almost_complete_goals,
            "yesterday_expense": yesterday_total_reais,
            "avg_daily_expense": avg_daily_expense_reais,
            "is_above_average": is_above_average
        }
    except Exception as e:
        logger.error(get_message("NOTIFICATION_USER_DATA_ERROR", "pt", user_id=user_id, error=str(e)))
        return {
            "score": 0,
            "upcoming_bills_count": 0,
            "upcoming_bills_total": 0,
            "upcoming_bills": [],
            "almost_complete_goals": [],
            "yesterday_expense": 0,
            "avg_daily_expense": 0,
            "is_above_average": False
        }


async def generate_personalized_message(user_data: Dict[str, Any]) -> str:
    """Gera mensagem personalizada usando IA."""
    score = user_data.get("score", 0)
    upcoming_bills_count = user_data.get("upcoming_bills_count", 0)
    upcoming_bills_total = user_data.get("upcoming_bills_total", 0)
    almost_complete_goals = user_data.get("almost_complete_goals", [])
    yesterday_expense = user_data.get("yesterday_expense", 0)
    avg_daily_expense = user_data.get("avg_daily_expense", 0)
    is_above_average = user_data.get("is_above_average", False)
    
    context = f"""
Você é a Veloria, uma assistente financeira amigável.

Dados do usuário:
- Score financeiro: {score} (escala 0-100)
- Contas a vencer nos próximos {DAYS_AHEAD} dias: {upcoming_bills_count} conta(s), totalizando R$ {upcoming_bills_total:.2f}
- Metas quase concluídas (>80%): {len(almost_complete_goals)} meta(s)
- Gastos de ontem: R$ {yesterday_expense:.2f}
- Média diária de gastos: R$ {avg_daily_expense:.2f}
- Gastos de ontem foram {'acima' if is_above_average else 'abaixo'} da média

Gere uma mensagem curta (1-2 frases) para motivar o usuário. Seja positiva, prática e personalizada.
Use emojis para tornar mais amigável.
"""
    
    try:
        response = await obter_resposta_ia_async(
            system_message=context,
            user_message="Gere uma mensagem motivacional para o usuário baseada nos dados acima."
        )
        return response.strip()
    except Exception as e:
        logger.error(get_message("NOTIFICATION_IA_ERROR", "pt", error=str(e)))
        language = "pt"
        if score >= 80:
            return get_message("NOTIFICATION_FALLBACK_HIGH", language, score=score)
        elif score >= 60:
            return get_message("NOTIFICATION_FALLBACK_MEDIUM", language, score=score)
        elif score >= 40:
            return get_message("NOTIFICATION_FALLBACK_LOW", language, score=score)
        else:
            return get_message("NOTIFICATION_FALLBACK_VERY_LOW", language, score=score)


async def send_daily_notification(user_id: str, db) -> bool:
    """Envia notificação proativa para um usuário específico."""
    try:
        token = await get_user_notification_token(user_id, db)
        if not token:
            logger.debug(get_message("NOTIFICATION_NO_TOKEN", "pt", user_id=user_id))
            return False
        
        user_data = await get_user_dashboard_data(user_id, db)
        message = await generate_personalized_message(user_data)
        
        success = await send_push_notification(
            token=token,
            title=get_message("NOTIFICATION_DAILY_TITLE", "pt"),
            body=message[:250],
            data={
                "type": "daily_summary",
                "score": user_data.get("score", 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        if success:
            logger.info(get_message("NOTIFICATION_SENT_SUCCESS", "pt", user_id=user_id, score=user_data.get("score", 0)))
            return True
        else:
            logger.warning(get_message("NOTIFICATION_SENT_FAILED", "pt", user_id=user_id))
            return False
        
    except Exception as e:
        logger.error(get_message("NOTIFICATION_SEND_ERROR", "pt", user_id=user_id, error=str(e)))
        return False


async def add_to_notification_queue(user_id: str) -> bool:
    """Adiciona um usuário à fila de notificações no Redis."""
    if not redis_client:
        return False
    
    try:
        await redis_client.rpush("notification_queue", user_id)
        logger.debug(f"📥 Usuário {user_id} adicionado à fila de notificações")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Erro ao adicionar à fila: {e}")
        return False


async def process_notification_queue() -> dict:
    """Processa a fila de notificações no Redis."""
    if not redis_client:
        logger.warning("ℹ️ Redis não disponível para processar fila")
        return {"processed": 0, "success": 0, "errors": 0}
    
    db = get_database()
    processed = 0
    success_count = 0
    error_count = 0
    
    logger.info("🚀 Iniciando processamento da fila de notificações...")
    
    while True:
        try:
            item = await redis_client.blpop("notification_queue", timeout=5)
            if not item:
                break
            
            user_id = item[1]
            result = await send_daily_notification(user_id, db)
            processed += 1
            
            if result:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar fila: {e}")
            error_count += 1
    
    logger.info(f"✅ Fila processada: {success_count}/{processed} enviadas, {error_count} erros")
    
    return {
        "processed": processed,
        "success": success_count,
        "errors": error_count
    }


async def process_notification_queue_forever() -> None:
    """Processa a fila de notificações em loop infinito."""
    logger.info("🔄 Iniciando worker de fila de notificações (loop infinito)...")
    
    while True:
        try:
            result = await process_notification_queue()
            if result["processed"] == 0:
                await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"❌ Erro no worker de fila: {e}")
            await asyncio.sleep(30)


async def send_daily_notifications_to_all_users() -> dict:
    """Envia notificações proativas para TODOS os usuários."""
    start_time = datetime.now(timezone.utc)
    logger.info(get_message("NOTIFICATION_WORKER_START", "pt"))
    
    db = get_database()
    
    users = await db.users.find({
        "expo_push_tokens": {"$exists": True, "$ne": []},
        "push_enabled": {"$ne": False}
    }).to_list(MAX_USERS_PER_BATCH)
    
    total_users = len(users)
    success_count = 0
    error_count = 0
    log_entries = []
    
    logger.info(get_message("NOTIFICATION_WORKER_USERS", "pt", total=total_users))
    
    for i, user in enumerate(users):
        user_id = str(user["_id"])
        try:
            result = await send_with_retry(user_id, db)
            
            if result:
                success_count += 1
                log_entries.append({
                    "user_id": user_id,
                    "type": "daily_summary",
                    "score": 0,
                    "message": "",
                    "sent_at": datetime.now(timezone.utc),
                    "success": True
                })
            else:
                error_count += 1
                log_entries.append({
                    "user_id": user_id,
                    "type": "daily_summary",
                    "score": 0,
                    "message": "Falha no envio",
                    "sent_at": datetime.now(timezone.utc),
                    "success": False
                })
        except Exception as e:
            logger.error(get_message("NOTIFICATION_WORKER_USER_ERROR", "pt", user_id=user_id, error=str(e)))
            error_count += 1
            log_entries.append({
                "user_id": user_id,
                "type": "daily_summary",
                "score": 0,
                "message": f"Erro: {str(e)[:100]}",
                "sent_at": datetime.now(timezone.utc),
                "success": False
            })
        
        if (i + 1) % PAUSE_INTERVAL == 0:
            await asyncio.sleep(PAUSE_DURATION)
    
    if log_entries:
        try:
            await db.notification_logs.insert_many(log_entries)
            logger.debug(f"📊 {len(log_entries)} logs inseridos em lote")
        except Exception as e:
            logger.error(f"❌ Erro ao inserir logs em lote: {e}")
            for entry in log_entries:
                try:
                    await db.notification_logs.insert_one(entry)
                except:
                    pass
    
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    logger.info(get_message("NOTIFICATION_WORKER_DONE", "pt", success=success_count, total=total_users, duration=round(duration, 2)))
    
    return {
        "total_users": total_users,
        "success_count": success_count,
        "error_count": error_count,
        "duration_seconds": round(duration, 2),
        "timestamp": start_time.isoformat()
    }


def run_daily_notifications_sync() -> Optional[dict]:
    """Versão síncrona para ser chamada pelo APScheduler."""
    try:
        result = asyncio.run(send_daily_notifications_to_all_users())
        return result
    except Exception as e:
        logger.error(get_message("NOTIFICATION_WORKER_FATAL", "pt", error=str(e)))
        import traceback
        logger.debug(traceback.format_exc())
        return None


# ================================================================
# CHANGELOG
# ================================================================

"""
📋 CHANGELOG - 23/07/2026 - VERSÃO CORRIGIDA
──────────────────────────────────────────────────────────────

✅ CORREÇÕES:
   1. 🔧 get_user_dashboard_data: usa 'bills' em vez de 'bill_installments'
   2. 🔧 Adicionada função _get_next_installment() para buscar próxima parcela
   3. 🔧 Compatibilidade com modelo de contas do frontend
   4. 🔧 Adicionado campo 'upcoming_bills' com detalhes das contas
   5. 🔧 Verificação de contas paga antes de processar

✅ MANTIDO:
   - Redis fila para workers distribuídos
   - Retry automático com backoff exponencial
   - Processamento em lote com insert_many
   - Internacionalização (i18n) nos logs
   - Constantes centralizadas (.env)

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 23/07/2026
"""