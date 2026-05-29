"""
Utilitário de Paginação para endpoints da API
Arquivo: backend/app/utils/pagination.py

🔧 MODIFICADO: Regra 2.8 - Adicionado logger para rastreamento
"""

from typing import Optional, List, Any, Tuple
from math import ceil
from pydantic import BaseModel

from app.utils.logger import setup_logger

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)


class PaginationParams(BaseModel):
    """Parâmetros de paginação recebidos via query string"""
    page: int = 1
    limit: int = 20
    
    @property
    def skip(self) -> int:
        return (self.page - 1) * self.limit
    
    @property
    def max_limit(self) -> int:
        return min(self.limit, 100)  # Máximo 100 itens por página


class PaginatedResponse(BaseModel):
    """Resposta padronizada com paginação"""
    items: List[Any]
    total: int
    page: int
    limit: int
    pages: int
    has_next: bool
    has_prev: bool


def paginate(items: List[Any], total: int, params: PaginationParams) -> PaginatedResponse:
    """Cria uma resposta paginada a partir dos dados"""
    pages = ceil(total / params.limit) if total > 0 else 1
    
    logger.debug(f"Paginação criada: page={params.page}, limit={params.limit}, total={total}, pages={pages}")
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        limit=params.limit,
        pages=pages,
        has_next=params.page < pages,
        has_prev=params.page > 1
    )


async def paginate_query(collection, query: dict, params: PaginationParams, sort: Optional[Tuple] = None):
    """
    Executa uma query paginada no MongoDB
    Retorna (items, total)
    """
    logger.debug(f"Executando query paginada: skip={params.skip}, limit={params.limit}, query={query}")
    
    cursor = collection.find(query)
    
    if sort:
        cursor = cursor.sort(sort)
    
    total = await collection.count_documents(query)
    cursor = cursor.skip(params.skip).limit(params.limit)
    items = await cursor.to_list(length=params.limit)
    
    logger.debug(f"Query paginada concluída: {len(items)} itens retornados de {total} totais")
    
    return items, total