"""
Funções Utilitárias para Perfil Financeiro
Arquivo: backend/app/utils/profile_utils.py

Funcionalidade: Centraliza funções relacionadas ao perfil financeiro
para reutilização na rota profile.py.

Funcionalidades:
- Criação de perfil vazio com campos obrigatórios
- Preparação de perfil para resposta com fallback
- Garantia de existência da coleção com índices
- Cache Redis para perfil (TTL: 5 minutos)
- Métricas de hit/miss do cache
- Validação Pydantic no retorno
- Internacionalização (i18n) para mensagens

Principais features:
- 🔧 NOVO: Cache Redis para perfil (com fallback MongoDB)
- 🔧 NOVO: Métricas de hit/miss do cache
- 🔧 NOVO: Validação Pydantic no retorno
- 🔧 NOVO: Criação de índices na coleção (SEM TTL)
- 🔧 NOVO: Internacionalização (i18n) nas mensagens
- 🔧 NOVO: Validação de user_id
- 🔧 CORRIGIDO: Campos obrigatórios completos
- 🔧 CORRIGIDO: Removido TTL - dados mantidos para sempre
- ✅ Funções reutilizáveis para perfil
- ✅ Conversão de ObjectId centralizada
- ✅ Documentação completa

Regra: 2.8 (Logs)
Regra: 3.2 (Cache com Redis)
Regra: 4.1 (Índices)
Regra: 5.1 (Tratamento de erros)
Regra: 7.1 (Internacionalização)

🔧 USO:
    from app.utils.profile_utils import (
        create_empty_profile,
        prepare_profile_response,
        ensure_profile_collection,
        get_cached_profile,
        set_cached_profile,
        invalidate_profile_cache,
        get_profile_metrics,
        reset_profile_metrics
    )
    
    # Garantir que a coleção existe com índices
    await ensure_profile_collection(db)
    
    # Buscar perfil com cache
    profile = await get_cached_profile(user_id, db)
    if profile is None:
        profile = await db.user_profiles.find_one({"user_id": user_id})
        if profile:
            await set_cached_profile(user_id, profile)
    
    # Preparar resposta (com validação Pydantic)
    response = prepare_profile_response(profile, fallback_user_id=user_id)
    
    # Ver métricas do cache
    metrics = get_profile_metrics()
    print(metrics["hit_rate"])  # 85.0%
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import os

from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger
from app.utils.i18n import get_message
from app.core.constants import BALANCE_CACHE_TTL_SECONDS

# 🔧 NOVO: Import do modelo Pydantic
from app.models.profile import UserProfileResponse

logger = setup_logger(__name__)

# ============================================================
# REDIS CLIENT (CONEXÃO SEGURA)
# ============================================================

try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para cache de perfil")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - usando MongoDB para cache de perfil")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - usando MongoDB para cache de perfil")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")


# ============================================================
# MÉTRICAS DE CACHE
# ============================================================

class ProfileCacheMetrics:
    """
    🔧 NOVO: Métricas para monitorar a eficácia do cache de perfil.
    
    🔧 USO:
        metrics = ProfileCacheMetrics()
        metrics.record_hit()
        metrics.record_miss()
        print(metrics.get_hit_rate())  # 50.0%
    """
    
    def __init__(self):
        self._hits = 0
        self._misses = 0
    
    def record_hit(self) -> None:
        """Registra um acerto de cache."""
        self._hits += 1
    
    def record_miss(self) -> None:
        """Registra um erro de cache."""
        self._misses += 1
    
    def get_hit_rate(self) -> float:
        """Retorna o percentual de acertos."""
        total = self._hits + self._misses
        return round((self._hits / total * 100), 2) if total > 0 else 0.0
    
    def get_summary(self) -> dict:
        """Retorna um resumo das métricas."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.get_hit_rate(),
            "total": self._hits + self._misses
        }
    
    def reset(self) -> None:
        """Reseta todas as métricas."""
        self._hits = 0
        self._misses = 0


# 🔧 NOVO: Instância global de métricas
_profile_metrics = ProfileCacheMetrics()


# ============================================================
# FUNÇÕES DE CACHE
# ============================================================

async def get_cached_profile(user_id: str, db) -> Optional[Dict[str, Any]]:
    """
    Busca o perfil do cache Redis.

    🔧 USO:
        profile = await get_cached_profile(user_id, db)

    📋 PADRÃO:
        - Tenta Redis primeiro
        - 🔧 NOVO: Registra hit/miss nas métricas
        - Se falhar, retorna None (fallback para MongoDB)
    """
    if not redis_client:
        return None

    try:
        key = f"profile:{user_id}"
        data = await redis_client.get(key)
        if data:
            # 🔧 NOVO: Registra hit nas métricas
            _profile_metrics.record_hit()
            logger.debug(get_message("PROFILE_CACHE_HIT", "pt", user_id=user_id))
            return json.loads(data)
        
        # 🔧 NOVO: Registra miss nas métricas
        _profile_metrics.record_miss()
        logger.debug(get_message("PROFILE_CACHE_MISS", "pt", user_id=user_id))
        return None
        
    except Exception as e:
        # 🔧 NOVO: Registra miss nas métricas em caso de erro
        _profile_metrics.record_miss()
        logger.warning(f"⚠️ Erro ao buscar perfil no Redis: {e}")
        return None


async def set_cached_profile(user_id: str, profile: Dict[str, Any]) -> None:
    """
    Armazena o perfil no cache Redis.

    🔧 USO:
        await set_cached_profile(user_id, profile)

    📋 PADRÃO:
        - Usa setex com TTL (5 minutos)
        - Se Redis falhar, apenas loga (não quebra a requisição)
    """
    if not redis_client:
        return

    try:
        key = f"profile:{user_id}"
        await redis_client.setex(
            key,
            BALANCE_CACHE_TTL_SECONDS,
            json.dumps(profile, default=str)
        )
        logger.debug(get_message("PROFILE_CACHE_SET", "pt", user_id=user_id))
    except Exception as e:
        logger.warning(f"⚠️ Erro ao armazenar perfil no Redis: {e}")


async def invalidate_profile_cache(user_id: str) -> None:
    """
    Invalida o cache de perfil para um usuário.

    🔧 USO:
        await invalidate_profile_cache(user_id)

    📋 PADRÃO:
        - Segue o mesmo padrão de balance_cache.py e score_cache.py
    """
    if not redis_client:
        return

    try:
        key = f"profile:{user_id}"
        await redis_client.delete(key)
        logger.info(get_message("PROFILE_CACHE_INVALIDATED", "pt", user_id=user_id))
    except Exception as e:
        logger.warning(f"⚠️ Erro ao invalidar cache de perfil: {e}")


# ============================================================
# FUNÇÕES DE MÉTRICAS
# ============================================================

def get_profile_metrics() -> dict:
    """
    🔧 NOVO: Retorna as métricas atuais do cache de perfil.
    
    🔧 USO:
        metrics = get_profile_metrics()
        print(metrics["hit_rate"])  # 85.0
    
    📋 PADRÃO:
        - Útil para debug e monitoramento
        - Pode ser exposto via endpoint admin
    """
    return _profile_metrics.get_summary()


def reset_profile_metrics() -> None:
    """
    🔧 NOVO: Reseta as métricas do cache de perfil.
    
    🔧 USO:
        reset_profile_metrics()  # Reinicia os contadores
    """
    _profile_metrics.reset()
    logger.info("🔄 Métricas de perfil resetadas")


# ============================================================
# FUNÇÕES PRINCIPAIS
# ============================================================

def create_empty_profile(user_id: str) -> Dict[str, Any]:
    """
    Cria um perfil vazio com campos obrigatórios.

    🔧 USO:
        empty = create_empty_profile("user123")

    📋 PADRÃO:
        - Inclui todos os campos obrigatórios do modelo UserProfile
        - Validação de user_id
        - Campos completos (não apenas mínimo)

    Args:
        user_id: ID do usuário (string não vazia)

    Returns:
        dict: Dicionário com campos obrigatórios preenchidos

    Raises:
        ValueError: Se user_id for vazio ou None
    """
    # Validação de entrada
    if not user_id or not isinstance(user_id, str):
        logger.error(f"❌ user_id inválido: {user_id}")
        raise ValueError("user_id é obrigatório e deve ser uma string não vazia")

    now = datetime.now(timezone.utc)

    return {
        "user_id": user_id,
        "created_at": now,
        "updated_at": now,
        # Campos obrigatórios do modelo
        "psychology": {},
        "goals": {},
        "habits": {},
        "risk_tolerance": {},
        "dream_value": None,
        "dream_goal": None,
        "next_year_goals": None,
        "next_year_goal_value": None,
        "is_complete": False,
        "completion_percentage": 0.0
    }


def prepare_profile_response(
    profile: Optional[Dict[str, Any]],
    fallback_user_id: Optional[str] = None
) -> UserProfileResponse:
    """
    🔧 CORRIGIDO: Prepara o perfil para resposta com validação Pydantic.

    🔧 USO:
        response = prepare_profile_response(profile, fallback_user_id="user123")

    📋 PADRÃO:
        - Converte ObjectId para string
        - Adiciona campo 'id' a partir de '_id' ou 'user_id'
        - 🔧 NOVO: Retorna UserProfileResponse (validação Pydantic)
        - Log de aviso se profile for None

    Args:
        profile: Dicionário do perfil (pode ser None)
        fallback_user_id: ID do usuário para criar perfil vazio

    Returns:
        UserProfileResponse: Perfil validado com Pydantic
    """
    if not profile:
        if fallback_user_id:
            logger.info(get_message("PROFILE_CACHE_MISS", "pt", user_id=fallback_user_id))
            empty = create_empty_profile(fallback_user_id)
            return UserProfileResponse(**empty)
        # Log de aviso em vez de retorno silencioso
        logger.warning("⚠️ Profile é None e fallback_user_id não fornecido")
        return UserProfileResponse(**{})

    result = convert_objectid_to_str(profile)

    # ID consistente
    if "_id" in profile:
        result["id"] = str(profile["_id"])
    elif "user_id" in result:
        result["id"] = result["user_id"]
    elif fallback_user_id:
        result["id"] = fallback_user_id
    else:
        result["id"] = "unknown"
        logger.warning(f"⚠️ ID não encontrado no perfil: {profile}")

    # 🔧 NOVO: Validação com Pydantic
    try:
        return UserProfileResponse(**result)
    except Exception as e:
        logger.error(f"❌ Erro ao validar perfil com Pydantic: {e}", exc_info=True)
        # Fallback: retorna perfil vazio
        empty = create_empty_profile(fallback_user_id or result.get("user_id", "unknown"))
        return UserProfileResponse(**empty)


async def ensure_profile_collection(db) -> bool:
    """
    Garante que a coleção user_profiles existe com índices.

    🔧 USO:
        await ensure_profile_collection(db)

    📋 PADRÃO:
        - Cria índices para user_id (único) e updated_at
        - Índice composto para consultas comuns
        - Índice para is_complete
        - 🔧 CORRIGIDO: SEM TTL - dados mantidos para sempre

    Args:
        db: Conexão com o banco de dados

    Returns:
        bool: True se a coleção existe ou foi criada
    """
    collection_name = "user_profiles"

    try:
        # Verifica se a coleção existe
        collections = await db.list_collection_names()
        if collection_name not in collections:
            logger.warning(f"⚠️ Coleção '{collection_name}' não existe, criando...")
            await db.create_collection(collection_name)
            logger.info(f"✅ Coleção '{collection_name}' criada com sucesso")

        # Cria índices
        collection = db[collection_name]

        # Índice único para user_id (consulta por usuário)
        await collection.create_index("user_id", unique=True)
        logger.debug(f"✅ Índice 'user_id' criado em '{collection_name}'")

        # 🔧 CORRIGIDO: SEM TTL - mantém dados para sempre
        await collection.create_index("updated_at")
        logger.debug(f"✅ Índice 'updated_at' (sem TTL) criado em '{collection_name}'")

        # Índice composto para consultas comuns (user_id + updated_at)
        await collection.create_index([("user_id", 1), ("updated_at", -1)])
        logger.debug(f"✅ Índice composto '(user_id, updated_at)' criado em '{collection_name}'")

        # Índice para is_complete (perfis completos/incompletos)
        await collection.create_index("is_complete")
        logger.debug(f"✅ Índice 'is_complete' criado em '{collection_name}'")

        return True

    except Exception as e:
        # i18n no log de erro
        error_msg = get_message("ERROR_PROFILE_COLLECTION", "pt", error=str(e))
        logger.error(f"❌ {error_msg}", exc_info=True)
        return False


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. Garantir coleção (antes de qualquer operação):
   from app.utils.profile_utils import ensure_profile_collection
   await ensure_profile_collection(db)

2. Buscar perfil com cache:
   from app.utils.profile_utils import get_cached_profile, set_cached_profile
   
   profile = await get_cached_profile(user_id, db)
   if profile is None:
       profile = await db.user_profiles.find_one({"user_id": user_id})
       if profile:
           await set_cached_profile(user_id, profile)
       else:
           profile = create_empty_profile(user_id)

3. Preparar resposta (com validação Pydantic):
   from app.utils.profile_utils import prepare_profile_response
   response = prepare_profile_response(profile, fallback_user_id=user_id)

4. Invalidar cache ao atualizar:
   from app.utils.profile_utils import invalidate_profile_cache
   await db.user_profiles.update_one(...)
   await invalidate_profile_cache(user_id)

5. Ver métricas (debug/admin):
   from app.utils.profile_utils import get_profile_metrics
   metrics = get_profile_metrics()
   # metrics = {"hits": 80, "misses": 20, "hit_rate": 80.0, "total": 100}
"""


# ============================================================
# DECISÕES DOCUMENTADAS
# ============================================================
#
# ✅ Funções reutilizáveis para perfil
# ✅ create_empty_profile com campos obrigatórios
# ✅ prepare_profile_response com fallback
# ✅ ensure_profile_collection com logs
# ✅ Conversão de ObjectId centralizada
# ✅ 🔧 NOVO: Cache Redis para perfil (TTL: 5 minutos)
# ✅ 🔧 NOVO: Índices na coleção user_profiles
# ✅ 🔧 NOVO: Internacionalização (i18n) nos logs
# ✅ 🔧 NOVO: Validação de user_id
# ✅ 🔧 NOVO: Campos completos no create_empty_profile
# ✅ 🔧 NOVO: Métricas de hit/miss do cache
# ✅ 🔧 NOVO: Validação Pydantic no retorno
# ✅ 🔧 CORRIGIDO: Log de aviso quando profile é None
# ✅ 🔧 CORRIGIDO: ID consistente (usa _id > user_id > fallback)
# ✅ 🔧 CORRIGIDO: SEM TTL - dados mantidos para sempre
# ✅ Documentação completa com exemplos
#
# ❌ Não implementado (Pós-MVP):
#   - Pipeline de agregação para perfil completo
#
# 📋 CHANGELOG:
#   - v1: Versão inicial com funções básicas
#   - v2: Adicionado - Cache Redis, índices, i18n, validações (06/07/2026)
#   - v3: Removido - TTL do índice updated_at (dados mantidos para sempre) (06/07/2026)
#   - v4: Adicionado - Métricas de cache, validação Pydantic (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO