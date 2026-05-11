"""
Rotas de IA (Inteligência Artificial)
Arquivo: backend/app/routes/ia.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
import os

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.services.ia_service import obter_resposta_ia_async
from app.database import get_database

router = APIRouter(prefix="/ia", tags=["IA"])


# ========== SCHEMAS ==========

class ChatRequest(BaseModel):
    """Requisição para o chat da IA (apenas a pergunta do usuário)"""
    pergunta: str = Field(..., max_length=500, description="Pergunta do usuário sobre finanças")


class ChatResponse(BaseModel):
    """Resposta da IA"""
    resposta: str


# ========== FUNÇÕES AUXILIARES ==========

async def montar_contexto_ia(
    current_user: UserResponse,
    db
) -> str:
    """
    Monta o contexto do sistema para a IA com base nos dados do usuário.
    Os dados são buscados diretamente no banco (não confia no frontend).
    """
    # Buscar perfil do usuário
    profile = await db.user_profiles.find_one({"user_id": current_user.id})
    
    # Buscar score atual
    score_doc = await db.score_history.find_one(
        {"user_id": current_user.id},
        sort=[("date", -1)]
    )
    score = score_doc.get("score", 0) if score_doc else 0
    
    # Buscar resumo de transações dos últimos 30 dias
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    transactions = await db.transactions.find({
        "user_id": current_user.id,
        "type": "expense",
        "date": {"$gte": thirty_days_ago}
    }).to_list(100)
    
    # Agrupar gastos por categoria
    gastos_por_categoria = {}
    for t in transactions:
        cat = t.get("category", "Outros")
        gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + t["amount"]
    
    # Formatar resumo
    resumo_gastos = ", ".join([f"{cat}: R$ {round(valor, 2)}" for cat, valor in gastos_por_categoria.items()])
    
    # Montar contexto completo
    contexto = f"""
Você é a Veloria, uma assistente financeira amigável e profissional do app Velorium.

Dados do usuário:
- Nome: {current_user.name}
- Sentimento sobre dinheiro: {profile.get('money_feeling', 'não informado') if profile else 'não informado'}
- Score financeiro atual: {score}

Gastos recentes (últimos 30 dias):
{resumo_gastos if resumo_gastos else 'Nenhum gasto registrado'}

Instruções:
1. Responda sempre em português, com tom amigável e profissional.
2. Use os dados do usuário para personalizar a resposta quando relevante.
3. Se a pergunta não for sobre finanças, responda educadamente que você só pode ajudar com finanças.
4. Seja concisa (máximo 3-4 parágrafos).
5. Não dê recomendações de investimentos específicos (apenas conceitos gerais).
"""
    return contexto


# ========== ENDPOINTS ==========

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Endpoint de chat com a IA Veloria.
    O contexto é montado automaticamente no backend com os dados reais do usuário.
    """
    try:
        contexto = await montar_contexto_ia(current_user, db)
        resposta = await obter_resposta_ia_async(contexto, request.pergunta)
        return ChatResponse(resposta=resposta)
    except Exception as e:
        # Log interno (não exposto ao cliente)
        print(f"Erro na chamada da IA para usuário {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível processar sua solicitação. Tente novamente mais tarde."
        )


# ========== ENDPOINT DE TESTE (APENAS DESENVOLVIMENTO) ==========
# A rota /perguntar está desativada em produção por segurança.

if os.getenv("DEBUG", "false").lower() == "true":
    class PerguntaRequestTeste(BaseModel):
        prompt_context: str
        pergunta_usuario: str = Field(..., max_length=500)

    @router.post("/perguntar", response_model=ChatResponse)
    async def perguntar_teste(
        request: PerguntaRequestTeste,
        current_user: UserResponse = Depends(get_current_user)
    ):
        """Endpoint de teste (apenas em desenvolvimento)"""
        resposta = await obter_resposta_ia_async(request.prompt_context, request.pergunta_usuario)
        return ChatResponse(resposta=resposta)