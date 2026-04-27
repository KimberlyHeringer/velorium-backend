# app/services/score_service.py
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

async def calculate_score(
    user_id: str,
    db,
    transactions: Optional[List[Dict]] = None,
    profile: Optional[Dict] = None,
    goals: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Calcula o score financeiro do usuário seguindo exatamente a mesma lógica do frontend.
    Parâmetros:
        user_id: ID do usuário
        db: instância do MongoDB (para buscar dados se não fornecidos)
        transactions: lista de transações (últimos 30 dias) – opcional
        profile: perfil financeiro – opcional
        goals: lista de metas – opcional
    Retorna:
        dict com score, detalhes, etc.
    """
    # ========== 1. BUSCAR DADOS SE NÃO FORNECIDOS ==========
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    if transactions is None:
        transactions = await db.transactions.find({
            "user_id": user_id,
            "date": {"$gte": thirty_days_ago}
        }).to_list(1000)
    
    if profile is None:
        profile = await db.user_profiles.find_one({"user_id": user_id}) or {}
    
    if goals is None:
        goals = await db.goals.find({"user_id": user_id}).to_list(1000) if "goals" in await db.list_collection_names() else []
    
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
    }
    
    # ========== 3. FREQUÊNCIA (últimos 30 dias) ==========
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
    
    # ========== 4. CONTROLE FINANCEIRO (despesas mês atual / renda mensal) ==========
    today = datetime.now(timezone.utc)
    month_start = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    despesas_mes = sum(
        t["amount"] for t in transactions
        if t["type"] == "expense" and t["date"] >= month_start
    )
    # Buscar renda mensal do usuário (campo monthly_income em User)
    user_doc = await db.users.find_one({"_id": user_id})
    renda_mensal = Decimal(str(user_doc.get("monthly_income", 0))) if user_doc else Decimal("0")
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
    
    # ========== 7. EVOLUÇÃO DE GASTOS (mês atual vs anterior) ==========
    mes_anterior = today.month - 1 if today.month > 1 else 12
    ano_anterior = today.year if today.month > 1 else today.year - 1
    month_prev_start = datetime(ano_anterior, mes_anterior, 1, tzinfo=timezone.utc)
    next_month = month_prev_start.replace(month=mes_anterior+1) if mes_anterior < 12 else datetime(ano_anterior+1, 1, 1, tzinfo=timezone.utc)
    despesas_mes_anterior = sum(
        t["amount"] for t in transactions
        if t["type"] == "expense" and month_prev_start <= t["date"] < next_month
    )
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
        ultima_data = max(t["date"] for t in transactions)
        dias_inativos = (today - ultima_data).days
        inatividade = 0
        if dias_inativos > 15:
            inatividade = -10
        elif dias_inativos > 7:
            inatividade = -5
    else:
        inatividade = -10
    score += inatividade
    details["inatividade"] = inatividade
    
    # ========== 9. BÔNUS METAS CONCLUÍDAS NOS ÚLTIMOS 7 DIAS ==========
    sete_dias_atras = today - timedelta(days=7)
    metas_recentes = [
        g for g in goals
        if g.get("completed") and g.get("updatedAt") and g["updatedAt"] >= sete_dias_atras
    ]
    bonus_metas = min(2, len(metas_recentes) * 0.5)
    score += bonus_metas
    details["bonusMetas"] = bonus_metas
    
    # ========== 10. APLICAÇÃO DA VARIAÇÃO DIÁRIA ==========
    # Busca último score registrado para o usuário
    last_score_doc = await db.score_history.find_one(
        {"user_id": user_id},
        sort=[("date", -1)]
    )
    if last_score_doc:
        last_score = last_score_doc.get("score", 50)
        last_date = last_score_doc.get("date")
        today_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        if last_date and last_date.date() == today_date.date():
            # Mesmo dia – mantém o score do dia (já calculado anteriormente)
            # Na verdade, não deve recalcular no mesmo dia. Vamos retornar o salvo.
            pass
        else:
            diff = score - last_score
            if diff > 5:
                score = last_score + 5
            elif diff < -5:
                score = last_score - 5
    else:
        last_score = None
    
    # ========== 11. LIMITAR ENTRE 0 E 100 ==========
    score = max(0, min(100, int(round(score))))
    
    # ========== 12. SALVAR HISTÓRICO (snapshot diário) ==========
    now_utc = datetime.now(timezone.utc)
    # Se já existe registro para hoje, atualiza; senão insere
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
    else:
        await db.score_history.insert_one({
            "user_id": user_id,
            "date": now_utc,
            "score": score,
            "details": details,
            "created_at": now_utc,
            "updated_at": now_utc,
        })
    
    # ========== 13. RETORNAR RESULTADO ==========
    return {
        "score": score,
        "lastScore": last_score,
        "lastDate": last_score_doc["date"].isoformat() if last_score_doc else None,
        "details": details,
        "transactionsCount": qtd_transacoes,
        "despesasMes": float(despesas_mes),
        "rendaMensal": float(renda_mensal),
    }