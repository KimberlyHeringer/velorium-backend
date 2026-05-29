"""
Serviço de Integração com a API da Groq (IA)
Arquivo: backend/app/services/ia_service.py

🔧 MODIFICADO: Regra 2.8 - Substituído print por logger.error
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

# Cliente assíncrono (não bloqueia o event loop do FastAPI)
client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


async def obter_resposta_ia_async(system_message: str, user_message: str) -> str:
    """
    Versão assíncrona da chamada à API da Groq.
    Não bloqueia o servidor enquanto aguarda a resposta.
    
    Args:
        system_message: Instruções de sistema (contexto, regras)
        user_message: Pergunta do usuário
    
    Returns:
        Resposta da IA ou mensagem amigável em caso de erro
    """
    try:
        logger.debug(f"Enviando requisição para Groq - System: {len(system_message)} chars, User: {len(user_message)} chars")
        
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.4,      # Mais conservador (precisão em finanças)
            max_tokens=500,       # Limita tamanho da resposta (controle de custo)
            stream=False,
        )
        
        resposta = response.choices[0].message.content
        logger.debug(f"Resposta da Groq recebida: {len(resposta)} caracteres")
        return resposta
        
    except Exception as e:
        # 🔧 CORREÇÃO 2.8: substituindo print por logger.error
        logger.error(f"Erro na chamada da API Groq: {e}")
        import traceback
        logger.debug(f"Detalhes do erro na Groq: {traceback.format_exc()}")
        
        # Mensagem amigável para o usuário (não expõe detalhes internos)
        return "Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente mais tarde."


# ========== FUNÇÃO SÍNCRONA (LEGADO) ==========
# Mantida apenas para compatibilidade com código antigo.
# Use obter_resposta_ia_async em novos endpoints.

def obter_resposta_ia(system_message: str, user_message: str) -> str:
    """
    Versão síncrona (legado). Para novas implementações, use a versão async.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    logger.debug("Usando função síncrona de IA (legado)")
    return loop.run_until_complete(
        obter_resposta_ia_async(system_message, user_message)
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Cliente assíncrono (AsyncOpenAI) para não bloquear o event loop
# ✅ Temperatura reduzida para 0.4 (mais preciso para finanças)
# ✅ Adicionado max_tokens=500 (controle de custo e tempo)
# ✅ Tratamento de erro com mensagem amigável (não vaza detalhes)
# ✅ 🔧 Logs substituídos (Regra 2.8)
# ✅ Mantida função síncrona para compatibilidade (legado)