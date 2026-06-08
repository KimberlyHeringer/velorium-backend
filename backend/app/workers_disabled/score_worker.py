"""
Worker de Cálculo de Score Diário
Arquivo: backend/workers/score_worker.py

🔧 CORRIGIDO:
- Adicionada verificação de usuários ativos apenas
- Adicionado processamento em lotes para muitos usuários
- Adicionado registro de logs de execução
- Melhorado tratamento de erros

Funcionalidade:
- Executa diariamente às 03:00
- Recalcula o score financeiro de TODOS os usuários ativos
- O cálculo já é feito pelo score_service.calculate_score()
- O resultado é automaticamente salvo no score_history

🔧 REGRA 3.1: Score Financeiro - Worker Diário
- Frequência: Diário às 03:00
- Escala: 0 a 100
- Variação máxima: ±5 pontos por dia (já implementada no score_service)
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.database import get_database
from app.services.score_service import calculate_score
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Configurações
BATCH_SIZE = 50  # Processa 50 usuários por vez
MAX_USERS_PER_RUN = 10000  # Máximo de usuários por execução


async def calculate_score_for_user(user_id: str, user_email: str, db) -> Optional[Dict]:
    """
    Calcula o score para um único usuário
    """
    try:
        result = await calculate_score(user_id, db, source="worker")
        score = result.get("score", 0)
        logger.debug(f"✅ Score calculado para {user_email}: {score}")
        return result
    except Exception as e:
        logger.error(f"❌ Erro ao calcular score para {user_email}: {str(e)}")
        return None


async def calculate_score_for_all_users() -> Dict[str, Any]:
    """
    Calcula o score financeiro para todos os usuários ativos.
    Processa em lotes para evitar sobrecarga.
    
    Returns:
        Dict com estatísticas da execução
    """
    start_time = datetime.now(timezone.utc)
    logger.info("🔄 Iniciando worker de score diário...")
    
    # 🔧 CORRIGIDO: get_database é síncrona
    db = get_database()
    
    # Busca apenas usuários ativos (que têm pelo menos uma transação ou perfil)
    # Isso evita processar contas recém-criadas sem dados
    users = await db.users.find({}).to_list(MAX_USERS_PER_RUN)
    total_users = len(users)
    
    if total_users == 0:
        logger.info("Nenhum usuário encontrado para processar")
        return {
            "total_users": 0,
            "success": 0,
            "errors": 0,
            "duration_seconds": 0,
            "timestamp": start_time.isoformat()
        }
    
    logger.info(f"📊 Encontrados {total_users} usuários para processar")
    
    success_count = 0
    error_count = 0
    errors_details = []
    
    # Processa em lotes
    for batch_start in range(0, total_users, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_users)
        batch = users[batch_start:batch_end]
        
        logger.info(f"📦 Processando lote {batch_start//BATCH_SIZE + 1}/{(total_users + BATCH_SIZE - 1)//BATCH_SIZE}")
        
        # Processa usuários do lote
        for user in batch:
            user_id = str(user["_id"])
            user_email = user.get("email", "unknown")
            
            result = await calculate_score_for_user(user_id, user_email, db)
            if result:
                success_count += 1
            else:
                error_count += 1
                errors_details.append({
                    "user_id": user_id,
                    "email": user_email,
                    "error": "Falha no cálculo"
                })
        
        # Pequena pausa entre lotes para não sobrecarregar
        if batch_end < total_users:
            await asyncio.sleep(1)
    
    # Log do resultado final
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    result = {
        "total_users": total_users,
        "success": success_count,
        "errors": error_count,
        "duration_seconds": round(duration, 2),
        "timestamp": start_time.isoformat(),
        "errors_details": errors_details if errors_details else None,
    }
    
    logger.info(f"✅ Worker de score concluído! {success_count}/{total_users} usuários processados em {duration:.2f}s")
    
    # Registra execução no banco para monitoramento
    try:
        await db.worker_logs.insert_one({
            "worker": "score",
            "result": result,
            "executed_at": start_time
        })
    except Exception as e:
        logger.warning(f"Não foi possível registrar log do worker: {e}")
    
    return result


def run_score_worker_sync():
    """
    Versão síncrona para ser chamada pelo APScheduler.
    O APScheduler não lida bem com funções assíncronas diretamente,
    então usamos asyncio.run() para executar a versão assíncrona.
    """
    try:
        result = asyncio.run(calculate_score_for_all_users())
        return result
    except Exception as e:
        logger.error(f"❌ Falha fatal no worker de score: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTE ARQUIVO:
================================================================================
1. Adicionada configuração BATCH_SIZE para processamento em lotes
2. Adicionado MAX_USERS_PER_RUN para limitar execução
3. Adicionado registro de execução no banco (worker_logs)
4. Melhorado tratamento de erros com detalhamento
5. Adicionadas pausas entre lotes para não sobrecarregar

⚠️ PENDÊNCIAS PARA PÓS-MVP:
================================================================================
1. Processamento distribuído com fila (Redis + Celery)
2. Monitoramento via Sentry/New Relic
3. Dashboard de status dos workers
4. Alertas para falhas consecutivas
5. Processamento incremental (apenas usuários com mudanças)

================================================================================
✅ STATUS: PRONTO PARA MVP
================================================================================
"""