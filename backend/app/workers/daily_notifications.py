"""
Worker de Notificações Proativas
Arquivo: backend/workers/daily_notifications.py

🔧 REGRA 4.1: Notificações Proativas
- Executa diariamente às 09:00
- Gera mensagem personalizada via IA
- Envia push notification para cada usuário
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from bson import ObjectId

from app.database import get_database
from app.services.ia_service import obter_resposta_ia_async
from app.utils.logger import setup_logger
from app.utils.currency import from_cents

logger = setup_logger(__name__)


async def get_user_notification_token(user_id: str, db) -> str:
    """Busca o token de notificação push do usuário"""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        return user.get("expo_push_token")
    return None


async def get_user_dashboard_data(user_id: str, db) -> Dict[str, Any]:
    """
    Busca dados do usuário para gerar a mensagem personalizada:
    - Score atual
    - Contas a vencer (próximos 3 dias)
    - Metas com progresso > 80%
    - Gastos acima da média
    """
    # Busca score atual
    score_doc = await db.score_history.find_one(
        {"user_id": user_id},
        sort=[("date", -1)]
    )
    score = score_doc.get("score", 0) if score_doc else 0
    
    # Busca contas a vencer (próximos 3 dias)
    today = datetime.now(timezone.utc)
    three_days_later = today + timedelta(days=3)
    
    bills_cursor = db.bill_installments.find({
        "user_id": user_id,
        "paid": False,
        "due_date": {"$gte": today, "$lte": three_days_later}
    })
    upcoming_bills = await bills_cursor.to_list(10)
    upcoming_bills_count = len(upcoming_bills)
    upcoming_bills_total = sum(b.get("amount", 0) for b in upcoming_bills)
    
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
    
    # Busca gastos dos últimos 30 dias para média
    thirty_days_ago = today - timedelta(days=30)
    transactions = await db.transactions.find({
        "user_id": user_id,
        "type": "expense",
        "date": {"$gte": thirty_days_ago}
    }).to_list(100)
    
    # Calcula média diária de gastos
    total_expense = sum(t.get("amount", 0) for t in transactions)
    avg_daily_expense = total_expense / 30 if transactions else 0
    
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
    
    # Converte centavos para reais
    upcoming_bills_total_reais = from_cents(upcoming_bills_total) if upcoming_bills_total else 0
    yesterday_total_reais = from_cents(yesterday_total) if yesterday_total else 0
    avg_daily_expense_reais = from_cents(avg_daily_expense) if avg_daily_expense else 0
    
    return {
        "score": score,
        "upcoming_bills_count": upcoming_bills_count,
        "upcoming_bills_total": upcoming_bills_total_reais,
        "almost_complete_goals": almost_complete_goals,
        "yesterday_expense": yesterday_total_reais,
        "avg_daily_expense": avg_daily_expense_reais,
        "is_above_average": is_above_average
    }


async def generate_personalized_message(user_data: Dict[str, Any]) -> str:
    """
    Gera mensagem personalizada usando IA
    """
    score = user_data.get("score", 0)
    upcoming_bills_count = user_data.get("upcoming_bills_count", 0)
    upcoming_bills_total = user_data.get("upcoming_bills_total", 0)
    almost_complete_goals = user_data.get("almost_complete_goals", [])
    yesterday_expense = user_data.get("yesterday_expense", 0)
    avg_daily_expense = user_data.get("avg_daily_expense", 0)
    is_above_average = user_data.get("is_above_average", False)
    
    # Constrói contexto para IA
    context = f"""
Você é a Veloria, uma assistente financeira amigável.

Dados do usuário:
- Score financeiro: {score} (escala 0-100)
- Contas a vencer nos próximos 3 dias: {upcoming_bills_count} conta(s), totalizando R$ {upcoming_bills_total:.2f}
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
        logger.error(f"Erro ao gerar mensagem IA: {e}")
        # Fallback: mensagem genérica
        return f"💪 Seu score está em {score}! Continue assim para alcançar suas metas."


async def send_daily_notification(user_id: str, db):
    """
    Envia notificação proativa para um usuário específico
    """
    try:
        # Busca token do usuário
        token = await get_user_notification_token(user_id, db)
        if not token:
            logger.debug(f"Usuário {user_id} não tem token de notificação")
            return
        
        # Busca dados do usuário
        user_data = await get_user_dashboard_data(user_id, db)
        
        # Gera mensagem personalizada
        message = await generate_personalized_message(user_data)
        
        # Envia notificação
        from app.services.notification_service import send_push_notification
        await send_push_notification(token, {
            "title": "🌅 Bom dia! Sua dose diária de finanças",
            "body": message,
            "data": {
                "type": "daily_summary",
                "score": user_data.get("score", 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        })
        
        # Registra log
        logger.info(f"Notificação enviada para usuário {user_id} - Score: {user_data.get('score', 0)}")
        
    except Exception as e:
        logger.error(f"Erro ao enviar notificação para usuário {user_id}: {e}")


async def send_daily_notifications_to_all_users():
    """
    Envia notificações proativas para TODOS os usuários
    """
    start_time = datetime.now(timezone.utc)
    logger.info("🚀 Iniciando worker de notificações proativas...")
    
    db = await get_database()
    
    # Busca todos os usuários com token de notificação
    users = await db.users.find({
        "expo_push_token": {"$exists": True, "$ne": None}
    }).to_list(1000)
    
    total_users = len(users)
    success_count = 0
    error_count = 0
    
    logger.info(f"📊 Encontrados {total_users} usuários com notificações ativas")
    
    for user in users:
        user_id = str(user["_id"])
        try:
            await send_daily_notification(user_id, db)
            success_count += 1
        except Exception as e:
            logger.error(f"Erro ao processar usuário {user_id}: {e}")
            error_count += 1
        
        # Pequena pausa para não sobrecarregar
        await asyncio.sleep(0.5)
    
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"✅ Worker de notificações concluído! {success_count}/{total_users} enviadas em {duration:.2f}s")
    
    return {
        "total_users": total_users,
        "success": success_count,
        "errors": error_count,
        "duration_seconds": round(duration, 2)
    }


def run_daily_notifications_sync():
    """
    Versão síncrona para ser chamada pelo APScheduler
    """
    try:
        result = asyncio.run(send_daily_notifications_to_all_users())
        return result
    except Exception as e:
        logger.error(f"❌ Falha fatal no worker de notificações: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None