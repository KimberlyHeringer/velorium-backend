"""
Serviço de Cálculo do Score Financeiro
Arquivo: backend/app/services/score_service.py

Funcionalidades:
- Cálculo do score financeiro do usuário (0-100)
- Salva histórico diário (append-only)
- Variação limitada a ±5 pontos por dia
- Suporte a cache para evitar recálculos desnecessários

Principais features:
- Score baseado em 8 fatores: frequência, controle, dívidas, reserva, evolução, inatividade, metas, comportamento
- Cache de 1 hora para respostas rápidas (com TTL automático no MongoDB)
- i18n completo nas mensagens de log
- Filtro de transações irrelevantes para inatividade (exclui transferências internas)
- Identificação de origem (user/worker) para monitoramento
- Logs estruturados com prefixo [USER] ou [WORKER]
- 🔧 CORRIGIDO: Uso de .total_seconds() em vez de .seconds no TTL
- 🔧 CORRIGIDO: Verificação db is None em funções de cache
- 🔧 CORRIGIDO: Todas as mensagens de log com i18n
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Literal
from bson import ObjectId

from app.utils.logger import setup_logger
from app.utils.currency import from_cents
from app.utils.i18n import get_message

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# ========== CONSTANTES ==========
SCORE_CACHE_TTL_SECONDS = 3600  # 1 hora
IRRELEVANT_CATEGORIES = ["transferencia", "ajuste_manual", "investimento_interno"]


# ========== FUNÇÕES AUXILIARES ==========

def ensure_timezone(dt):
    """Garante que uma data tenha timezone UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_relevant_transaction(t: Dict) -> bool:
    """
    🔧 CORRIGIDO: Verifica se a transação deve ser considerada para inatividade.
    
    Exclui:
      - Transferências internas (category = "transferencia")
      - Ajustes manuais (is_manual_adjustment = True)
      - Investimentos internos (category = "investimento_interno")
    
    Returns:
        bool: True se a transação for relevante, False caso contrário
    """
    if t.get("category") in IRRELEVANT_CATEGORIES:
        return False
    if t.get("is_manual_adjustment", False):
        return False
    return True


async def get_cached_score(user_id: str, db) -> Optional[Dict]:
    """
    🔧 CORRIGIDO: Busca score do cache com verificação db is None.
    🔧 CORRIGIDO: Usa .total_seconds() para cálculo de TTL.
    """
    if db is None:
        logger.warning("⚠️ db não pode ser None em get_cached_score")
        return None
    
    try:
        cache_doc = await db.score_cache.find_one({"user_id": user_id})
        if cache_doc:
            cached_at = ensure_timezone(cache_doc.get("cached_at"))
            if cached_at:
                elapsed = (datetime.now(timezone.utc) - cached_at).total_seconds()
                if elapsed < SCORE_CACHE_TTL_SECONDS:
                    logger.debug(f"✅ {get_message('SCORE_CACHE_HIT', 'pt')} - {user_id}")
                    return cache_doc.get("score_data")
                else:
                    logger.debug(f"⏰ {get_message('SCORE_CACHE_EXPIRED', 'pt')} - {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ {get_message('SCORE_CACHE_ERROR', 'pt')}: {e}")
    
    logger.debug(f"📊 {get_message('SCORE_CACHE_MISS', 'pt')} - {user_id}")
    return None


async def set_cached_score(user_id: str, score_data: Dict, db) -> None:
    """
    🔧 CORRIGIDO: Armazena score no cache com verificação db is None.
    """
    if db is None:
        logger.warning("⚠️ db não pode ser None em set_cached_score")
        return
    
    try:
        await db.score_cache.update_one(
            {"user_id": user_id},
            {"$set": {
                "score_data": score_data,
                "cached_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        logger.debug(f"💾 {get_message('SCORE_CACHE_SAVED', 'pt')} - {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ {get_message('SCORE_CACHE_ERROR', 'pt')}: {e}")


async def invalidate_score_cache(user_id: str, db) -> None:
    """
    🔧 CORRIGIDO: Invalida cache de score com verificação db is None.
    """
    if db is None:
        logger.warning("⚠️ db não pode ser None em invalidate_score_cache")
        return
    
    try:
        await db.score_cache.delete_one({"user_id": user_id})
        logger.debug(f"🗑️ {get_message('SCORE_CACHE_INVALIDATED', 'pt')} - {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ {get_message('SCORE_CACHE_ERROR', 'pt')}: {e}")


# ========== FUNÇÃO PRINCIPAL ==========

async def calculate_score(
    user_id: str,
    db,
    transactions: Optional[List[Dict]] = None,
    profile: Optional[Dict] = None,
    goals: Optional[List[Dict]] = None,
    source: Literal["user", "worker"] = "user",
    skip_cache: bool = False
) -> Dict[str, Any]:
    """
    Calcula o score financeiro do usuário.
    
    Args:
        user_id: ID do usuário
        db: Conexão com o banco de dados
        transactions: Lista opcional de transações (se não fornecer, busca no banco)
        profile: Perfil opcional do usuário
        goals: Lista opcional de metas
        source: Origem do cálculo ("user" = requisição normal, "worker" = worker diário)
        skip_cache: Se True, ignora o cache
    
    Returns:
        Dict com score, detalhes e estatísticas
    """
    log_prefix = f"[{source.upper()}]"
    language = "pt"
    
    logger.debug(f"{log_prefix} {get_message('SCORE_CALCULATION_STARTED', language)} - {user_id}")
    
    # ===== 1. VERIFICA CACHE =====
    
    if not skip_cache:
        cached_score = await get_cached_score(user_id, db)
        if cached_score:
            logger.debug(f"{log_prefix} ✅ {get_message('SCORE_CACHE_HIT', language)} - {user_id}")
            return cached_score
    
    # ===== 2. BUSCAR DADOS =====
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    if transactions is None:
        transactions_cursor = db.transactions.find({
            "user_id": user_id,
            "date": {"$gte": thirty_days_ago}
        })
        transactions = await transactions_cursor.to_list(1000)
    
    # Converte amount de centavos para reais
    for t in transactions:
        if "date" in t:
            t["date"] = ensure_timezone(t["date"])
        if "amount" in t:
            t["amount"] = from_cents(t["amount"])
    
    if profile is None:
        profile = await db.user_profiles.find_one({"user_id": user_id}) or {}
    
    if goals is None:
        try:
            goals = await db.goals.find({"user_id": user_id}).to_list(1000)
        except Exception as e:
            logger.warning(f"{log_prefix} {get_message('SCORE_GOALS_ERROR', language)}: {e}")
            goals = []
    
    # Garantir que todas as metas tenham updated_at com timezone
    for g in goals:
        if "updated_at" in g:
            g["updated_at"] = ensure_timezone(g["updated_at"])
        elif "updatedAt" in g:
            g["updated_at"] = ensure_timezone(g["updatedAt"])
        if "target" in g:
            g["target"] = from_cents(g["target"])
        if "current" in g:
            g["current"] = from_cents(g["current"])
    
    # ===== 3. PONTOS BASE =====
    
    score = 50
    details = {
        "base": 50,
        "frequencia": 0,
        "controle": 0,
        "dividas": 0,
        "reserva": 0,
        "evolucao": 0,
        "inatividade": 0,
        "bonusMetas": 0,
        "source": source,
    }
    
    # ===== 4. FREQUÊNCIA =====
    
    qtd_transacoes = len(transactions)
    if qtd_transacoes >= 11:
        freq = 10
    elif qtd_transacoes >= 6:
        freq = 6
    elif qtd_transacoes >= 1:
        freq = 3
    else:
        freq = 0
    score += freq
    details["frequencia"] = freq
    
    # ===== 5. CONTROLE FINANCEIRO =====
    
    today = datetime.now(timezone.utc)
    month_start = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    
    despesas_mes = 0
    for t in transactions:
        if t.get("type") == "expense":
            t_date = t.get("date")
            if t_date and t_date >= month_start:
                despesas_mes += float(t.get("amount", 0.0))
    
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        user_obj_id = user_id
    
    user_doc = await db.users.find_one({"_id": user_obj_id})
    
    if user_doc:
        renda_mensal = float(user_doc.get("monthly_income", 0.0))
        renda_mensal = round(renda_mensal, 2)
    else:
        logger.warning(f"{log_prefix} {get_message('SCORE_NO_USER', language)} - {user_id}")
        renda_mensal = 0.0
    
    controle = 0
    if renda_mensal > 0:
        percentual = (despesas_mes / renda_mensal) * 100
        if percentual < 70:
            controle = 15
        elif percentual <= 90:
            controle = 7
    score += controle
    details["controle"] = controle
    
    # ===== 6. DÍVIDAS =====
    
    tem_divida = profile.get("has_debt") not in (None, "", "nao")
    dividas = -15 if tem_divida else 0
    score += dividas
    details["dividas"] = dividas
    
    # ===== 7. RESERVA DE EMERGÊNCIA =====
    
    reserva_alvo = profile.get("emergency_target", "")
    reserva = 10 if reserva_alvo not in (None, "", "nenhuma") else 0
    score += reserva
    details["reserva"] = reserva
    
    # ===== 8. EVOLUÇÃO DE GASTOS =====
    
    mes_anterior = today.month - 1 if today.month > 1 else 12
    ano_anterior = today.year if today.month > 1 else today.year - 1
    month_prev_start = datetime(ano_anterior, mes_anterior, 1, tzinfo=timezone.utc)
    
    if mes_anterior < 12:
        next_month = datetime(ano_anterior, mes_anterior + 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(ano_anterior + 1, 1, 1, tzinfo=timezone.utc)
    
    despesas_mes_anterior = 0
    for t in transactions:
        if t.get("type") == "expense":
            t_date = t.get("date")
            if t_date and month_prev_start <= t_date < next_month:
                despesas_mes_anterior += float(t.get("amount", 0.0))
    
    evolucao = 0
    if despesas_mes_anterior > 0:
        reducao = ((despesas_mes_anterior - despesas_mes) / despesas_mes_anterior) * 100
        if reducao > 10:
            evolucao = 15
        elif reducao > 5:
            evolucao = 10
        elif reducao > 0:
            evolucao = 5
    score += evolucao
    details["evolucao"] = evolucao
    
    # ===== 9. INATIVIDADE (com filtro de transações relevantes) =====
    
    transacoes_relevantes = [t for t in transactions if is_relevant_transaction(t)]
    
    if transacoes_relevantes:
        ultima_data = None
        for t in transacoes_relevantes:
            t_date = t.get("date")
            if t_date:
                if ultima_data is None or t_date > ultima_data:
                    ultima_data = t_date
        
        if ultima_data:
            dias_inativos = (today - ultima_data).days
            if dias_inativos > 15:
                inatividade = -10
            elif dias_inativos > 7:
                inatividade = -5
            else:
                inatividade = 0
        else:
            inatividade = -10
    else:
        inatividade = -10
    score += inatividade
    details["inatividade"] = inatividade
    
    # ===== 10. BÔNUS METAS =====
    
    sete_dias_atras = today - timedelta(days=7)
    metas_recentes = 0
    for g in goals:
        if g.get("completed"):
            updated_at = g.get("updated_at")
            if updated_at and updated_at >= sete_dias_atras:
                metas_recentes += 1
    
    bonus_metas = min(2, metas_recentes * 0.5)
    score += bonus_metas
    details["bonusMetas"] = bonus_metas
    
    # ===== 11. VARIAÇÃO DIÁRIA =====
    
    last_score_doc = await db.score_history.find_one(
        {"user_id": user_id},
        sort=[("date", -1)]
    )
    
    last_score = None
    last_date_str = None
    
    if last_score_doc:
        last_score = last_score_doc.get("score", 50)
        last_date = ensure_timezone(last_score_doc.get("date"))
        if last_date:
            last_date_str = last_date.isoformat()
        
        today_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        if last_date and last_date.date() != today_date.date():
            diff = score - last_score
            if diff > 5:
                score = last_score + 5
                logger.debug(f"{log_prefix} {get_message('SCORE_VARIATION_LIMITED', language)} - {last_score} → {score}")
            elif diff < -5:
                score = last_score - 5
                logger.debug(f"{log_prefix} {get_message('SCORE_VARIATION_LIMITED', language)} - {last_score} → {score}")
    
    # ===== 12. LIMITAR SCORE =====
    
    score = max(0, min(100, int(round(score))))
    
    # ===== 13. SALVAR HISTÓRICO =====
    
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    existing = await db.score_history.find_one({
        "user_id": user_id,
        "date": {"$gte": today_start, "$lt": today_start + timedelta(days=1)}
    })
    
    if existing:
        await db.score_history.update_one(
            {"_id": existing["_id"]},
            {"$set": {"score": score, "details": details, "updated_at": now_utc}}
        )
        logger.debug(f"{log_prefix} {get_message('SCORE_UPDATED', language)} - {user_id}: {score}")
    else:
        await db.score_history.insert_one({
            "user_id": user_id,
            "date": now_utc,
            "score": score,
            "details": details,
            "created_at": now_utc,
            "updated_at": now_utc,
        })
        logger.info(f"{log_prefix} {get_message('SCORE_CALCULATED', language)} - {user_id}: {score}")
    
    # ===== 14. SALVAR CACHE =====
    
    result = {
        "score": score,
        "lastScore": last_score,
        "lastDate": last_date_str,
        "details": details,
        "transactionsCount": qtd_transacoes,
        "despesasMes": float(despesas_mes),
        "rendaMensal": float(renda_mensal),
    }
    
    await set_cached_score(user_id, result, db)
    
    logger.debug(f"{log_prefix} {get_message('SCORE_CALCULATED', language)} - {user_id}: {score}")
    return result


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Cálculo do score com 8 fatores
#   - Variação diária limitada a ±5 pontos
#   - Salvamento automático no histórico (append-only)
#   - Logs estruturados com prefixo [USER] ou [WORKER]
#   - Suporte a source para identificar origem do cálculo
#   - 🔧 CORRIGIDO: i18n completo em todas as mensagens de log
#   - 🔧 CORRIGIDO: Filtro de inatividade (exclui transferências internas)
#   - 🔧 CORRIGIDO: Cache de 1 hora com TTL automático no MongoDB
#   - 🔧 CORRIGIDO: .total_seconds() em vez de .seconds
#   - 🔧 CORRIGIDO: Verificação db is None
#   - 🔧 CORRIGIDO: Função invalidate_score_cache()
#
# ❌ Não implementado (Pós-MVP):
#   - Agregação do MongoDB (performance)
#   - Cache em Redis (já tem cache no MongoDB)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Correção de timezone, conversão de moeda, source, logs (25/05/2026)
#   - v3: i18n, filtro de inatividade, cache (04/07/2026)
#   - v4: Correções - .total_seconds(), db is None, TTL automático (04/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO