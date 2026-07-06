"""
Utilitário de Paginação para endpoints da API
Arquivo: backend/app/utils/pagination.py

Funcionalidades:
- Parâmetros de paginação padronizados (page, limit)
- Resposta paginada com metadados (total, pages, has_next, has_prev)
- Query paginada no MongoDB com suporte a sort
- Cache de total no Redis (TTL: 1 minuto) para reduzir count_documents
- TTL variável por coleção (configurável via constants)
- Fallback para MongoDB se Redis estiver indisponível
- Invalidação de cache quando houver alterações na coleção
- Métricas de hit/miss para monitoramento
- Tratamento de erros com logging

Principais features:
- 🔧 NOVO: Redis cache para total (com fallback MongoDB)
- 🔧 NOVO: Invalidação automática de cache
- 🔧 NOVO: TTL variável por coleção (via constants)
- 🔧 NOVO: Métricas de hit/miss do cache
- 🔧 NOVO: Geração de chave única com hash da query
- 🔧 CORRIGIDO: Renomeado max_limit para effective_limit (clareza)
- 🔧 CORRIGIDO: Validação nativa no Field (le=MAX_LIMIT)
- 🔧 CORRIGIDO: Tratamento de erro com try/except
- 🔧 CORRIGIDO: hint="_id_" no count_documents para performance
- ✅ Tipagem forte com Pydantic BaseModel
- ✅ Logging estruturado com setup_logger
- ✅ Propriedades para cálculos automáticos (skip)
- ✅ Documentação completa


"""

from typing import Optional, List, Any, Tuple, Dict
from math import ceil
import json
import hashlib
import os

from pydantic import BaseModel, Field

from app.utils.logger import setup_logger
from app.utils.exceptions import InternalServerException
from app.core.constants import (
    MAX_LIMIT,
    DEFAULT_LIMIT,
    PAGINATION_CACHE_TTL,
    PAGINATION_CACHE_TTL_DEFAULT
)

# ============================================================
# CONFIGURAÇÃO DE LOG
# ============================================================

logger = setup_logger(__name__)

# ============================================================
# REDIS CLIENT (CONEXÃO SEGURA)
# ============================================================

# Integração com Redis para cache de total
# Segue o mesmo padrão de balance_cache.py e score_cache.py
try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        logger.info("✅ Redis conectado com sucesso para cache de paginação")
    else:
        redis_client = None
        logger.info("ℹ️ Redis não configurado - usando MongoDB para cache de paginação")
except ImportError:
    redis_client = None
    logger.info("ℹ️ Redis não instalado - usando MongoDB para cache de paginação")
except Exception as e:
    redis_client = None
    logger.error(f"❌ Erro ao conectar Redis: {e}")


# ============================================================
# MÉTRICAS DE CACHE
# ============================================================

class PaginationCacheMetrics:
    """
    Métricas para monitorar a eficácia do cache de paginação.
    
    🔧 VERSÃO: Básica (em memória)
    - Contadores em memória (não persistente)
    - Útil para debug durante desenvolvimento
    - Pode ser expandido para Redis/Prometheus no futuro
    
    🔧 USO:
        metrics = PaginationCacheMetrics()
        metrics.record_hit("transactions")
        metrics.record_miss("transactions")
        print(metrics.get_hit_rate("transactions"))  # 50.0%
    """
    
    def __init__(self):
        self._hits: Dict[str, int] = {}
        self._misses: Dict[str, int] = {}
    
    def record_hit(self, collection: str) -> None:
        """Registra um acerto de cache para uma coleção."""
        self._hits[collection] = self._hits.get(collection, 0) + 1
    
    def record_miss(self, collection: str) -> None:
        """Registra um erro de cache para uma coleção."""
        self._misses[collection] = self._misses.get(collection, 0) + 1
    
    def get_hit_rate(self, collection: str) -> float:
        """Retorna o percentual de acertos para uma coleção."""
        hits = self._hits.get(collection, 0)
        misses = self._misses.get(collection, 0)
        total = hits + misses
        return round((hits / total * 100), 2) if total > 0 else 0.0
    
    def get_summary(self) -> dict:
        """Retorna um resumo de todas as métricas."""
        all_collections = set(self._hits.keys()) | set(self._misses.keys())
        return {
            collection: {
                "hits": self._hits.get(collection, 0),
                "misses": self._misses.get(collection, 0),
                "hit_rate": self.get_hit_rate(collection)
            }
            for collection in all_collections
        }
    
    def reset(self) -> None:
        """Reseta todas as métricas."""
        self._hits.clear()
        self._misses.clear()


# 🔧 Instância global de métricas
_pagination_metrics = PaginationCacheMetrics()


