"""
Serviço de Integração com a API da Groq (IA)
Arquivo: backend/app/services/ia_service.py
"""

import os
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
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
        return response.choices[0].message.content
        
    except Exception as e:
        # Log interno (pode ser substituído por logger.error em produção)
        if os.getenv("DEBUG", "false").lower() == "true":
            print(f"❌ Erro na chamada da API Groq: {e}")
        
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
    
    return loop.run_until_complete(
        obter_resposta_ia_async(system_message, user_message)
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Cliente assíncrono (AsyncOpenAI) para não bloquear o event loop
# ✅ Temperatura reduzida para 0.4 (mais preciso para finanças)
# ✅ Adicionado max_tokens=500 (controle de custo e tempo)
# ✅ Tratamento de erro com mensagem amigável (não vaza detalhes)
# ✅ Log condicional (apenas em DEBUG)
# ✅ Mantida função síncrona para compatibilidade (legado)