from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# Importações dos seus serviços e autenticação
from app.services.ia_service import obter_resposta_ia
from app.utils.auth import get_current_user
from app.models.user import UserResponse

router = APIRouter(prefix="/ia", tags=["Inteligência Artificial"])

# Define o formato da requisição que o frontend deve enviar
class ChatRequest(BaseModel):
    pergunta: str
    # Dados do usuário que serão enviados pelo frontend
    perfil: Optional[dict] = None
    score: Optional[int] = None
    resumo_transacoes: Optional[dict] = None

@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Recebe uma pergunta do usuário, monta um contexto personalizado com seu perfil,
    score e transações, e usa a IA para gerar uma resposta financeira.
    """
    # 1. Montar o prompt de contexto com as informações do usuário
    contexto = f"""
        Perfil do Usuário:
        - Sentimento sobre dinheiro: {request.perfil.get('money_feeling', 'não informado')}
        - Reação a compras não planejadas: {request.perfil.get('post_purchase', 'não informado')}
        - Sonho para os próximos 5 anos: {request.perfil.get('dream_5y', 'não informado')}
        - Reserva de emergência desejada: {request.perfil.get('emergency_target', 'não informado')}
        - Possui dívidas? {request.perfil.get('has_debt', 'não informado')}
        - Comportamento com cartão de crédito: {request.perfil.get('credit_card_behavior', 'não informado')}

        Score financeiro atual: {request.score}

        Resumo das últimas transações:
        - Gastos com Alimentação: R$ {request.resumo_transacoes.get('Alimentação', 0)}
        - Gastos com Transporte: R$ {request.resumo_transacoes.get('Transporte', 0)}
        - Gastos com Lazer: R$ {request.resumo_transacoes.get('Lazer', 0)}
        - Gastos com Moradia: R$ {request.resumo_transacoes.get('Moradia', 0)}
    """

    # 2. Obter a resposta da IA
    resposta_ia = obter_resposta_ia(contexto, request.pergunta)

    return {"resposta": resposta_ia}