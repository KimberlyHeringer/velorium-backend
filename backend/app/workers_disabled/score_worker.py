"""
Worker de Cálculo de Score Diário
Arquivo: backend/workers/score_worker.py

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
from typing import List, Dict, Any

from app.database import get_database
from app.services.score_service import calculate_score
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


async def calculate_score_for_all_users() -> Dict[str, Any]:
    """
    Calcula o score financeiro para todos os usuários ativos.
    
    Returns:
        Dict com estatísticas da execução:
        - total_users: número total de usuários processados
        - success: quantos tiveram score calculado com sucesso
        - errors: quantos falharam
        - duration: tempo total de execução (segundos)
    """
    start_time = datetime.now(timezone.utc)
    logger.info("🔄 Iniciando worker de score diário...")
    
    db = await get_database()
    
    # Busca todos os usuários ativos
    users = await db.users.find({}).to_list(None)
    total_users = len(users)
    success_count = 0
    error_count = 0
    errors_details = []
    
    logger.info(f"📊 Encontrados {total_users} usuários para processar")
    
    for user in users:
        user_id = str(user["_id"])
        user_email = user.get("email", "unknown")
        
        try:
            # 🔧 O calculate_score já salva automaticamente no score_history
            result = await calculate_score(user_id, db)
            score = result.get("score", 0)
            success_count += 1
            logger.debug(f"✅ Score calculado para {user_email}: {score}")
            
        except Exception as e:
            error_count += 1
            error_msg = f"❌ Erro ao calcular score para {user_email}: {str(e)}"
            logger.error(error_msg)
            errors_details.append({"user_id": user_id, "email": user_email, "error": str(e)})
    
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


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Usa asyncio.run() para compatibilidade com APScheduler
# ✅ Logs detalhados de cada usuário processado
# ✅ Estatísticas de execução (tempo, sucessos, erros)
# ✅ Captura e log de erros individuais (não interrompe o lote)
# ✅ Compatível com a estrutura existente do calculate_score
#
# 📌 Melhorias futuras (pós-MVP):
#    - Processamento em lotes (batch) para muitos usuários
#    - Fila com Redis para workers distribuídos
#    - Monitoramento via Sentry/New Relic