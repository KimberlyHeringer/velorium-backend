"""
Rotas de IA (Inteligência Artificial)
Arquivo: backend/app/routes/ia.py

🔧 MODIFICADO: Regra 2.8 - Logs
🔧 MODIFICADO: Regra 2.10 - Adicionado validate_object_id
🔧 MODIFICADO: Regra 3.4 - IA e Dados do Usuário
- Adicionada anonimização dos dados
- Adicionado histórico de conversa (últimas 3 mensagens)
- Respostas mais diretas e focadas em finanças
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
from app.utils.anonimizer import (
    anonymize_user_data, 
    get_conversation_context,
    get_score_range
)
from bson import ObjectId

logger = setup_logger(__name__)

router = APIRouter(prefix="/ia", tags=["IA"])


# ========== SCHEMAS ==========

class ChatRequest(BaseModel):
    pergunta: str = Field(..., max_length=500)


class ChatResponse(BaseModel):
    resposta: str


# ========== FUNÇÕES AUXILIARES ==========

async def montar_contexto_ia_anonimizado() -> str:
    """Versão anonimizada do contexto (sem dados pessoais)"""
    return """
Contexto: O usuário optou por não compartilhar dados financeiros detalhados.

Orientações:
- Responda com dicas genéricas e conceitos gerais sobre finanças pessoais.
- Seja direta e prática.
- Não peça dados específicos do usuário.
- Mantenha respostas curtas (1-3 frases para perguntas simples).
"""


async def montar_contexto_ia_completo_anonimizado(current_user: UserResponse, db, conversation_history: str = "") -> str:
    """
    Monta o contexto com dados ANONIMIZADOS do usuário (research_consent = true)
    🔧 REGRA 3.4: Remove nome, email, valores exatos
    """
    # Busca perfil do usuário (dados comportamentais, sem identificação)
    profile = await db.user_profiles.find_one({"user_id": current_user.id})
    
    # Busca último score
    score_doc = await db.score_history.find_one(
        {"user_id": current_user.id},
        sort=[("date", -1)]
    )
    score = score_doc.get("score", 0) if score_doc else 0
    
    # Busca gastos dos últimos 30 dias
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    transactions = await db.transactions.find({
        "user_id": current_user.id,
        "type": "expense",
        "date": {"$gte": thirty_days_ago}
    }).to_list(100)
    
    # Calcula gastos por categoria e total
    gastos_por_categoria = {}
    total_gasto = 0
    for t in transactions:
        cat = t.get("category", "Outros")
        amount = t["amount"]
        gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + amount
        total_gasto += amount
    
    # 🔧 ANONIMIZAÇÃO: converte para faixas e categorias agregadas
    anonymized_data = anonymize_user_data(
        score=score,
        expenses_by_category=gastos_por_categoria,
        total_expense=total_gasto,
        profile_data=profile
    )
    
    # 🔧 Constrói contexto com dados anonimizados
    contexto = f"""
Dados anônimos do usuário:
- Faixa de score financeiro: {anonymized_data.get('score_range', 'não disponível')}
- Principais categorias de gasto: {', '.join(anonymized_data.get('top_categories', ['nenhuma registrada']))}
- Faixa de gasto total (últimos 30 dias): R$ {anonymized_data.get('total_expense_range', 'não disponível')}
- Perfil financeiro: {anonymized_data.get('money_feeling', 'não informado')}
"""

    # Adiciona histórico da conversa se disponível
    if conversation_history:
        contexto += f"\n\nHistórico da conversa:\n{conversation_history}"
    
    return contexto


async def montar_contexto_ia_sem_consentimento() -> str:
    """Contexto genérico para usuários que não aceitaram o consentimento"""
    return """
Contexto: O usuário NÃO autorizou o uso de seus dados financeiros.

Orientações:
- Responda com dicas genéricas e conceitos gerais sobre finanças pessoais.
- NÃO mencione que os dados não foram compartilhados.
- Seja direta e prática.
- Mantenha respostas curtas (1-3 frases para perguntas simples).
"""


# ========== ENDPOINT PRINCIPAL ==========

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    # 1. Validar ID do usuário
    validate_object_id(current_user.id, "user_id")
    
    # 2. Buscar o documento completo do usuário
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
    
    # 4. 🔧 NOVO: Buscar histórico da conversa (últimas 3 interações)
    conversation_history = []
    if research_consent:
        # Busca histórico de mensagens do usuário
        history_cursor = db.chat_history.find(
            {"user_id": current_user.id},
            sort=[("created_at", -1)],
            limit=6  # 3 interações (3 perguntas + 3 respostas)
        )
        history = await history_cursor.to_list(6)
        history.reverse()  # Ordem cronológica
        
        for msg in history:
            conversation_history.append({
                "role": "user",
                "content": msg.get("question", ""),
                "created_at": msg.get("created_at")
            })
            if msg.get("answer"):
                conversation_history.append({
                    "role": "assistant", 
                    "content": msg.get("answer", ""),
                    "created_at": msg.get("created_at")
                })
    
    # 🔧 Formata o histórico para contexto
    history_context = get_conversation_context(conversation_history)
    
    # 5. Escolher o modo de resposta (com anonimização)
    try:
        if research_consent:
            logger.debug(f"Usando contexto completo ANONIMIZADO para usuário {current_user.id}")
            contexto = await montar_contexto_ia_completo_anonimizado(current_user, db, history_context)
        else:
            logger.debug(f"Usando contexto genérico para usuário {current_user.id} (sem consentimento)")
            contexto = await montar_contexto_ia_sem_consentimento()
        
        resposta = await obter_resposta_ia_async(
            system_message=contexto, 
            user_message=chat_request.pergunta,
            conversation_history=history_context
        )
        
        # 6. 🔧 Salvar histórico da conversa
        if research_consent:
            await db.chat_history.insert_one({
                "user_id": current_user.id,
                "question": chat_request.pergunta,
                "answer": resposta,
                "created_at": datetime.now(timezone.utc)
            })
        
        logger.info(f"Chat IA bem-sucedido para usuário {current_user.id}")
        return ChatResponse(resposta=resposta)
        
    except Exception as e:
        logger.error(f"Erro na chamada da IA para usuário {current_user.id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro na IA: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível processar sua solicitação. Tente novamente mais tarde."
        )


# ========== ENDPOINT DE TESTE ==========

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
        resposta = await obter_resposta_ia_async(request.prompt_context, request.pergunta_usuario, "")
        return ChatResponse(resposta=resposta)