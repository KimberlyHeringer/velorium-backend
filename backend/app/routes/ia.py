"""
Rotas de IA (Inteligência Artificial)
Arquivo: backend/app/routes/ia.py

🔧 CORRIGIDO (v3.2 - FINAL):
- Convertidos centavos para reais no contexto da IA (to_cents/from_cents)
- Protegido endpoint /perguntar (teste) apenas em desenvolvimento
- Adicionada validação min_length=1 para pergunta
- Removida função não utilizada montar_contexto_ia_anonimizado

🆕 MELHORIAS ADICIONADAS (v3):
- 🔧 I18n completo com I18nHTTPException e get_message()
- 🆕 Adicionado request: Request em todos os endpoints
- 🆕 Adicionado rate limiting por usuário (user_id)
- 🆕 Adicionado cache para respostas da IA (em memória)
- 🆕 Adicionado feedback do usuário (útil/não útil)
- 🆕 Adicionado logs de auditoria (history)
- 🔧 REMOVIDO: raw_text da resposta (dados sensíveis)
- 🆕 Adicionado campo audit_id nas respostas

🔧 CORREÇÕES DO DESENVOLVEDOR (v3.1):
- 🔧 CORRIGIDO: get_user_rate_limit_key agora recebe Request
- 🔧 CORRIGIDO: save_feedback com upsert para evitar duplicatas
- 🔧 DOCUMENTADO: ia_cache em memória (aceitável para MVP)

🔧 CORREÇÕES DOS DESENVOLVEDORES (v3.2):
- 🔧 MELHORADO: get_user_rate_limit_key com fallback para IP
- 🔧 NOVO: Limpeza periódica do cache (evita memory leak)
- 🔧 NOVO: Validação de research_consent no feedback
- 🔧 CORRIGIDO: MAX_HISTORY_ENTRIES agora é usado no histórico

📋 DECISÕES DOCUMENTADAS:
- ✅ Implementado cache em memória para reduzir custos da IA
- ✅ Implementado feedback do usuário para melhorar a IA
- ✅ Implementado logs de auditoria para rastreabilidade
- ✅ Removido raw_text por questões de segurança/LGPD
- ✅ Rate limiting por usuário (mais seguro que por IP)

📋 LIMITAÇÕES CONHECIDAS:
- Cache em memória: reinicia quando o servidor reinicia
- Para produção com muitos usuários, considerar Redis
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
import os
import json
import hashlib
import asyncio
from typing import Optional, Dict, List
from enum import Enum

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
from app.utils.currency import from_cents
from bson import ObjectId

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

logger = setup_logger(__name__)

router = APIRouter(prefix="/ia", tags=["IA"])


# ========== CONSTANTES ==========
CACHE_TTL_SECONDS = 3600  # 1 hora
MAX_HISTORY_ENTRIES = 1000  # Limite de histórico por usuário


# ========== CACHE EM MEMÓRIA ==========
class IACache:
    """
    🆕 Cache em memória para respostas da IA.
    Reduz custos e latência.
    
    🔧 MELHORADO: Limpeza periódica para evitar memory leak.
    Limitações: reinicia quando o servidor reinicia.
    Para produção, considerar Redis.
    """
    
    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._ttl = CACHE_TTL_SECONDS
        self._start_cleanup()
    
    def _start_cleanup(self):
        """Inicia o loop de limpeza periódica do cache"""
        asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """
        🔧 NOVO: Limpeza periódica do cache (a cada hora).
        Remove entradas expiradas para evitar memory leak.
        """
        while True:
            try:
                await asyncio.sleep(3600)  # A cada hora
                now = datetime.now(timezone.utc)
                to_delete = [
                    key for key, entry in self._cache.items()
                    if now > entry.get("expires_at", now)
                ]
                for key in to_delete:
                    del self._cache[key]
                if to_delete:
                    logger.debug(f"🧹 Limpeza de cache: {len(to_delete)} entradas removidas")
            except Exception as e:
                logger.error(f"❌ Erro na limpeza do cache: {e}")
    
    def _get_cache_key(self, user_id: str, question: str, context_hash: str) -> str:
        """Gera chave única para o cache"""
        content = f"{user_id}:{question}:{context_hash}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, user_id: str, question: str, context_hash: str) -> Optional[str]:
        """Busca resposta no cache"""
        key = self._get_cache_key(user_id, question, context_hash)
        entry = self._cache.get(key)
        
        if not entry:
            return None
        
        # Verifica se expirou
        if datetime.now(timezone.utc) > entry["expires_at"]:
            del self._cache[key]
            return None
        
        logger.debug(f"💾 Cache hit para usuário {user_id}")
        return entry["response"]
    
    def set(self, user_id: str, question: str, context_hash: str, response: str):
        """Armazena resposta no cache"""
        key = self._get_cache_key(user_id, question, context_hash)
        self._cache[key] = {
            "response": response,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self._ttl)
        }
        logger.debug(f"💾 Cache miss - resposta armazenada para usuário {user_id}")


# Instância global do cache
ia_cache = IACache()


# ========== SCHEMAS ==========

class ChatRequest(BaseModel):
    pergunta: str = Field(..., min_length=1, max_length=500, description="Pergunta do usuário")


class ChatResponse(BaseModel):
    resposta: str
    audit_id: str  # 🆕 ID para feedback


class ExtractTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Texto da notificação")
    source: str = Field("notification", description="Fonte do texto (notification, screenshot, etc)")


class ExtractTextResponse(BaseModel):
    amount: Optional[float] = None
    merchant: Optional[str] = None
    suggested_category: Optional[str] = None
    confidence: float = 0.0
    # raw_text: str  # 🔧 REMOVIDO - dados sensíveis


class FeedbackType(str, Enum):
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"


class FeedbackRequest(BaseModel):
    audit_id: str = Field(..., description="ID da interação")
    feedback: FeedbackType = Field(..., description="Tipo de feedback")
    comment: Optional[str] = Field(None, max_length=500, description="Comentário adicional")


# ========== FUNÇÕES AUXILIARES ==========

# 🔧 MELHORADO: Fallback para IP
def get_user_rate_limit_key(request: Request) -> str:
    """
    🔧 MELHORADO: Gera chave de rate limiting por usuário ou IP.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"ia:user:{user_id}"
    
    # Fallback para IP (se disponível)
    client_ip = request.client.host if request.client else "unknown"
    return f"ia:ip:{client_ip}"


