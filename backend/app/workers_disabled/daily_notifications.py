"""
Worker de Notificações Proativas
Arquivo: backend/workers/daily_notifications.py

🔧 CORRIGIDO:
- Importação correta de send_push_notification (de app.routes.notifications)
- Removido await desnecessário do get_database()
- Adicionada verificação de token antes de enviar
- Melhorado tratamento de erros

🔧 REGRA 4.1: Notificações Proativas
- Executa diariamente às 09:00
- Gera mensagem personalizada via IA
- Envia push notification para cada usuário
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.database import get_database
from app.services.ia_service import obter_resposta_ia_async
from app.utils.logger import setup_logger
from app.utils.currency import from_cents

# 🔧 CORRIGIDO: importação correta (da rota, não do service inexistente)
from app.routes.notifications import send_push_notification

logger = setup_logger(__name__)


async def get_user_notification_token(user_id: str, db) -> Optional[str]:
    """Busca o token de notificação push do usuário"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            token = user.get("expo_push_token")
            if token:
                logger.debug(f"Token encontrado para usuário {user_id}")
                return token
        logger.debug(f"Nenhum token encontrado para usuário {user_id}")
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar token para usuário {user_id}: {e}")
        return None


async def get_user_dashboard_data(user_id: str, db) -> Dict[str, Any]:
    """
    Busca dados do usuário para gerar a mensagem personalizada:
    - Score atual
    - Contas a vencer (próximos 3 dias)
    - Metas com progresso > 80%
    - Gastos acima da média
    """
    try:
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
        
        # Calcula média diária de gastos (em centavos)
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
        
        # Converte centavos para reais (apenas para exibição na IA)
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
    except Exception as e:
        logger.error(f"Erro ao buscar dados do usuário {user_id}: {e}")
        return {
            "score": 0,
            "upcoming_bills_count": 0,
            "upcoming_bills_total": 0,
            "almost_complete_goals": [],
            "yesterday_expense": 0,
            "avg_daily_expense": 0,
            "is_above_average": False
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
        # Fallback: mensagem genérica baseada no score
        if score >= 80:
            return f"🏆 Excelente! Seu score está em {score}. Continue assim!"
        elif score >= 60:
            return f"📈 Bom trabalho! Seu score é {score}. Com pequenos ajustes, você chega lá!"
        elif score >= 40:
            return f"💪 Você está no caminho! Score {score}. Foque em reduzir gastos."
        else:
            return f"🌟 Vamos começar? Seu score é {score}. Eu posso te ajudar a melhorar!"


async def send_daily_notification(user_id: str, db):
    """
    Envia notificação proativa para um usuário específico
    """
    try:
        # Busca token do usuário
        token = await get_user_notification_token(user_id, db)
        if not token:
            logger.debug(f"Usuário {user_id} não tem token de notificação")
            return False
        
        # Busca dados do usuário
        user_data = await get_user_dashboard_data(user_id, db)
        
        # Gera mensagem personalizada
        message = await generate_personalized_message(user_data)
        
        # 🔧 CORRIGIDO: send_push_notification agora importado corretamente
        success = await send_push_notification(
            token=token,
            title="🌅 Bom dia! Sua dose diária de finanças",
            body=message[:250],  # Limita tamanho
            data={
                "type": "daily_summary",
                "score": user_data.get("score", 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        if success:
            # Registra o envio no log
            logger.info(f"✅ Notificação enviada para usuário {user_id} - Score: {user_data.get('score', 0)}")
            
            # Registra no banco para auditoria
            await db.notification_logs.insert_one({
                "user_id": user_id,
                "type": "daily_summary",
                "score": user_data.get("score", 0),
                "message": message[:100],
                "sent_at": datetime.now(timezone.utc),
                "success": True
            })
        else:
            logger.warning(f"❌ Falha ao enviar notificação para usuário {user_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Erro ao enviar notificação para usuário {user_id}: {e}")
        return False


async def send_daily_notifications_to_all_users():
    """
    Envia notificações proativas para TODOS os usuários
    """
    start_time = datetime.now(timezone.utc)
    logger.info("🚀 Iniciando worker de notificações proativas...")
    
    # 🔧 CORRIGIDO: get_database é síncrona (não precisa de await)
    db = get_database()
    
    # Busca todos os usuários com token de notificação e notificações ativas
    users = await db.users.find({
        "expo_push_token": {"$exists": True, "$ne": None},
        "push_enabled": {"$ne": False}  # Se não tiver o campo, considera true
    }).to_list(1000)
    
    total_users = len(users)
    success_count = 0
    error_count = 0
    
    logger.info(f"📊 Encontrados {total_users} usuários com notificações ativas")
    
    for i, user in enumerate(users):
        user_id = str(user["_id"])
        try:
            result = await send_daily_notification(user_id, db)
            if result:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Erro ao processar usuário {user_id}: {e}")
            error_count += 1
        
        # Pequena pausa a cada 10 usuários para não sobrecarregar a API
        if (i + 1) % 10 == 0:
            await asyncio.sleep(1)
    
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"✅ Worker de notificações concluído! {success_count}/{total_users} enviadas em {duration:.2f}s")
    
    return {
        "total_users": total_users,
        "success": success_count,
        "errors": error_count,
        "duration_seconds": round(duration, 2),
        "timestamp": start_time.isoformat()
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


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTE ARQUIVO:
================================================================================
1. Importação corrigida: de app.routes.notifications import send_push_notification
2. Removido await desnecessário do get_database()
3. Adicionada verificação de push_enabled no filtro de usuários
4. Adicionado registro de logs de envio no banco
5. Adicionado fallback de mensagem IA baseado no score
6. Adicionada pausa a cada 10 usuários para não sobrecarregar

⚠️ PENDÊNCIAS PARA PÓS-MVP:
================================================================================
1. Internacionalização (i18n) das mensagens
2. Processamento em lotes (batch) para muitos usuários
3. Fila com Redis para workers distribuídos
4. Dashboard de monitoramento dos workers
5. Retry automático para falhas temporárias

================================================================================
✅ STATUS: PRONTO PARA MVP
================================================================================
"""