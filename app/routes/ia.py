from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from app.services.ia_service import obter_resposta_ia
from app.utils.auth import get_current_user
from app.models.user import UserResponse

router = APIRouter(prefix="/ia", tags=["Inteligência Artificial"])

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
    contexto = f"""
    Perfil do Usuário:
    - Sentimento sobre dinheiro: {request.perfil.get('money_feeling', 'não informado') if request.perfil else 'não informado'}
    - Reação a compras não planejadas: {request.perfil.get('post_purchase', 'não informado') if request.perfil else 'não informado'}
    - Sonho para os próximos 5 anos: {request.perfil.get('dream_5y', 'não informado') if request.perfil else 'não informado'}
    - Reserva de emergência desejada: {request.perfil.get('emergency_target', 'não informado') if request.perfil else 'não informado'}
    - Possui dívidas? {request.perfil.get('has_debt', 'não informado') if request.perfil else 'não informado'}
    - Comportamento com cartão de crédito: {request.perfil.get('credit_card_behavior', 'não informado') if request.perfil else 'não informado'}

    Score financeiro atual: {request.score if request.score is not None else 'não calculado'}

    Resumo das últimas transações:
    - Gastos com Alimentação: R$ {request.resumo_transacoes.get('Alimentação', 0) if request.resumo_transacoes else 0}
    - Gastos com Transporte: R$ {request.resumo_transacoes.get('Transporte', 0) if request.resumo_transacoes else 0}
    - Gastos com Lazer: R$ {request.resumo_transacoes.get('Lazer', 0) if request.resumo_transacoes else 0}
    - Gastos com Moradia: R$ {request.resumo_transacoes.get('Moradia', 0) if request.resumo_transacoes else 0}
    """
    resposta_ia = obter_resposta_ia(contexto, request.pergunta)
    return {"resposta": resposta_ia}