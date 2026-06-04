"""
Serviço de Integração com a API da Groq (IA)
Arquivo: backend/app/services/ia_service.py

🔧 MODIFICADO: Regra 2.8 - Substituído print por logger.error
🔧 MODIFICADO: Regra 3.4 - IA e Dados do Usuário
- Otimizado prompt para respostas mais diretas
- Adicionado foco estrito em finanças
- Limite de contexto para respostas curtas
"""

import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY não encontrada no .env!")
    raise ValueError("GROQ_API_KEY não encontrada no .env!")

# Cliente assíncrono
client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# 🔧 NOVO: Prompt base do sistema (regras globais)
SYSTEM_PROMPT_BASE = """Você é a Veloria, uma assistente financeira direta, prática e amigável do app Velorium.

REGRAS OBRIGATÓRIAS:
1. Responda APENAS sobre finanças pessoais: economia, investimentos, controle de gastos, planejamento financeiro, dívidas, reserva de emergência, etc.
2. Se a pergunta NÃO for sobre finanças, responda: "Desculpe, só posso ajudar com perguntas sobre finanças pessoais. Posso ajudar com economia, investimentos ou planejamento financeiro?"
3. Seja DIRETA e CONCISA. Para perguntas simples, responda com 1-2 frases.
4. Use linguagem simples, evite jargões desnecessários.
5. Não dê recomendações de investimentos específicos (apenas conceitos gerais).
6. Responda em português (Brasil)."""


async def obter_resposta_ia_async(
    system_message: str, 
    user_message: str,
    conversation_history: str = ""
) -> str:
    """
    Versão assíncrona da chamada à API da Groq.
    
    Args:
        system_message: Instruções de sistema (contexto, regras)
        user_message: Pergunta do usuário
        conversation_history: Histórico recente da conversa (opcional)
    
    Returns:
        Resposta da IA ou mensagem amigável em caso de erro
    """
    try:
        # 🔧 Monta o prompt completo com histórico
        full_system = SYSTEM_PROMPT_BASE
        if system_message:
            full_system += f"\n\n{system_message}"
        
        full_user_message = user_message
        if conversation_history:
            full_user_message = f"Histórico da conversa:\n{conversation_history}\n\nNova pergunta: {user_message}"
        
        logger.debug(f"Enviando requisição para Groq - System: {len(full_system)} chars, User: {len(full_user_message)} chars")
        
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": full_user_message}
            ],
            temperature=0.3,      # 🔧 Mais baixo para respostas mais diretas e consistentes
            max_tokens=300,       # 🔧 Reduzido para respostas mais curtas
            stream=False,
        )
        
        resposta = response.choices[0].message.content
        logger.debug(f"Resposta da Groq recebida: {len(resposta)} caracteres")
        return resposta
        
    except Exception as e:
        logger.error(f"Erro na chamada da API Groq: {e}")
        import traceback
        logger.debug(f"Detalhes do erro na Groq: {traceback.format_exc()}")
        
        # Mensagem amigável para o usuário
        return "Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente mais tarde."


def obter_resposta_ia(system_message: str, user_message: str) -> str:
    """
    Versão síncrona (legado).
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    logger.debug("Usando função síncrona de IA (legado)")
    return loop.run_until_complete(
        obter_resposta_ia_async(system_message, user_message, "")
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Cliente assíncrono (AsyncOpenAI) para não bloquear o event loop
# ✅ Temperatura reduzida para 0.4 (mais preciso para finanças)
# ✅ Adicionado max_tokens=500 (controle de custo e tempo)
# ✅ Tratamento de erro com mensagem amigável (não vaza detalhes)
# ✅ 🔧 Logs substituídos (Regra 2.8)
# ✅ Mantida função síncrona para compatibilidade (legado)