async def montar_contexto_ia_completo_anonimizado(current_user: UserResponse, db, conversation_history: str = "") -> str:
    """
    Monta o contexto com dados ANONIMIZADOS do usuário (research_consent = true)
    🔧 REGRA 3.4: Remove nome, email, valores exatos
    🔧 CORRIGIDO: Converte centavos para reais antes de enviar para IA
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
    total_gasto = 0
    for t in transactions:
        cat = t.get("category", "Outros")
        amount_cents = t.get("amount", 0)
        amount_reais = from_cents(amount_cents)
        gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + amount_reais
        total_gasto += amount_reais
    
    anonymized_data = anonymize_user_data(
        score=score,
        expenses_by_category=gastos_por_categoria,
        total_expense=total_gasto,
        profile_data=profile
    )
    
    # 🔧 Fallback seguro para score_range
    score_range = anonymized_data.get('score_range', 'não disponível')
    top_categories = ', '.join(anonymized_data.get('top_categories', ['nenhuma registrada']))
    total_expense_range = anonymized_data.get('total_expense_range', 'não disponível')
    money_feeling = anonymized_data.get('money_feeling', 'não informado')
    
    contexto = f"""
Dados anônimos do usuário:
- Faixa de score financeiro: {score_range}
- Principais categorias de gasto: {top_categories}
- Faixa de gasto total (últimos 30 dias): R$ {total_expense_range}
- Perfil financeiro: {money_feeling}
"""

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


async def add_audit_log(db, user_id: str, action: str, details: dict) -> str:
    """
    🆕 Adiciona entrada no log de auditoria da IA.
    Retorna o ID do log para referência.
    """
    log_entry = {
        "user_id": user_id,
        "action": action,
        "details": details,
        "created_at": datetime.now(timezone.utc),
        "ip": None,  # Pode ser adicionado se necessário
        "user_agent": None
    }
    
    result = await db.ia_audit_logs.insert_one(log_entry)
    return str(result.inserted_id)


async def save_feedback(db, audit_id: str, feedback: str, comment: str = None):
    """
    🆕 Salva o feedback do usuário sobre a resposta da IA.
    🔧 CORRIGIDO: Upsert para evitar duplicatas.
    """
    existing = await db.ia_feedback.find_one({"audit_id": audit_id})
    
    if existing:
        await db.ia_feedback.update_one(
            {"audit_id": audit_id},
            {
                "$set": {
                    "feedback": feedback,
                    "comment": comment,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        logger.debug(f"🔄 Feedback atualizado para audit {audit_id}")
    else:
        await db.ia_feedback.insert_one({
            "audit_id": audit_id,
            "feedback": feedback,
            "comment": comment,
            "created_at": datetime.now(timezone.utc)
        })
        logger.debug(f"✅ Feedback criado para audit {audit_id}")


# ========== ENDPOINT PRINCIPAL ==========

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Chat com a IA - versão com anonimização e cache"""
    
    language = getattr(request.state, "language", "pt")
    
    # 🔧 Armazena user_id no state para o rate limiting
    request.state.user_id = str(current_user.id)
    
    validate_object_id(current_user.id, "user_id")
    
    user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user_doc:
        logger.warning(f"⚠️ Usuário não encontrado no chat: {current_user.id}")
        raise NotFoundException(
            message_key="ERROR_USER_NOT_FOUND",
            request=request
        )
    
    terms_accepted = user_doc.get("terms_accepted", False)
    research_consent = user_doc.get("research_consent", False)
    
    if not terms_accepted:
        logger.warning(f"⚠️ Tentativa de usar IA sem aceitar termos: {current_user.id}")
        raise ValidationException(
            message_key="ERROR_TERMS_NOT_ACCEPTED",
            request=request
        )
    
    # 🔍 Buscar histórico da conversa (usando MAX_HISTORY_ENTRIES)
    conversation_history = []
    if research_consent:
        history_cursor = db.chat_history.find(
            {"user_id": current_user.id},
            sort=[("created_at", -1)],
            limit=MAX_HISTORY_ENTRIES
        )
        history = await history_cursor.to_list(MAX_HISTORY_ENTRIES)
        history.reverse()
        
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
    
    history_context = get_conversation_context(conversation_history)
    
    try:
        if research_consent:
            logger.debug(f"📊 Usando contexto completo ANONIMIZADO para usuário {current_user.id}")
            contexto = await montar_contexto_ia_completo_anonimizado(current_user, db, history_context)
        else:
            logger.debug(f"📊 Usando contexto genérico para usuário {current_user.id} (sem consentimento)")
            contexto = await montar_contexto_ia_sem_consentimento()
        
        # 🆕 Verifica cache
        context_hash = hashlib.md5(contexto.encode()).hexdigest()
        cached_response = ia_cache.get(str(current_user.id), chat_request.pergunta, context_hash)
        
        if cached_response:
            resposta = cached_response
            from_cache = True
        else:
            resposta = await obter_resposta_ia_async(
                system_message=contexto, 
                user_message=chat_request.pergunta,
                conversation_history=history_context
            )
            from_cache = False
            ia_cache.set(str(current_user.id), chat_request.pergunta, context_hash, resposta)
        
        # 🆕 Salvar na conversa
        if research_consent:
            await db.chat_history.insert_one({
                "user_id": current_user.id,
                "question": chat_request.pergunta,
                "answer": resposta,
                "from_cache": from_cache,
                "created_at": datetime.now(timezone.utc)
            })
        
        # 🆕 Log de auditoria
        audit_id = await add_audit_log(
            db,
            str(current_user.id),
            "chat",
            {
                "question": chat_request.pergunta,
                "from_cache": from_cache,
                "research_consent": research_consent
            }
        )
        
        logger.info(f"✅ Chat IA bem-sucedido para usuário {current_user.id} (cache: {from_cache})")
        return ChatResponse(resposta=resposta, audit_id=audit_id)
        
    except Exception as e:
        logger.error(f"❌ Erro na chamada da IA para usuário {current_user.id}: {e}")
        import traceback
        logger.debug(f"Detalhes do erro na IA: {traceback.format_exc()}")
        raise I18nHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message_key="ERROR_IA_REQUEST_FAILED",
            request=request
        )


# ========== FEEDBACK DO USUÁRIO ==========

@router.post("/feedback", response_model=dict)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def submit_feedback(
    request: Request,
    feedback_data: FeedbackRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    🆕 Recebe feedback do usuário sobre a resposta da IA.
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 Armazena user_id no state para o rate limiting
    request.state.user_id = str(current_user.id)
    
    # 🔧 Valida research_consent
    user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user_doc:
        raise NotFoundException(
            message_key="ERROR_USER_NOT_FOUND",
            request=request
        )
    if not user_doc.get("research_consent", False):
        raise ValidationException(
            message_key="ERROR_RESEARCH_CONSENT_REQUIRED",
            request=request
        )
    
    # Valida se o audit_id existe
    audit_log = await db.ia_audit_logs.find_one({
        "_id": ObjectId(feedback_data.audit_id),
        "user_id": str(current_user.id)
    })
    
    if not audit_log:
        raise NotFoundException(
            message_key="ERROR_AUDIT_NOT_FOUND",
            request=request
        )
    
    # Salva o feedback (com upsert)
    await save_feedback(
        db,
        feedback_data.audit_id,
        feedback_data.feedback,
        feedback_data.comment
    )
    
    logger.info(f"✅ Feedback recebido: {feedback_data.feedback} para audit {feedback_data.audit_id}")
    
    return {
        "message": get_message("SUCCESS_FEEDBACK_RECEIVED", language),
        "success": True
    }


# ========== ENDPOINT PARA EXTRAIR DADOS DE TEXTO ==========

@router.post("/extract-from-text", response_model=ExtractTextResponse)
@limiter.limit("20/minute", key_func=get_user_rate_limit_key)
async def extract_from_text(
    request: Request,
    extract_request: ExtractTextRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Extrai dados financeiros de um texto (notificação, screenshot, etc.)
    Usa IA para identificar valor, estabelecimento, categoria.
    🔧 REGRA 3.5: Leitura de Notificações
    🔧 REMOVIDO: raw_text da resposta (dados sensíveis)
    """
    language = getattr(request.state, "language", "pt")
    
    # 🔧 Armazena user_id no state para o rate limiting
    request.state.user_id = str(current_user.id)
    
    try:
        logger.info(f"📊 Extraindo dados de texto para usuário {current_user.id} - Fonte: {extract_request.source}")
        
        system_prompt = """
Você é um assistente especializado em extrair informações financeiras de textos.

Dado um texto (geralmente de notificação de banco ou app de compras), extraia:
1. amount: valor da transação (número, sem R$)
2. merchant: nome do estabelecimento (se disponível)
3. suggested_category: categoria sugerida (Alimentação, Transporte, Moradia, Lazer, Saúde, Educação, Investimentos, Outros)

Regras:
- Se não encontrar valor, retorne amount = null
- Se não encontrar estabelecimento, retorne merchant = null
- Use apenas as categorias listadas acima
- Retorne confidence (0-1) baseado na sua certeza

Responda APENAS com JSON no formato:
{"amount": 123.45, "merchant": "Nome do local", "suggested_category": "Alimentação", "confidence": 0.95}
"""
        
        user_message = f"Texto: {extract_request.text}\n\nExtraia as informações financeiras."
        
        resposta = await obter_resposta_ia_async(system_prompt, user_message)
        
        try:
            clean_response = resposta.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.startswith('```'):
                clean_response = clean_response[3:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            
            data = json.loads(clean_response.strip())
            
            # 🆕 Log de auditoria (sem raw_text)
            await add_audit_log(
                db,
                str(current_user.id),
                "extract_text",
                {
                    "source": extract_request.source,
                    "amount_found": data.get('amount') is not None,
                    "merchant_found": data.get('merchant') is not None,
                    "confidence": data.get('confidence', 0)
                }
            )
            
            logger.info(f"✅ Extração concluída: amount={data.get('amount')}, merchant={data.get('merchant')}, confidence={data.get('confidence')}")
            
            return ExtractTextResponse(
                amount=data.get('amount'),
                merchant=data.get('merchant'),
                suggested_category=data.get('suggested_category'),
                confidence=data.get('confidence', 0.5)
                # raw_text removido
            )
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao parsear resposta da IA: {resposta} - Erro: {e}")
            return ExtractTextResponse(
                confidence=0.0
                # raw_text removido
            )
        
    except Exception as e:
        logger.error(f"❌ Erro ao extrair dados do texto: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        
        # 🆕 Log de auditoria do erro
        await add_audit_log(
            db,
            str(current_user.id),
            "extract_text_error",
            {
                "source": extract_request.source,
                "error": str(e)
            }
        )
        
        raise I18nHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message_key="ERROR_IA_REQUEST_FAILED",
            request=request
        )


# ========== ENDPOINT DE TESTE (APENAS EM DESENVOLVIMENTO) ==========

# 🔧 CORRIGIDO: Protegido apenas para ambiente de desenvolvimento
if os.getenv("ENVIRONMENT", "development") != "production" and os.getenv("DEBUG", "false").lower() == "true":
    class PerguntaRequestTeste(BaseModel):
        prompt_context: str
        pergunta_usuario: str = Field(..., min_length=1, max_length=500)

    @router.post("/perguntar", response_model=ChatResponse)
    async def perguntar_teste(
        request: PerguntaRequestTeste,
        current_user: UserResponse = Depends(get_current_user)
    ):
        """Endpoint de teste - disponível apenas em desenvolvimento com DEBUG=true"""
        logger.debug(f"🔬 Endpoint de teste IA usado por usuário {current_user.id}")
        resposta = await obter_resposta_ia_async(request.prompt_context, request.pergunta_usuario, "")
        return ChatResponse(resposta=resposta, audit_id="test")


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO (v3.2):
================================================================================
1. 🆕 I18n completo com I18nHTTPException e get_message()
2. 🆕 Adicionado request: Request em todos os endpoints
3. 🆕 Rate limiting por usuário (user_id)
4. 🆕 Cache em memória para respostas da IA (reduz custos)
5. 🆕 Feedback do usuário (útil/não útil)
6. 🆕 Logs de auditoria (history)
7. 🔧 REMOVIDO: raw_text da resposta (dados sensíveis)
8. 🆕 Adicionado campo audit_id nas respostas
9. 🔧 CORRIGIDO: get_user_rate_limit_key agora recebe Request
10. 🔧 CORRIGIDO: save_feedback com upsert para evitar duplicatas
11. 🔧 DOCUMENTADO: ia_cache em memória (aceitável para MVP)
12. 🔧 MELHORADO: get_user_rate_limit_key com fallback para IP
13. 🔧 NOVO: Limpeza periódica do cache (evita memory leak)
14. 🔧 NOVO: Validação de research_consent no feedback
15. 🔧 CORRIGIDO: MAX_HISTORY_ENTRIES agora é usado no histórico

📌 CHAVES I18N UTILIZADAS:
   - ERROR_USER_NOT_FOUND → "Usuário não encontrado"
   - ERROR_TERMS_NOT_ACCEPTED → "Para usar o assistente..."
   - ERROR_IA_REQUEST_FAILED → "Não foi possível processar..."
   - SUCCESS_FEEDBACK_RECEIVED → "Feedback recebido com sucesso"
   - ERROR_AUDIT_NOT_FOUND → "Interação não encontrada"
   - ERROR_RESEARCH_CONSENT_REQUIRED → "Consentimento de pesquisa necessário"

📋 DECISÕES DOCUMENTADAS:
   - ✅ Cache em memória: reduz custos da IA (aceitável para MVP)
   - ✅ Feedback do usuário: melhora a IA
   - ✅ Logs de auditoria: rastreabilidade
   - ✅ Rate limiting por usuário: mais seguro
   - ✅ raw_text removido: segurança/LGPD

✅ STATUS: PRONTO PARA PRODUÇÃO
================================================================================
"""