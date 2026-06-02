"""
Rotas de IA (Inteligência Artificial)
Arquivo: backend/app/routes/ia.py

🔧 MODIFICADO: Regra 2.8 - Logs
- Substituído print por logger.error
- Adicionado logs para eventos importantes
🔧 MODIFICADO: Regra 2.10 - Adicionado validate_object_id
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
import os

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.services.ia_service import obter_resposta_ia_async
from app.database import get_database
from app.utils.rate_limiter import limiter
from app.utils.logger import setup_logger
from app.utils.validators import validate_object_id
from bson import ObjectId

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

router = APIRouter(prefix="/ia", tags=["IA"])


# ========== SCHEMAS ==========

class ChatRequest(BaseModel):
    pergunta: str = Field(..., max_length=500)


class ChatResponse(BaseModel):
    resposta: str


# ========== FUNÇÕES AUXILIARES ==========

async def montar_contexto_ia_anonimizado() -> str:
    """
    Versão anonimizada do contexto (sem dados pessoais e financeiros).
    """
    return """
Você é a Veloria, uma assistente financeira amigável e profissional do app Velorium.

O usuário optou por não compartilhar seus dados financeiros. Portanto, responda com dicas genéricas e conceitos gerais sobre finanças pessoais.

Instruções:
1. Responda em português, tom amigável e profissional.
2. Não solicite dados específicos do usuário.
3. Não mencione que os dados não foram compartilhados (apenas responda normalmente, mas sem personalização).
4. Seja concisa (máximo 3-4 parágrafos).
5. Não dê recomendações de investimentos específicos.
"""


async def montar_contexto_ia_completo(current_user: UserResponse, db) -> str:
    """
    Monta o contexto completo com os dados reais do usuário (usado quando research_consent = true).
    """
    profile = await db.user_profiles.find_one({"user_id": current_user.id})
    
    score_doc = await db.score_history.find_one(
        {"user_id": current_user.id},
        sort=[("date", -1)]
    )
    score = score_doc.get("score", 0) if score_doc else 0
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    transactions = await db.transactions.find({
        "user_id": current_user.id,
        "type": "expense",
        "date": {"$gte": thirty_days_ago}
    }).to_list(100)
    
    gastos_por_categoria = {}
    for t in transactions:
        cat = t.get("category", "Outros")
        gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + t["amount"]
    
    resumo_gastos = ", ".join([f"{cat}: R$ {round(valor, 2)}" for cat, valor in gastos_por_categoria.items()])
    
    contexto = f"""
Você é a Veloria, uma assistente financeira amigável e profissional do app Velorium.

Dados do usuário:
- Nome: {current_user.name}
- Sentimento sobre dinheiro: {profile.get('money_feeling', 'não informado') if profile else 'não informado'}
- Score financeiro atual: {score}

Gastos recentes (últimos 30 dias):
{resumo_gastos if resumo_gastos else 'Nenhum gasto registrado'}

Instruções:
1. Responda em português, com tom amigável e profissional.
2. Use os dados do usuário para personalizar a resposta quando relevante.
3. Se a pergunta não for sobre finanças, responda educadamente que você só pode ajudar com finanças.
4. Seja concisa (máximo 3-4 parágrafos).
5. Não dê recomendações de investimentos específicos (apenas conceitos gerais).
"""
    return contexto


# ========== ENDPOINT PRINCIPAL ==========

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    # 1. Validar ID do usuário (Regra 2.10)
    validate_object_id(current_user.id, "user_id")
    
    # 2. Buscar o documento completo do usuário (para acessar os campos de consentimento)
    user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user_doc:
        logger.warning(f"Usuário não encontrado no chat: {current_user.id}")
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    terms_accepted = user_doc.get("terms_accepted", False)
    research_consent = user_doc.get("research_consent", False)
    
    # 3. Verificar se os termos foram aceitos
    if not terms_accepted:
        logger.warning(f"Tentativa de usar IA sem aceitar termos: {current_user.id}")
        raise HTTPException(
            status_code=403,
            detail="Para usar o assistente, você precisa aceitar os Termos de Uso. Acesse Configurações > Consentimento."
        )
    
    # 4. Escolher o modo de resposta
    try:
        if research_consent:
            logger.debug(f"Usando contexto completo para usuário {current_user.id} (research_consent=true)")
            contexto = await montar_contexto_ia_completo(current_user, db)
            resposta = await obter_resposta_ia_async(contexto, chat_request.pergunta)
        else:
            logger.debug(f"Usando contexto anonimizado para usuário {current_user.id} (research_consent=false)")
            contexto = await montar_contexto_ia_anonimizado()
            resposta = await obter_resposta_ia_async(contexto, chat_request.pergunta)
        
        logger.info(f"Chat IA bem-sucedido para usuário {current_user.id}")
        return ChatResponse(resposta=resposta)
    except Exception as e:
        # 🔧 CORREÇÃO 2.8: substituindo print por logger.error
        logger.error(f"Erro na chamada da IA para usuário {current_user.id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro na IA: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível processar sua solicitação. Tente novamente mais tarde."
        )


# ========== ENDPOINT DE TESTE (apenas desenvolvimento) ==========

if os.getenv("DEBUG", "false").lower() == "true":
    class PerguntaRequestTeste(BaseModel):
        prompt_context: str
        pergunta_usuario: str = Field(..., max_length=500)

    @router.post("/perguntar", response_model=ChatResponse)
    async def perguntar_teste(
        request: PerguntaRequestTeste,
        current_user: UserResponse = Depends(get_current_user)
    ):
        logger.debug(f"Endpoint de teste IA usado por usuário {current_user.id}")
        resposta = await obter_resposta_ia_async(request.prompt_context, request.pergunta_usuario)
        return ChatResponse(resposta=resposta)