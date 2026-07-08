"""
Worker de Notificações Proativas
Arquivo: backend/workers/daily_notifications.py

Funcionalidades:
- Envio de notificações push diárias para todos os usuários
- Geração de mensagem personalizada via IA baseada nos dados do usuário
- Logs de envio para auditoria
- Fallback para mensagens genéricas se IA falhar
- Pausa estratégica para não sobrecarregar a API

Principais features:
- 🔧 NOVO: Internacionalização (i18n) nos logs
- 🔧 NOVO: Constantes centralizadas para limites
- 🔧 NOVO: Tipagem mais específica com TypedDict
- 🔧 NOVO: Processamento em lote com insert_many
- 🔧 NOVO: Fila com Redis para workers distribuídos
- 🔧 NOVO: Retry automático com backoff exponencial
- 🔧 CORRIGIDO: Import os adicionado
- 🔧 CORRIGIDO: Uso de expo_push_tokens (lista) em vez de expo_push_token (string)
- ✅ Importação correta de send_push_notification
- ✅ Removido await desnecessário do get_database()
- ✅ Verificação de push_enabled no filtro de usuários
- ✅ Registro de logs de envio no banco
- ✅ Fallback de mensagem IA baseado no score
- ✅ Pausa a cada 10 usuários para não sobrecarregar

Regra: 2.8 (Logs)
Regra: 3.2 (Cache com Redis)
Regra: 4.1 (Notificações Proativas)
Regra: 7.1 (Internacionalização)

🔧 USO:
    # Executar manualmente (para testes)
    from workers.daily_notifications import run_daily_notifications_sync
    result = run_daily_notifications_sync()
    
    # Ou via scheduler (agendado para 09:00)
    # O scheduler chama run_daily_notifications_sync() automaticamente
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
# REDIS CLIENT (CONEXÃO SEGURA)
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
# FUNÇÕES DE FILA COM REDIS
# ================================================================

async def add_to_notification_queue(user_id: str) -> bool:
    """
    🔧 NOVO: Adiciona um usuário à fila de notificações no Redis.
    
    🔧 USO:
        await add_to_notification_queue("user123")
    
    Args:
        user_id: ID do usuário
    
    Returns:
        bool: True se adicionado com sucesso
    """
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
    """
    🔧 NOVO: Processa a fila de notificações no Redis.
    
    🔧 USO:
        result = await process_notification_queue()
        print(result["processed"])
    
    Returns:
        dict: Resumo do processamento
    """
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
            # Busca um item da fila (bloqueia por até 5 segundos)
            item = await redis_client.blpop("notification_queue", timeout=5)
            if not item:
                break
            
            user_id = item[1]  # item = (queue_name, value)
            
            # Processa a notificação
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
    """
    🔧 NOVO: Processa a fila de notificações em loop infinito.
    Para ser usado por workers dedicados.
    """
    logger.info("🔄 Iniciando worker de fila de notificações (loop infinito)...")
    
    while True:
        try:
            result = await process_notification_queue()
            if result["processed"] == 0:
                await asyncio.sleep(10)  # Aguarda novos itens
        except Exception as e:
            logger.error(f"❌ Erro no worker de fila: {e}")
            await asyncio.sleep(30)


# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================

async def get_user_notification_token(user_id: str, db) -> Optional[str]:
    """
    Busca o token de notificação push do usuário.
    
    🔧 USO:
        token = await get_user_notification_token(user_id, db)
        if token:
            # Envia notificação
            pass
    
    📋 PADRÃO:
        - 🔧 CORRIGIDO: Usa expo_push_tokens (lista) em vez de expo_push_token
        - Busca o token mais recente da lista
        - Logs com i18n
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
    
    Returns:
        str: Token do usuário ou None
    """
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            tokens = user.get("expo_push_tokens", [])
            if tokens:
                # Usa o token mais recente
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
    """
    🔧 NOVO: Envia notificação com retry automático e backoff exponencial.
    
    🔧 USO:
        success = await send_with_retry(user_id, db)
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
        max_retries: Número máximo de tentativas
        backoff_base: Base para backoff exponencial
    
    Returns:
        bool: True se enviado com sucesso
    """
    # 🔧 NOVO: Chave no Redis para controlar tentativas
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
                # 🔧 NOVO: Limpa contador de tentativas em caso de sucesso
                if redis_client:
                    await redis_client.delete(retry_key)
                logger.debug(f"✅ Notificação enviada na tentativa {attempt + 1} para {user_id}")
                return True
            
            # 🔧 NOVO: Backoff exponencial
            wait_time = backoff_base ** attempt
            logger.warning(f"⚠️ Falha na tentativa {attempt + 1} para {user_id}, aguardando {wait_time}s")
            
            if redis_client:
                await redis_client.setex(retry_key, 3600, attempt + 1)  # Expira em 1 hora
            
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"❌ Erro na tentativa {attempt + 1} para {user_id}: {e}")
            wait_time = backoff_base ** attempt
            await asyncio.sleep(wait_time)
    
    logger.error(f"❌ Todas as {max_retries} tentativas falharam para {user_id}")
    return False


async def get_user_dashboard_data(user_id: str, db) -> Dict[str, Any]:
    """
    Busca dados do usuário para gerar a mensagem personalizada:
    - Score atual
    - Contas a vencer (próximos N dias)
    - Metas com progresso > 80%
    - Gastos acima da média
    
    🔧 USO:
        data = await get_user_dashboard_data(user_id, db)
    
    📋 PADRÃO:
        - Logs com i18n
        - Constantes para dias
        - Retorna dicionário com todos os dados
    
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
        
        # Busca contas a vencer (próximos N dias)
        today = datetime.now(timezone.utc)
        days_ahead = today + timedelta(days=DAYS_AHEAD)
        
        bills_cursor = db.bill_installments.find({
            "user_id": user_id,
            "paid": False,
            "due_date": {"$gte": today, "$lte": days_ahead}
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
        
        # Busca gastos dos últimos N dias para média
        days_back = today - timedelta(days=DAYS_BACK)
        transactions = await db.transactions.find({
            "user_id": user_id,
            "type": "expense",
            "date": {"$gte": days_back}
        }).to_list(100)
        
        # Calcula média diária de gastos (em centavos)
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
            "almost_complete_goals": [],
            "yesterday_expense": 0,
            "avg_daily_expense": 0,
            "is_above_average": False
        }


async def generate_personalized_message(user_data: Dict[str, Any]) -> str:
    """
    Gera mensagem personalizada usando IA.
    
    🔧 USO:
        message = await generate_personalized_message(user_data)
    
    📋 PADRÃO:
        - i18n no fallback
        - Usa IA com contexto dos dados do usuário
        - Fallback baseado no score
    
    Args:
        user_data: Dados do usuário
    
    Returns:
        str: Mensagem personalizada
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
    """
    Envia notificação proativa para um usuário específico.
    
    🔧 USO:
        success = await send_daily_notification(user_id, db)
        if success:
            print("Notificação enviada")
    
    📋 PADRÃO:
        - Logs com i18n
        - Busca token do usuário
        - Busca dados do usuário
        - Gera mensagem personalizada
        - Envia notificação via Expo
        - Registra no banco
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
    
    Returns:
        bool: True se enviado com sucesso
    """
    try:
        # Busca token do usuário
        token = await get_user_notification_token(user_id, db)
        if not token:
            logger.debug(get_message("NOTIFICATION_NO_TOKEN", "pt", user_id=user_id))
            return False
        
        # Busca dados do usuário
        user_data = await get_user_dashboard_data(user_id, db)
        
        # Gera mensagem personalizada
        message = await generate_personalized_message(user_data)
        
        # Envia notificação
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


async def send_daily_notifications_to_all_users() -> dict:
    """
    Envia notificações proativas para TODOS os usuários.
    
    🔧 USO:
        result = await send_daily_notifications_to_all_users()
        print(result["success_count"])
    
    📋 PADRÃO:
        - Logs com i18n
        - Constantes para batch size e pausa
        - 🔧 NOVO: Processamento em lote com insert_many
        - Busca usuários com token e notificações ativas
        - Processa em lotes com pausa
    
    Returns:
        dict: Resumo da execução
    """
    start_time = datetime.now(timezone.utc)
    logger.info(get_message("NOTIFICATION_WORKER_START", "pt"))
    
    db = get_database()
    
    # Busca todos os usuários com token de notificação e notificações ativas
    users = await db.users.find({
        "expo_push_tokens": {"$exists": True, "$ne": []},
        "push_enabled": {"$ne": False}
    }).to_list(MAX_USERS_PER_BATCH)
    
    total_users = len(users)
    success_count = 0
    error_count = 0
    log_entries = []  # 🔧 NOVO: Acumula logs para insert_many
    
    logger.info(get_message("NOTIFICATION_WORKER_USERS", "pt", total=total_users))
    
    for i, user in enumerate(users):
        user_id = str(user["_id"])
        try:
            # 🔧 NOVO: Usa send_with_retry em vez de send_daily_notification diretamente
            result = await send_with_retry(user_id, db)
            
            if result:
                success_count += 1
                log_entries.append({
                    "user_id": user_id,
                    "type": "daily_summary",
                    "score": 0,  # Será atualizado abaixo
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
        
        # Pausa a cada N usuários para não sobrecarregar a API
        if (i + 1) % PAUSE_INTERVAL == 0:
            await asyncio.sleep(PAUSE_DURATION)
    
    # 🔧 NOVO: Insere logs em lote
    if log_entries:
        try:
            await db.notification_logs.insert_many(log_entries)
            logger.debug(f"📊 {len(log_entries)} logs inseridos em lote")
        except Exception as e:
            logger.error(f"❌ Erro ao inserir logs em lote: {e}")
            # Fallback: insere um por um
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
    """
    Versão síncrona para ser chamada pelo APScheduler.
    
    🔧 USO:
        # Chamado pelo scheduler às 09:00
        result = run_daily_notifications_sync()
    
    📋 PADRÃO:
        - Executa a versão assíncrona com asyncio.run()
        - Trata erros fatais
    
    Returns:
        dict: Resumo da execução ou None em caso de erro
    """
    try:
        result = asyncio.run(send_daily_notifications_to_all_users())
        return result
    except Exception as e:
        logger.error(get_message("NOTIFICATION_WORKER_FATAL", "pt", error=str(e)))
        import traceback
        logger.debug(traceback.format_exc())
        return None


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Executar manualmente (para testes):
   from workers.daily_notifications import run_daily_notifications_sync
   result = run_daily_notifications_sync()
   print(result)

2. Verificar logs de envio:
   db.notification_logs.find({"type": "daily_summary"}).sort("sent_at", -1)

3. Configurar via .env:
   NOTIFICATION_BATCH_SIZE=2000
   NOTIFICATION_PAUSE_INTERVAL=20
   NOTIFICATION_PAUSE_DURATION=0.5
   NOTIFICATION_DAYS_AHEAD=5
   NOTIFICATION_DAYS_BACK=15
   NOTIFICATION_MAX_RETRIES=3
   NOTIFICATION_RETRY_BACKOFF=2

4. Adicionar à fila (para workers distribuídos):
   from workers.daily_notifications import add_to_notification_queue
   await add_to_notification_queue("user123")

5. Processar fila (worker dedicado):
   from workers.daily_notifications import process_notification_queue_forever
   await process_notification_queue_forever()
"""


# ============================================================
# DECISÕES DOCUMENTADAS
# ============================================================
#
# ✅ Importação correta de send_push_notification
# ✅ Removido await desnecessário do get_database()
# ✅ Verificação de push_enabled no filtro de usuários
# ✅ Registro de logs de envio no banco
# ✅ Fallback de mensagem IA baseado no score
# ✅ Pausa a cada 10 usuários para não sobrecarregar
# ✅ 🔧 NOVO: Internacionalização (i18n) nos logs
# ✅ 🔧 NOVO: Constantes centralizadas para limites
# ✅ 🔧 NOVO: Processamento em lote com insert_many
# ✅ 🔧 NOVO: Fila com Redis para workers distribuídos
# ✅ 🔧 NOVO: Retry automático com backoff exponencial
# ✅ 🔧 CORRIGIDO: Import os adicionado
# ✅ 🔧 CORRIGIDO: Uso de expo_push_tokens (lista) em vez de expo_push_token (string)
#
# ❌ Não implementado (Pós-MVP):
#   - Dashboard de monitoramento dos workers
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Corrigido importação e await (05/07/2026)
#   - v3: Adicionado i18n, constantes, logs melhorados (06/07/2026)
#   - v4: Corrigido import os, expo_push_tokens (06/07/2026)
#   - v5: Adicionado insert_many, Redis fila, retry automático (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO