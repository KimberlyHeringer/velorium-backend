"""
Worker de Cálculo de Score Diário
Arquivo: backend/workers/score_worker.py

Funcionalidades:
- Executa diariamente às 03:00
- Recalcula o score financeiro de TODOS os usuários ativos
- Processa em lotes para evitar sobrecarga
- Registra logs de execução para monitoramento
- Internacionalização (i18n) nos logs

Principais features:
- 🔧 NOVO: Internacionalização (i18n) nos logs
- 🔧 NOVO: Constantes configuráveis via .env
- 🔧 NOVO: Filtro de usuários com dados relevantes
- 🔧 NOVO: Pausa entre lotes configurável
- 🔧 NOVO: Redis Queue para processamento distribuído
- 🔧 NOVO: Processamento incremental (apenas usuários com mudanças)
- 🔧 CORRIGIDO: Verificação de db None
- 🔧 CORRIGIDO: Limite de erros registrados (MAX_ERRORS)
- ✅ Processamento em lotes (BATCH_SIZE)
- ✅ Limite de usuários por execução (MAX_USERS_PER_RUN)
- ✅ Registro de execução no banco (worker_logs)
- ✅ Tratamento de erros com detalhamento
- ✅ Versão síncrona para APScheduler

Regra: 2.8 (Logs)
Regra: 3.1 (Score Financeiro - Worker Diário)
Regra: 7.1 (Internacionalização)

🔧 USO:
    # Executar manualmente (para testes)
    from workers.score_worker import run_score_worker_sync
    result = run_score_worker_sync()
    
    # Ou via scheduler (agendado para 03:00)
    # O scheduler chama run_score_worker_sync() automaticamente
    
    # Adicionar usuário à fila Redis
    from workers.score_worker import add_to_score_queue
    await add_to_score_queue("user123")
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.database import get_database
from app.services.score_service import calculate_score
from app.utils.logger import setup_logger
from app.utils.i18n import get_message

logger = setup_logger(__name__)

# ================================================================
# CONSTANTES
# ================================================================

SCORE_BATCH_SIZE = int(os.getenv("SCORE_BATCH_SIZE", "50"))
SCORE_MAX_USERS_PER_RUN = int(os.getenv("SCORE_MAX_USERS_PER_RUN", "10000"))
SCORE_PAUSE_DURATION = float(os.getenv("SCORE_PAUSE_DURATION", "1.0"))
MAX_ERRORS = int(os.getenv("SCORE_MAX_ERRORS", "100"))
SCORE_INCREMENTAL_ENABLED = os.getenv("SCORE_INCREMENTAL_ENABLED", "true").lower() == "true"


# ================================================================
# REDIS CLIENT (CONEXÃO SEGURA)
# ================================================================

try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para fila de score")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - fila de score desabilitada")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - fila de score desabilitada")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")


# ================================================================
# FUNÇÕES DE FILA COM REDIS
# ================================================================

async def add_to_score_queue(user_id: str) -> bool:
    """
    🔧 NOVO: Adiciona um usuário à fila de score no Redis.
    
    🔧 USO:
        await add_to_score_queue("user123")
    
    Args:
        user_id: ID do usuário
    
    Returns:
        bool: True se adicionado com sucesso
    """
    if not redis_client:
        return False
    
    try:
        await redis_client.rpush("score_queue", user_id)
        logger.debug(get_message("SCORE_QUEUE_ADDED", "pt", user_id=user_id))
        return True
    except Exception as e:
        logger.warning(get_message("SCORE_QUEUE_ERROR", "pt", error=str(e)))
        return False


async def process_score_queue() -> dict:
    """
    🔧 NOVO: Processa a fila de score no Redis.
    
    🔧 USO:
        result = await process_score_queue()
        print(result["processed"])
    
    Returns:
        dict: Resumo do processamento
    """
    if not redis_client:
        logger.warning("ℹ️ Redis não disponível para processar fila de score")
        return {"processed": 0, "success": 0, "errors": 0}
    
    db = get_database()
    if db is None:
        logger.error(get_message("SCORE_WORKER_DB_NONE", "pt"))
        return {"processed": 0, "success": 0, "errors": 1, "error": "Database connection failed"}
    
    processed = 0
    success_count = 0
    error_count = 0
    
    logger.info(get_message("SCORE_QUEUE_PROCESSING", "pt"))
    
    while True:
        try:
            # Busca um item da fila (bloqueia por até 5 segundos)
            item = await redis_client.blpop("score_queue", timeout=5)
            if not item:
                break
            
            user_id = item[1]  # item = (queue_name, value)
            processed += 1
            
            # Busca dados do usuário para o email
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            user_email = user.get("email", "unknown") if user else "unknown"
            
            result = await calculate_score_for_user(user_id, user_email, db)
            if result:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            logger.error(get_message("SCORE_QUEUE_PROCESS_ERROR", "pt", error=str(e)))
            error_count += 1
    
    logger.info(get_message("SCORE_QUEUE_DONE", "pt", success=success_count, processed=processed))
    
    return {
        "processed": processed,
        "success": success_count,
        "errors": error_count
    }


async def process_score_queue_forever() -> None:
    """
    🔧 NOVO: Processa a fila de score em loop infinito.
    Para ser usado por workers dedicados.
    """
    logger.info(get_message("SCORE_QUEUE_WORKER_START", "pt"))
    
    while True:
        try:
            result = await process_score_queue()
            if result["processed"] == 0:
                await asyncio.sleep(10)  # Aguarda novos itens
        except Exception as e:
            logger.error(get_message("SCORE_QUEUE_WORKER_ERROR", "pt", error=str(e)))
            await asyncio.sleep(30)


# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================

async def calculate_score_for_user(
    user_id: str,
    user_email: str,
    db
) -> Optional[Dict]:
    """
    Calcula o score para um único usuário.
    
    🔧 USO:
        result = await calculate_score_for_user(user_id, user_email, db)
        if result:
            print(result["score"])
    
    📋 PADRÃO:
        - Logs com i18n
        - Chama calculate_score com source="worker"
        - Retorna None em caso de erro
    
    Args:
        user_id: ID do usuário
        user_email: Email do usuário (para logs)
        db: Conexão com o banco de dados
    
    Returns:
        dict: Resultado do cálculo ou None
    """
    try:
        result = await calculate_score(user_id, db, source="worker")
        score = result.get("score", 0)
        logger.debug(get_message("SCORE_WORKER_USER_SUCCESS", "pt", email=user_email, score=score))
        return result
    except Exception as e:
        logger.error(get_message("SCORE_WORKER_USER_ERROR", "pt", email=user_email, error=str(e)))
        return None


# ================================================================
# FUNÇÕES PRINCIPAIS
# ================================================================

async def calculate_score_for_all_users(
    use_incremental: bool = SCORE_INCREMENTAL_ENABLED
) -> Dict[str, Any]:
    """
    Calcula o score financeiro para todos os usuários ativos.
    Processa em lotes para evitar sobrecarga.
    
    🔧 USO:
        result = await calculate_score_for_all_users()
        print(result["success_count"])
    
    📋 PADRÃO:
        - Logs com i18n
        - 🔧 NOVO: Processamento incremental (apenas usuários com mudanças)
        - 🔧 CORRIGIDO: Verificação de db None
        - 🔧 CORRIGIDO: Limite de erros registrados
        - Processa em lotes com pausa
        - Registra execução no banco
    
    Args:
        use_incremental: Se True, processa apenas usuários com mudanças
    
    Returns:
        Dict com estatísticas da execução
    """
    start_time = datetime.now(timezone.utc)
    logger.info(get_message("SCORE_WORKER_START", "pt"))
    
    # Verificação de db None
    db = get_database()
    if db is None:
        logger.error(get_message("SCORE_WORKER_DB_NONE", "pt"))
        return {
            "total_users": 0,
            "success_count": 0,
            "error_count": 1,
            "duration_seconds": 0,
            "timestamp": start_time.isoformat(),
            "error": "Database connection failed"
        }
    
    # 🔧 NOVO: Busca a última execução para processamento incremental
    last_run = None
    if use_incremental:
        last_run_doc = await db.worker_logs.find_one(
            {"worker": "score"},
            sort=[("executed_at", -1)]
        )
        if last_run_doc:
            last_run = last_run_doc.get("executed_at")
            logger.info(get_message("SCORE_WORKER_INCREMENTAL", "pt", last_run=last_run))
    
    # Filtro base: apenas usuários com dados financeiros
    query = {"has_financial_data": {"$ne": False}}
    
    # 🔧 NOVO: Processamento incremental (apenas mudanças desde a última execução)
    if last_run and use_incremental:
        # Busca usuários que tiveram atividade financeira recente
        active_users = set()
        
        # Usuários com novas transações
        recent_transactions = await db.transactions.distinct(
            "user_id", 
            {"date": {"$gt": last_run}}
        )
        active_users.update(recent_transactions)
        
        # Usuários com novas metas
        recent_goals = await db.goals.distinct(
            "user_id",
            {"created_at": {"$gt": last_run}}
        )
        active_users.update(recent_goals)
        
        # Usuários com novos cartões
        recent_cards = await db.credit_cards.distinct(
            "user_id",
            {"created_at": {"$gt": last_run}}
        )
        active_users.update(recent_cards)
        
        if active_users:
            query["_id"] = {"$in": [ObjectId(u) for u in active_users]}
            logger.info(get_message("SCORE_WORKER_ACTIVE_USERS", "pt", count=len(active_users)))
        else:
            logger.info(get_message("SCORE_WORKER_NO_ACTIVE_USERS", "pt"))
            return {
                "total_users": 0,
                "success_count": 0,
                "error_count": 0,
                "duration_seconds": 0,
                "timestamp": start_time.isoformat(),
                "incremental": True
            }
    
    # Busca usuários
    users = await db.users.find(query).to_list(SCORE_MAX_USERS_PER_RUN)
    total_users = len(users)
    
    if total_users == 0:
        logger.info(get_message("SCORE_WORKER_NO_USERS", "pt"))
        return {
            "total_users": 0,
            "success_count": 0,
            "error_count": 0,
            "duration_seconds": 0,
            "timestamp": start_time.isoformat(),
            "incremental": use_incremental
        }
    
    logger.info(get_message("SCORE_WORKER_USERS", "pt", total=total_users))
    
    success_count = 0
    error_count = 0
    errors_details = []
    
    # Processa em lotes
    for batch_start in range(0, total_users, SCORE_BATCH_SIZE):
        batch_end = min(batch_start + SCORE_BATCH_SIZE, total_users)
        batch = users[batch_start:batch_end]
        
        batch_num = batch_start // SCORE_BATCH_SIZE + 1
        total_batches = (total_users + SCORE_BATCH_SIZE - 1) // SCORE_BATCH_SIZE
        
        logger.info(get_message("SCORE_WORKER_BATCH", "pt", current=batch_num, total=total_batches))
        
        # Processa usuários do lote
        for user in batch:
            user_id = str(user["_id"])
            user_email = user.get("email", "unknown")
            
            result = await calculate_score_for_user(user_id, user_email, db)
            if result:
                success_count += 1
            else:
                error_count += 1
                # Limita o número de erros registrados
                if len(errors_details) < MAX_ERRORS:
                    errors_details.append({
                        "user_id": user_id,
                        "email": user_email,
                        "error": "Falha no cálculo"
                    })
        
        # Pausa entre lotes
        if batch_end < total_users:
            await asyncio.sleep(SCORE_PAUSE_DURATION)
    
    # Log do resultado final
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    result = {
        "total_users": total_users,
        "success_count": success_count,
        "error_count": error_count,
        "duration_seconds": round(duration, 2),
        "timestamp": start_time.isoformat(),
        "incremental": use_incremental,
        "last_run": last_run.isoformat() if last_run else None,
        "errors_details": errors_details if errors_details else None,
        "errors_truncated": error_count > MAX_ERRORS if error_count > 0 else False
    }
    
    logger.info(get_message("SCORE_WORKER_DONE", "pt", success=success_count, total=total_users, duration=round(duration, 2)))
    
    # Registra execução no banco para monitoramento
    try:
        await db.worker_logs.insert_one({
            "worker": "score",
            "result": result,
            "executed_at": start_time
        })
        logger.debug(get_message("SCORE_WORKER_LOGGED", "pt"))
    except Exception as e:
        logger.warning(get_message("SCORE_WORKER_LOG_ERROR", "pt", error=str(e)))
    
    return result


def run_score_worker_sync() -> Optional[dict]:
    """
    Versão síncrona para ser chamada pelo APScheduler.
    
    🔧 USO:
        # Chamado pelo scheduler às 03:00
        result = run_score_worker_sync()
    
    📋 PADRÃO:
        - Executa a versão assíncrona com asyncio.run()
        - Trata erros fatais
        - Logs com i18n
    
    Returns:
        dict: Resumo da execução ou None em caso de erro
    """
    try:
        result = asyncio.run(calculate_score_for_all_users())
        return result
    except Exception as e:
        logger.error(get_message("SCORE_WORKER_FATAL", "pt", error=str(e)))
        import traceback
        logger.debug(traceback.format_exc())
        return None


# ================================================================
# NOTAS DE IMPLEMENTAÇÃO
# ================================================================

"""
📌 COMO USAR:

1. Executar manualmente (para testes):
   from workers.score_worker import run_score_worker_sync
   result = run_score_worker_sync()
   print(result)

2. Verificar logs de execução:
   db.worker_logs.find({"worker": "score"}).sort("executed_at", -1)

3. Configurar via .env:
   SCORE_BATCH_SIZE=100
   SCORE_MAX_USERS_PER_RUN=20000
   SCORE_PAUSE_DURATION=2.0
   SCORE_MAX_ERRORS=50
   SCORE_INCREMENTAL_ENABLED=true

4. Adicionar usuário à fila Redis:
   from workers.score_worker import add_to_score_queue
   await add_to_score_queue("user123")

5. Processar fila (worker dedicado):
   from workers.score_worker import process_score_queue_forever
   await process_score_queue_forever()
"""


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================
#
# ✅ Processamento em lotes (BATCH_SIZE)
# ✅ Limite de usuários por execução (MAX_USERS_PER_RUN)
# ✅ Registro de execução no banco (worker_logs)
# ✅ Tratamento de erros com detalhamento
# ✅ Pausas entre lotes para não sobrecarregar
# ✅ 🔧 NOVO: Internacionalização (i18n) nos logs
# ✅ 🔧 NOVO: Constantes configuráveis via .env
# ✅ 🔧 NOVO: Filtro de usuários com has_financial_data
# ✅ 🔧 NOVO: Redis Queue para processamento distribuído
# ✅ 🔧 NOVO: Processamento incremental (apenas usuários com mudanças)
# ✅ 🔧 CORRIGIDO: Verificação de db None
# ✅ 🔧 CORRIGIDO: Limite de erros registrados (MAX_ERRORS)
# ✅ Versão síncrona para APScheduler
#
# ❌ Não implementado (Pós-MVP):
#   - Monitoramento via Sentry/New Relic
#   - Dashboard visual de status dos workers
#   - Alertas para falhas consecutivas
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado BATCH_SIZE, MAX_USERS_PER_RUN, logs (05/07/2026)
#   - v3: Adicionado i18n, constantes via .env, filtro de usuários (06/07/2026)
#   - v4: Corrigido db None, limite de erros (06/07/2026)
#   - v5: Adicionado Redis Queue, processamento incremental (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO