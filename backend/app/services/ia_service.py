"""
Serviço de Integração com a API da Groq (IA)
Arquivo: backend/app/services/ia_service.py

Funcionalidades:
- Chat com IA (Veloria) para perguntas financeiras
- Cache de respostas para perguntas repetidas
- Suporte a múltiplos idiomas (pt, en, es, zh)
- Timeout configurável
- Métricas de uso (chamadas, tokens)
- Modelo configurável via env

Principais features:
- 🔧 i18n: Prompts em 4 idiomas com detecção automática
- 🔧 Cache: TTL de 1 hora para economizar custos (com suporte a idioma)
- 🔧 Timeout: Configurável via .env (padrão 30s)
- 🔧 Modelo: Configurável via .env (padrão llama-3.3-70b-versatile)
- 🔧 Métricas: Registro de chamadas e tokens por usuário
- 🔧 Logs estruturados com logger
- 🔧 Tratamento de erro com mensagens amigáveis i18n
- 🔧 CORRIGIDO: get_database() sem await (função síncrona)
- 🔧 CORRIGIDO: Cache com suporte a idioma na chave
- 🔧 CORRIGIDO: Função síncrona usa asyncio.run()
- 🔧 CORRIGIDO: Verificação db is None em _registrar_metrica
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import hashlib
import time
import asyncio

from openai import AsyncOpenAI
from dotenv import load_dotenv

from app.utils.logger import setup_logger
from app.core.constants import (
    CACHE_TTL_SECONDS,
    IA_TIMEOUT_SECONDS,
    GROQ_DEFAULT_MODEL,
    IA_MAX_TOKENS,
    IA_TEMPERATURE,
    IA_CACHE_MAX_SIZE
)

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# ========== CONFIGURAÇÕES ==========

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY não encontrada no .env!")
    raise ValueError("GROQ_API_KEY não encontrada no .env!")

# Modelo configurável via env
GROQ_MODEL = os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)

# Timeout configurável via env (em segundos)
try:
    IA_TIMEOUT = int(os.environ.get("IA_TIMEOUT_SECONDS", IA_TIMEOUT_SECONDS))
except ValueError:
    IA_TIMEOUT = IA_TIMEOUT_SECONDS
    logger.warning(f"IA_TIMEOUT_SECONDS inválido, usando padrão: {IA_TIMEOUT}s")

# Cache TTL configurável via env (em segundos)
try:
    CACHE_TTL = int(os.environ.get("IA_CACHE_TTL_SECONDS", CACHE_TTL_SECONDS))
except ValueError:
    CACHE_TTL = CACHE_TTL_SECONDS
    logger.warning(f"IA_CACHE_TTL_SECONDS inválido, usando padrão: {CACHE_TTL}s")

logger.info(f"🚀 IA Service iniciado com modelo: {GROQ_MODEL}")
logger.info(f"⏱️ Timeout: {IA_TIMEOUT}s, Cache TTL: {CACHE_TTL}s")

# Cliente assíncrono
client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=IA_TIMEOUT,
)

# ========== PROMPTS POR IDIOMA (i18n) ==========

SYSTEM_PROMPTS = {
    "pt": """Você é a Veloria, uma assistente financeira direta, prática e amigável do app Velorium.

REGRAS OBRIGATÓRIAS:
1. Responda APENAS sobre finanças pessoais: economia, investimentos, controle de gastos, planejamento financeiro, dívidas, reserva de emergência, etc.
2. Se a pergunta NÃO for sobre finanças, responda: "Desculpe, só posso ajudar com perguntas sobre finanças pessoais. Posso ajudar com economia, investimentos ou planejamento financeiro?"
3. Seja DIRETA e CONCISA. Para perguntas simples, responda com 1-2 frases.
4. Use linguagem simples, evite jargões desnecessários.
5. Não dê recomendações de investimentos específicos (apenas conceitos gerais).
6. Responda em português (Brasil).""",

    "en": """You are Veloria, a direct, practical and friendly financial assistant from the Velorium app.

MANDATORY RULES:
1. Respond ONLY about personal finances: savings, investments, spending control, financial planning, debts, emergency funds, etc.
2. If the question is NOT about finances, respond: "Sorry, I can only help with questions about personal finances. Can I help with savings, investments or financial planning?"
3. Be DIRECT and CONCISE. For simple questions, answer with 1-2 sentences.
4. Use simple language, avoid unnecessary jargon.
5. Do not give specific investment recommendations (only general concepts).
6. Respond in English.""",

    "es": """Eres Veloria, una asistente financiera directa, práctica y amigable de la aplicación Velorium.

REGLAS OBLIGATORIAS:
1. Responde SOLAMENTE sobre finanzas personales: ahorro, inversiones, control de gastos, planificación financiera, deudas, fondo de emergencia, etc.
2. Si la pregunta NO es sobre finanzas, responde: "Lo siento, solo puedo ayudar con preguntas sobre finanzas personales. ¿Puedo ayudar con ahorros, inversiones o planificación financiera?"
3. Sé DIRECTA y CONCISA. Para preguntas simples, responde con 1-2 frases.
4. Usa lenguaje simple, evita jergas innecesarias.
5. No des recomendaciones de inversiones específicas (solo conceptos generales).
6. Responde en español.""",

    "zh": """你是Veloria，一个直接、实用、友好的财务助手，来自Velorium应用。