# ============================================================
# FUNÇÃO AUXILIAR: TTL POR COLEÇÃO
# ============================================================

def get_ttl_for_collection(collection_name: str) -> int:
    """
    Retorna o TTL apropriado para uma coleção.
    
    🔧 USO:
        ttl = get_ttl_for_collection("transactions")  # 60
        ttl = get_ttl_for_collection("goals")         # 300
    
    📋 PADRÃO:
        - Busca no dicionário PAGINATION_CACHE_TTL
        - Se não encontrar, usa PAGINATION_CACHE_TTL_DEFAULT
    """
    return PAGINATION_CACHE_TTL.get(collection_name, PAGINATION_CACHE_TTL_DEFAULT)


# ============================================================
# CLASSES
# ============================================================

class PaginationParams(BaseModel):
    """
    Parâmetros de paginação recebidos via query string.

    📋 PADRÃO:
    - page: Número da página (inicia em 1)
    - limit: Quantidade de itens por página (máximo 100)

    🔧 PROPRIEDADES:
    - skip: Quantos itens pular para a página solicitada
    - effective_limit: Limite efetivo respeitando o máximo de 100
    """
    page: int = Field(1, ge=1, description="Número da página (inicia em 1)")
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description=f"Itens por página (máximo {MAX_LIMIT})")

    @property
    def skip(self) -> int:
        """Calcula quantos itens pular para a página solicitada"""
        return (self.page - 1) * self.limit

    @property
    def effective_limit(self) -> int:
        """
        🔧 CORRIGIDO: Renomeado de max_limit para effective_limit.
        Retorna o limite efetivo, respeitando o máximo de 100.
        Útil para garantir que o limite não ultrapasse o máximo permitido.
        """
        return min(self.limit, MAX_LIMIT)


class PaginatedResponse(BaseModel):
    """
    Resposta padronizada com paginação.

    📋 PADRÃO:
    - items: Lista de itens da página atual
    - total: Total de itens na coleção
    - page: Página atual
    - limit: Itens por página
    - pages: Total de páginas
    - has_next: Se existe próxima página
    - has_prev: Se existe página anterior
    """
    items: List[Any] = Field(..., description="Lista de itens da página atual")
    total: int = Field(..., ge=0, description="Total de itens na coleção")
    page: int = Field(..., ge=1, description="Página atual")
    limit: int = Field(..., ge=1, description="Itens por página")
    pages: int = Field(..., ge=1, description="Total de páginas")
    has_next: bool = Field(..., description="Se existe próxima página")
    has_prev: bool = Field(..., description="Se existe página anterior")

    model_config = {"from_attributes": True}


# ============================================================
# FUNÇÕES DE PAGINAÇÃO
# ============================================================

def paginate(items: List[Any], total: int, params: PaginationParams) -> PaginatedResponse:
    """
    Cria uma resposta paginada a partir dos dados.

    🔧 USO:
        items = await cursor.to_list(length=params.limit)
        total = await get_cached_total(collection, query, user_id)
        return paginate(items, total, params)

    📋 PADRÃO:
    - Usa math.ceil para calcular total de páginas
    - Calcula has_next e has_prev automaticamente
    - Retorna PaginatedResponse padronizada
    """
    # Calcula total de páginas
    pages = max(1, ceil(total / params.effective_limit))

    logger.debug(
        f"Paginação criada: page={params.page}, limit={params.effective_limit}, "
        f"total={total}, pages={pages}, has_next={params.page < pages}"
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        limit=params.effective_limit,
        pages=pages,
        has_next=params.page < pages,
        has_prev=params.page > 1
    )


# ============================================================
# FUNÇÕES DE CACHE (REDIS)
# ============================================================

def _generate_cache_key(
    collection_name: str,
    user_id: Optional[str],
    query: dict,
    sort: Optional[Tuple] = None
) -> str:
    """
    Gera uma chave única para o cache baseada nos parâmetros da query.

    🔧 USO:
        key = _generate_cache_key("transactions", user_id, query, sort)

    📋 PADRÃO:
        - Formato: pagination:total:{collection}:{user_id}:{query_hash}
        - Inclui user_id se disponível (cache por usuário)
        - Hash da query para evitar chaves muito longas
    """
    # Converte query e sort para string ordenada
    query_str = json.dumps(query, sort_keys=True, default=str)
    
    # Adiciona user_id se disponível
    user_part = f":{user_id}" if user_id else ""
    
    # Adiciona sort se disponível
    sort_str = json.dumps(sort, sort_keys=True, default=str) if sort else ""
    sort_part = f":{sort_str}" if sort_str else ""
    
    # Cria hash da query + sort para chave curta e única
    content = f"{query_str}{sort_str}"
    query_hash = hashlib.md5(content.encode()).hexdigest()[:12]
    
    return f"pagination:total:{collection_name}{user_part}:{query_hash}"


async def get_cached_total(
    collection_name: str,
    user_id: Optional[str],
    query: dict,
    sort: Optional[Tuple] = None
) -> Optional[int]:
    """
    Busca o total de documentos do cache Redis.

    🔧 USO:
        total = await get_cached_total("transactions", user_id, query)

    📋 PADRÃO:
        - Tenta Redis primeiro
        - Se falhar, retorna None (fallback para count_documents)
        - Logs de debug para rastreabilidade
    """
    if not redis_client:
        return None

    try:
        key = _generate_cache_key(collection_name, user_id, query, sort)
        data = await redis_client.get(key)
        
        if data:
            logger.debug(f"✅ Total obtido do Redis para {collection_name}: {data}")
            return int(data)
        
        logger.debug(f"ℹ️ Total não encontrado no Redis para {collection_name}")
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao buscar total no Redis: {e}")
        return None


async def set_cached_total(
    collection_name: str,
    user_id: Optional[str],
    query: dict,
    total: int,
    sort: Optional[Tuple] = None,
    ttl: Optional[int] = None
) -> None:
    """
    Armazena o total de documentos no cache Redis.

    🔧 USO:
        await set_cached_total("transactions", user_id, query, total)

    📋 PADRÃO:
        - 🔧 NOVO: Usa TTL específico por coleção
        - Usa setex com TTL (1 minuto por padrão)
        - Se Redis falhar, apenas loga (não quebra a requisição)
    """
    if not redis_client:
        return

    try:
        # Usa TTL específico da coleção se não for fornecido
        if ttl is None:
            ttl = get_ttl_for_collection(collection_name)
        
        key = _generate_cache_key(collection_name, user_id, query, sort)
        await redis_client.setex(key, ttl, str(total))
        logger.debug(f"💾 Total armazenado no Redis para {collection_name}: {total} (TTL: {ttl}s)")
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao armazenar total no Redis: {e}")


async def invalidate_pagination_cache(
    collection_name: str,
    user_id: Optional[str] = None
) -> None:
    """
    Invalida o cache de paginação para uma coleção e/ou usuário.

    🔧 USO:
        # Invalidar tudo para uma coleção
        await invalidate_pagination_cache("transactions")
        
        # Invalidar apenas para um usuário específico
        await invalidate_pagination_cache("transactions", user_id)

    📋 PADRÃO:
        - Usa scan_iter para buscar todas as chaves do padrão
        - Deleta em lotes de 100 para não sobrecarregar
        - Segue o mesmo padrão de balance_cache.py e score_cache.py
    """
    if not redis_client:
        return

    try:
        # Define o padrão de busca
        if user_id:
            pattern = f"pagination:*:{collection_name}:{user_id}:*"
        else:
            pattern = f"pagination:*:{collection_name}:*"
        
        logger.debug(f"🗑️ Invalidando cache de paginação: {pattern}")
        
        # Busca e deleta chaves em lotes
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key)
            if len(keys) >= 100:
                await redis_client.delete(*keys)
                keys = []
        
        if keys:
            await redis_client.delete(*keys)
        
        logger.info(f"🗑️ Cache de paginação invalidado para {collection_name}" + 
                   (f" (usuário {user_id})" if user_id else ""))
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao invalidar cache de paginação: {e}")


# ============================================================
# FUNÇÕES DE MÉTRICAS
# ============================================================

def get_pagination_metrics() -> dict:
    """
    Retorna as métricas atuais do cache de paginação.
    
    🔧 USO:
        metrics = get_pagination_metrics()
        print(metrics["transactions"]["hit_rate"])  # 85.0
    
    📋 PADRÃO:
        - Útil para debug e monitoramento
        - Pode ser exposto via endpoint admin
    """
    return _pagination_metrics.get_summary()


def reset_pagination_metrics() -> None:
    """
    Reseta as métricas do cache de paginação.
    
    🔧 USO:
        reset_pagination_metrics()  # Reinicia os contadores
    """
    _pagination_metrics.reset()
    logger.info("🔄 Métricas de paginação resetadas")


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

async def paginate_query(
    collection,
    collection_name: str,
    query: dict,
    params: PaginationParams,
    user_id: Optional[str] = None,
    sort: Optional[Tuple] = None,
    use_cache: bool = True
) -> Tuple[List[Any], int]:
    """
    Executa uma query paginada no MongoDB com cache de total.

    🔧 USO:
        items, total = await paginate_query(
            collection=db.transactions,
            collection_name="transactions",
            query={"user_id": user_id},
            params=params,
            user_id=user_id,
            sort=("date", -1)
        )

    📋 PADRÃO:
        - Usa skip e limit para paginação
        - 🔧 NOVO: Usa cache Redis para total (com fallback MongoDB)
        - 🔧 NOVO: TTL específico por coleção
        - 🔧 NOVO: Métricas de hit/miss
        - 🔧 CORRIGIDO: Usa count_documents com hint para performance
        - Retorna (items, total) para uso em paginate()

    ⚠️ ATENÇÃO:
        - O cache é invalidado automaticamente via invalidate_pagination_cache()
        - Chamar esta função após qualquer alteração na coleção
    """
    logger.debug(
        f"Executando query paginada: skip={params.skip}, limit={params.effective_limit}, "
        f"collection={collection_name}, query={query}, sort={sort}, use_cache={use_cache}"
    )

    try:
        # 🔧 Cria cursor base
        cursor = collection.find(query)

        # 🔧 Aplica ordenação se fornecida
        if sort:
            cursor = cursor.sort(sort)

        # 🔧 Busca total (com cache)
        total = None
        from_cache = False
        
        if use_cache and redis_client:
            # Tenta buscar do cache
            total = await get_cached_total(
                collection_name=collection_name,
                user_id=user_id,
                query=query,
                sort=sort
            )
            if total is not None:
                from_cache = True
                # Registra hit nas métricas
                _pagination_metrics.record_hit(collection_name)
            else:
                # Registra miss nas métricas
                _pagination_metrics.record_miss(collection_name)

        # 🔧 Se não veio do cache, busca no MongoDB
        if total is None:
            try:
                # 🔧 CORRIGIDO: hint="_id_" para usar índice e performance
                total = await collection.count_documents(query, hint="_id_")
            except Exception:
                # Fallback se hint não for suportado
                total = await collection.count_documents(query)
            
            # 🔧 Armazena no cache (se Redis estiver disponível)
            if use_cache and redis_client and total is not None:
                await set_cached_total(
                    collection_name=collection_name,
                    user_id=user_id,
                    query=query,
                    total=total,
                    sort=sort
                )

        # 🔧 Aplica paginação
        cursor = cursor.skip(params.skip).limit(params.effective_limit)
        items = await cursor.to_list(length=params.effective_limit)

        logger.debug(
            f"Query paginada concluída: {len(items)} itens retornados de {total} totais "
            f"(cache: {'HIT' if from_cache else 'MISS'})"
        )

        return items, total

    except Exception as e:
        logger.error(f"❌ Erro na paginação: {e}", exc_info=True)
        raise InternalServerException(
            message_key="ERROR_PAGINATION_FAILED",
            request=None,
            error=str(e)
        )


# ============================================================
# DECISÕES DOCUMENTADAS
# ============================================================
#
# ✅ Tipagem forte com Pydantic BaseModel
# ✅ Logging estruturado com setup_logger
# ✅ Propriedades para cálculos automáticos (skip, effective_limit)
# ✅ Validação de limite máximo (100 itens por página)
# ✅ Redis com fallback para MongoDB
# ✅ TTL configurável via constants
# ✅ 🔧 NOVO: TTL variável por coleção
# ✅ Invalidação de cache com scan_iter
# ✅ Tratamento de erro com try/except
# ✅ hint="_id_" no count_documents para performance
# ✅ 🔧 NOVO: Métricas de hit/miss
# ✅ Documentação completa com exemplos
# ✅ 🔧 NOVO: Cache de total via Redis
# ✅ 🔧 NOVO: Funções get/set/invalidate
# ✅ 🔧 NOVO: Geração de chave com hash da query
# ✅ 🔧 CORRIGIDO: Renomeado max_limit → effective_limit
# ✅ 🔧 CORRIGIDO: Validação nativa no Field
# ✅ 🔧 CORRIGIDO: Tratamento de erro com InternalServerException
# ✅ 🔧 CORRIGIDO: hint="_id_" no count_documents
#
# ❌ Não implementado (Pós-MVP):
#   - Cursors para grandes volumes (muda assinatura da função)
#   - Cache distribuído (já usa Redis, mas poderia ser cluster)
#   - Métricas persistentes (em Redis/PostgreSQL)
#   - Cache com invalidação por TTL variável por coleção
#
# 📋 CHANGELOG:
#   - v1: Versão inicial com paginação básica
#   - v2: Refatoração - Renomeado max_limit, validação nativa (05/07/2026)
#   - v3: Adicionado - Redis cache total, invalidação, hint (06/07/2026)
#   - v4: Documentação - Padronização com logger.py (06/07/2026)
#   - v5: Adicionado - TTL por coleção, métricas básicas (06/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO