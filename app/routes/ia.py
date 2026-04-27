from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from app.services.ia_service import obter_resposta_ia
from app.utils.auth import get_current_user
from app.models.user import UserResponse

router = APIRouter()

# ========== ROTA SIMPLES (mantida por compatibilidade) ==========
class PerguntaRequest(BaseModel):
    prompt_context: str
    pergunta_usuario: str

class RespostaResponse(BaseModel):
    resposta: str

@router.post("/perguntar", response_model=RespostaResponse)
async def perguntar_ia(request: PerguntaRequest):
    try:
        resposta = obter_resposta_ia(request.prompt_context, request.pergunta_usuario)
        return RespostaResponse(resposta=resposta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== ROTA COMPLETA (COM AUTENTICAÇÃO E CONTEXTO) ==========
class ChatRequest(BaseModel):
    pergunta: str
    perfil: Optional[Dict] = None
    score: Optional[int] = None
    resumo_transacoes: Optional[Dict] = None

@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    # ========== 1. INSTRUÇÕES DE SISTEMA (comportamento da IA) ==========
    instrucoes = """
    Você é a Veloria, uma assistente financeira pessoal, amigável, empática e prática.
    
    Regras:
    1. Responda sempre em português claro, com tom de conversa humana (evite respostas muito longas ou técnicas).
    2. Se o usuário fizer uma pergunta fora do contexto financeiro (ex: "qual a capital da França?"), responda educadamente que você é especialista apenas em finanças pessoais e sugira que ele pergunte sobre orçamento, investimentos, economia, dívidas, etc.
    3. Seja positiva e encorajadora, mas realista. Nunca dê conselhos financeiros extremos ou ilegais.
    4. Use os dados do perfil e transações do usuário (fornecidos abaixo) para personalizar a resposta. Exemplo: "Vejo que você tem dívidas, que tal começar por pagar a mais cara primeiro?"
    5. Sempre que possível, dê exemplos práticos e passos acionáveis (ex: "Você pode tentar reduzir gastos com alimentação cozinhando em casa 3 vezes por semana").
    6. Se o usuário pedir conselhos de investimento, informe que você não pode recomendar produtos específicos, mas pode explicar conceitos gerais (risco, liquidez, diversificação).
    7. Mantenha as respostas concisas (máximo 3-4 parágrafos), a menos que o usuário peça mais detalhes.
    """

    # ========== 2. DADOS DO USUÁRIO (contexto estático) ==========
    contexto_dados = f"""
    Perfil do Usuário:
    - Sentimento sobre dinheiro: {request.perfil.get('money_feeling', 'não informado') if request.perfil else 'não informado'}
    - Reação a compras não planejadas: {request.perfil.get('post_purchase', 'não informado') if request.perfil else 'não informado'}
    - Sonho para os próximos 5 anos: {request.perfil.get('dream_5y', 'não informado') if request.perfil else 'não informado'}
    - Reserva de emergência desejada: {request.perfil.get('emergency_target', 'não informado') if request.perfil else 'não informado'}
    - Possui dívidas? {request.perfil.get('has_debt', 'não informado') if request.perfil else 'não informado'}
    - Comportamento com cartão de crédito: {request.perfil.get('credit_card_behavior', 'não informado') if request.perfil else 'não informado'}

    Score financeiro atual: {request.score if request.score is not None else 'não calculado'}

    Resumo das últimas transações (gastos no mês atual):
    - Gastos com Alimentação: R$ {request.resumo_transacoes.get('Alimentacao', 0) if request.resumo_transacoes else 0}
    - Gastos com Transporte: R$ {request.resumo_transacoes.get('Transporte', 0) if request.resumo_transacoes else 0}
    - Gastos com Lazer: R$ {request.resumo_transacoes.get('Lazer', 0) if request.resumo_transacoes else 0}
    - Gastos com Moradia: R$ {request.resumo_transacoes.get('Moradia', 0) if request.resumo_transacoes else 0}
    """

    # ========== 3. SEPARAÇÃO SYSTEM / USER ==========
    system_message = f"{instrucoes}\n\n{contexto_dados}"
    user_message = request.pergunta

    resposta_ia = obter_resposta_ia(system_message, user_message)
    return {"resposta": resposta_ia}