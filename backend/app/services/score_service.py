"""
Serviço de Cálculo do Score Financeiro
Arquivo: backend/app/services/score_service.py

🔧 MODIFICADO: Regra 2.8 - Usa setup_logger em vez de logging diretamente
🔧 MODIFICADO: Regra 2.11 - Conversão de moeda para centavos (from_cents)
🔧 MODIFICADO: Regra 3.1 - Score Financeiro
- Adicionado parâmetro source para identificar origem do cálculo (user/worker)
- Logs mais detalhados para monitoramento
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Literal
from bson import ObjectId

from app.utils.logger import setup_logger
from app.utils.currency import from_cents

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)


def ensure_timezone(dt):
    """Garante que uma data tenha timezone UTC"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def calculate_score(
    user_id: str,
    db,
    transactions: Optional[List[Dict]] = None,
    profile: Optional[Dict] = None,
    goals: Optional[List[Dict]] = None,
    source: Literal["user", "worker"] = "user",  # 🔧 NOVO: identifica origem
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
    
    Returns:
        Dict com score, detalhes e estatísticas
    """
    log_prefix = f"[{source.upper()}]"
    logger.debug(f"{log_prefix} Iniciando cálculo de score para usuário {user_id}")
    
    # ========== 1. BUSCAR DADOS ==========
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    if transactions is None:
        transactions_cursor = db.transactions.find({
            "user_id": user_id,
            "date": {"$gte": thirty_days_ago}
        })
        transactions = await transactions_cursor.to_list(1000)
    
    # 🔧 REGRA 2.11: converter amount de centavos para reais (float)
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
            logger.warning(f"{log_prefix} Erro ao buscar metas para usuário {user_id}: {e}")
            goals = []
    
    # 🔧 CORREÇÃO: Garantir que todas as metas tenham updated_at com timezone
    for g in goals:
        if "updated_at" in g:
            g["updated_at"] = ensure_timezone(g["updated_at"])
        elif "updatedAt" in g:  # compatibilidade com nome antigo
            g["updated_at"] = ensure_timezone(g["updatedAt"])
        # 🔧 REGRA 2.11: converter target e current de centavos para reais (float)
        if "target" in g:
            g["target"] = from_cents(g["target"])
        if "current" in g:
            g["current"] = from_cents(g["current"])
    
    # ========== 2. PONTOS BASE ==========
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
        "source": source,  # 🔧 NOVO: registra origem no detalhe
    }
    
    # ========== 3. FREQUÊNCIA ==========
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
    
    # ========== 4. CONTROLE FINANCEIRO ==========
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
    
    # 🔧 CORREÇÃO: monthly_income com fallback seguro
    if user_doc:
        renda_mensal = float(user_doc.get("monthly_income", 0.0))
        renda_mensal = round(renda_mensal, 2)
    else:
        logger.warning(f"{log_prefix} Usuário {user_id} não encontrado para cálculo de score")
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
    
    # ========== 5. DÍVIDAS ==========
    tem_divida = profile.get("has_debt") not in (None, "", "nao")
    dividas = -15 if tem_divida else 0
    score += dividas
    details["dividas"] = dividas
    
    # ========== 6. RESERVA DE EMERGÊNCIA ==========
    reserva_alvo = profile.get("emergency_target", "")
    reserva = 10 if reserva_alvo not in (None, "", "nenhuma") else 0
    score += reserva
    details["reserva"] = reserva
    
    # ========== 7. EVOLUÇÃO DE GASTOS ==========
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
    
    # ========== 8. INATIVIDADE ==========
    if transactions:
        ultima_data = None
        for t in transactions:
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
    
    # ========== 9. BÔNUS METAS ==========
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
    
    # ========== 10. VARIAÇÃO DIÁRIA ==========
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
                logger.debug(f"{log_prefix} Variação limitada para usuário {user_id}: {last_score} → {score} (+5 max)")
            elif diff < -5:
                score = last_score - 5
                logger.debug(f"{log_prefix} Variação limitada para usuário {user_id}: {last_score} → {score} (-5 max)")
    
    # ========== 11. LIMITAR SCORE ==========
    score = max(0, min(100, int(round(score))))
    
    # ========== 12. SALVAR HISTÓRICO ==========
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
        logger.debug(f"{log_prefix} Score atualizado para usuário {user_id}: {score}")
    else:
        await db.score_history.insert_one({
            "user_id": user_id,
            "date": now_utc,
            "score": score,
            "details": details,
            "created_at": now_utc,
            "updated_at": now_utc,
        })
        logger.info(f"{log_prefix} Novo registro de score para usuário {user_id}: {score}")
    
    # ========== 13. RETORNAR ==========
    logger.debug(f"{log_prefix} Cálculo de score concluído para usuário {user_id}: {score}")
    return {
        "score": score,
        "lastScore": last_score,
        "lastDate": last_date_str,
        "details": details,
        "transactionsCount": qtd_transacoes,
        "despesasMes": float(despesas_mes),
        "rendaMensal": float(renda_mensal),
    }


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ 🔧 CORREÇÃO: Adicionada função ensure_timezone() para tratar datas sem timezone
# ✅ 🔧 CORREÇÃO: Cálculo de despesas_mes com datas corrigidas
# ✅ 🔧 CORREÇÃO: Cálculo de despesas_mes_anterior com datas corrigidas
# ✅ 🔧 CORREÇÃO: Cálculo de inatividade com datas corrigidas
# ✅ 🔧 CORREÇÃO: Cálculo de metas_recentes com datas corrigidas
# ✅ 🔧 CORREÇÃO: last_date com ensure_timezone
# ✅ Busca do usuário com ObjectId (corrigido)
# ✅ Conversão de renda_mensal para float + round
# ✅ Garantia de float() em todas as somas
# ✅ Adicionado logging (pronto para uso futuro)
#
# 🔧 REGRA 3.1 (NOVO):
# ✅ Adicionado parâmetro source para identificar origem do cálculo
# ✅ Logs com prefixo [USER] ou [WORKER] para monitoramento
# ✅ Campo source salvo no details do score_history
# ✅ Variação ±5 com logs detalhados
#
# 📌 Dívida técnica (pós-MVP):
#    - Cache do score diário (evitar recalcular toda requisição)
#    - Usar agregação do MongoDB em vez de trazer documentos (performance)
#    - Melhorar detecção de inatividade