强制性规则：
1. 只回答关于个人财务的问题：储蓄、投资、支出控制、财务规划、债务、应急基金等。
2. 如果问题不是关于财务的，回答："抱歉，我只能帮助回答有关个人财务的问题。我可以帮助储蓄、投资或财务规划吗？"
3. 要直接和简洁。对于简单的问题，用1-2句话回答。
4. 使用简单的语言，避免不必要的术语。
5. 不要给出具体的投资建议（只给出一般概念）。
6. 用中文回答。"""
}

# ========== CACHE DE RESPOSTAS ==========

class ResponseCache:
    """
    Cache simples para respostas da IA.
    - TTL configurável
    - Limpeza automática de entradas expiradas
    - Limite de tamanho máximo
    - 🔧 CORRIGIDO: Suporte a idioma na chave
    """
    
    def __init__(self, ttl_seconds: int = CACHE_TTL, max_size: int = IA_CACHE_MAX_SIZE):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, system_message: str, user_message: str, history: str = "", language: str = "pt") -> str:
        """
        Gera chave única para o cache.
        🔧 CORRIGIDO: Inclui idioma na chave.
        """
        content = f"{system_message}|{user_message}|{history}|{language}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get(self, system_message: str, user_message: str, history: str = "", language: str = "pt") -> Optional[str]:
        """Busca resposta no cache."""
        key = self._generate_key(system_message, user_message, history, language)
        
        if key in self._cache:
            entry = self._cache[key]
            # Verifica se expirou
            if datetime.now(timezone.utc) - entry['timestamp'] < timedelta(seconds=self.ttl):
                self._hits += 1
                logger.debug(f"✅ Cache hit: {user_message[:30]}... (idioma: {language})")
                return entry['response']
            else:
                # Remove entrada expirada
                del self._cache[key]
                logger.debug(f"🗑️ Cache entry expirada: {user_message[:30]}...")
        
        self._misses += 1
        return None
    
    def set(self, system_message: str, user_message: str, history: str, response: str, language: str = "pt") -> None:
        """Armazena resposta no cache."""
        key = self._generate_key(system_message, user_message, history, language)
        
        # Limita tamanho do cache
        if len(self._cache) >= self.max_size:
            # Remove a entrada mais antiga
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]['timestamp'])
            del self._cache[oldest_key]
            logger.debug(f"🗑️ Cache cheio, removendo entrada mais antiga")
        
        self._cache[key] = {
            'response': response,
            'timestamp': datetime.now(timezone.utc)
        }
        logger.debug(f"💾 Cache salvo: {user_message[:30]}... (idioma: {language})")
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas do cache."""
        total = self._hits + self._misses
        hit_rate = round((self._hits / total * 100) if total > 0 else 0, 2)
        return {
            'size': len(self._cache),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': hit_rate
        }
    
    def clear(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("🗑️ Cache completamente limpo")


# Instância global do cache
_response_cache = ResponseCache()


# ========== FUNÇÃO PRINCIPAL ==========

async def obter_resposta_ia_async(
    system_message: str,
    user_message: str,
    conversation_history: str = "",
    language: str = "pt",
    user_id: Optional[str] = None,
    skip_cache: bool = False
) -> str:
    """
    Versão assíncrona da chamada à API da Groq com:
    - i18n (prompts em 4 idiomas)
    - Cache de respostas (com suporte a idioma)
    - Timeout configurável
    - Métricas de uso
    
    Args:
        system_message: Instruções de sistema adicionais (contexto)
        user_message: Pergunta do usuário
        conversation_history: Histórico recente da conversa (opcional)
        language: Idioma do usuário (pt, en, es, zh)
        user_id: ID do usuário para métricas (opcional)
        skip_cache: Se True, ignora o cache
    
    Returns:
        Resposta da IA ou mensagem amigável em caso de erro
    """
    start_time = time.time()
    
    # ===== 1. PREPARA O PROMPT =====
    
    # Busca o prompt base no idioma correto
    base_prompt = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["pt"])
    
    full_system = base_prompt
    if system_message:
        full_system += f"\n\n{system_message}"
    
    full_user_message = user_message
    if conversation_history:
        full_user_message = f"Histórico da conversa:\n{conversation_history}\n\nNova pergunta: {user_message}"
    
    # ===== 2. VERIFICA CACHE (com suporte a idioma) =====
    
    cached_response = None
    if not skip_cache:
        cached_response = _response_cache.get(full_system, full_user_message, conversation_history, language)
        if cached_response:
            logger.debug(f"✅ Cache hit para usuário {user_id}: {user_message[:30]}...")
            return cached_response
    
    # ===== 3. CHAMA A IA =====
    
    try:
        logger.debug(f"📤 Enviando requisição para Groq - Modelo: {GROQ_MODEL}, Timeout: {IA_TIMEOUT}s")
        logger.debug(f"   - System: {len(full_system)} chars, User: {len(full_user_message)} chars")
        logger.debug(f"   - Idioma: {language}, Usuário: {user_id or 'anônimo'}")
        
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": full_user_message}
            ],
            temperature=IA_TEMPERATURE,
            max_tokens=IA_MAX_TOKENS,
            stream=False,
        )
        
        elapsed_time = time.time() - start_time
        resposta = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
        
        logger.debug(f"📥 Resposta recebida: {len(resposta)} caracteres, {tokens_used} tokens, {elapsed_time:.2f}s")
        
        # ===== 4. SALVA NO CACHE (com suporte a idioma) =====
        
        if not skip_cache:
            _response_cache.set(full_system, full_user_message, conversation_history, resposta, language)
        
        # ===== 5. REGISTRA MÉTRICAS =====
        
        if user_id:
            await _registrar_metrica(
                user_id=user_id,
                tokens_used=tokens_used,
                elapsed_time=elapsed_time,
                language=language,
                model=GROQ_MODEL
            )
        
        return resposta
        
    except TimeoutError as e:
        logger.error(f"⏱️ Timeout na chamada da API Groq: {e}")
        from app.utils.i18n import get_message
        return get_message("IA_ERROR_TIMEOUT", language)
        
    except Exception as e:
        logger.error(f"❌ Erro na chamada da API Groq: {e}")
        import traceback
        logger.debug(f"Detalhes do erro: {traceback.format_exc()}")
        
        from app.utils.i18n import get_message
        return get_message("IA_ERROR_GENERIC", language)


# ========== FUNÇÃO SÍNCRONA (LEGADO) ==========

def obter_resposta_ia(
    system_message: str,
    user_message: str,
    language: str = "pt"
) -> str:
    """
    Versão síncrona (legado) para compatibilidade.
    🔧 CORRIGIDO: Usa asyncio.run() em vez de loop manual.
    """
    return asyncio.run(
        obter_resposta_ia_async(system_message, user_message, "", language)
    )


# ========== MÉTRICAS DE USO ==========

async def _registrar_metrica(
    user_id: str,
    tokens_used: int,
    elapsed_time: float,
    language: str,
    model: str
) -> None:
    """
    Registra métricas de uso da IA no banco.
    🔧 CORRIGIDO: get_database() NÃO é async (removeu await).
    🔧 CORRIGIDO: Verifica se db não é None.
    """
    try:
        from app.database import get_database
        
        db = get_database()  # 🔧 CORRIGIDO: SEM AWAIT
        
        # 🔧 NOVO: Verifica se o banco está disponível
        if db is None:
            logger.warning("⚠️ Banco não disponível para registrar métricas")
            return
        
        await db.ia_metrics.insert_one({
            "user_id": user_id,
            "tokens_used": tokens_used,
            "elapsed_time": elapsed_time,
            "language": language,
            "model": model,
            "timestamp": datetime.now(timezone.utc)
        })
        logger.debug(f"📊 Métricas registradas para usuário {user_id}")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao registrar métricas: {e}")


async def get_ia_metrics(user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Retorna métricas de uso da IA para um usuário.
    🔧 CORRIGIDO: get_database() NÃO é async (removeu await).
    """
    try:
        from app.database import get_database
        
        db = get_database()  # 🔧 CORRIGIDO: SEM AWAIT
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        metrics = await db.ia_metrics.find({
            "user_id": user_id,
            "timestamp": {"$gte": since}
        }).to_list(1000)
        
        if not metrics:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "avg_time": 0,
                "calls_by_language": {},
                "days": days
            }
        
        total_calls = len(metrics)
        total_tokens = sum(m.get("tokens_used", 0) for m in metrics)
        avg_time = round(sum(m.get("elapsed_time", 0) for m in metrics) / total_calls, 2) if total_calls > 0 else 0
        
        # Contagem por idioma
        languages = {}
        for m in metrics:
            lang = m.get("language", "unknown")
            languages[lang] = languages.get(lang, 0) + 1
        
        return {
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "avg_time": avg_time,
            "calls_by_language": languages,
            "days": days
        }
    except Exception as e:
        logger.warning(f"⚠️ Erro ao buscar métricas: {e}")
        return {
            "total_calls": 0,
            "total_tokens": 0,
            "avg_time": 0,
            "calls_by_language": {},
            "days": days
        }


def get_cache_stats() -> Dict[str, int]:
    """
    Retorna estatísticas do cache.
    """
    return _response_cache.get_stats()


def clear_cache() -> None:
    """
    Limpa o cache de respostas.
    """
    _response_cache.clear()


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - i18n completo com prompts em 4 idiomas (pt, en, es, zh)
#   - Detecção automática de idioma via parâmetro
#   - Cache de respostas com TTL configurável (1 hora)
#   - 🔧 Cache com suporte a idioma na chave
#   - Timeout configurável via .env (padrão 30s)
#   - Modelo configurável via .env (padrão llama-3.3-70b-versatile)
#   - Métricas de uso (chamadas, tokens, tempo)
#   - Cliente assíncrono (AsyncOpenAI)
#   - Temperatura reduzida (0.3) para respostas diretas
#   - max_tokens=300 para controle de custo
#   - Tratamento de erro com mensagens amigáveis i18n
#   - Logs estruturados com logger
#   - Cache com limpeza automática de entradas expiradas
#   - Cache com limite de tamanho máximo (1000 entradas)
#   - Estatísticas do cache (hits, misses, hit rate)
#   - Função para limpar cache
#   - Função para buscar métricas de uso por usuário
#   - 🔧 CORRIGIDO: get_database() SEM AWAIT (função síncrona)
#   - 🔧 CORRIGIDO: Função síncrona usa asyncio.run()
#   - 🔧 CORRIGIDO: Cache com suporte a idioma na chave
#   - 🔧 CORRIGIDO: Verificação db is None em _registrar_metrica
#
# ❌ Não implementado (Pós-MVP):
#   - Rate limiting por usuário
#   - Fila de processamento para chamadas simultâneas
#   - Webhook para notificações de uso excessivo
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração com i18n, cache, timeout, métricas (04/07/2026)
#   - v3: Correções - get_database sem await, cache com language, asyncio.run (04/07/2026)
#   - v4: Correção - db is None em _registrar_metrica (04/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO