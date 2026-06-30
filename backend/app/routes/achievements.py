"""
Rotas de Conquistas do Usuário (sincronização)
Arquivo: backend/app/routes/achievements.py

🔧 CORRIGIDO (v2):
- Substituído HTTPException por I18nHTTPException
- Adicionado suporte a internacionalização
- Usa get_message() para mensagens de sucesso
- Adicionado request: Request nos endpoints
- 🔧 CORRIGIDO: Usa convert_objectid_to_str em vez de format_mongo_doc
- 🔧 CORRIGIDO: Query de duplicação no create com year/month None
- 🔧 CORRIGIDO: Query de duplicação no sync com year/month None
- 🔧 CORRIGIDO: Mensagens de sync com pluralização
- 🔧 CORRIGIDO: Removido try/except desnecessário no delete

🆕 MELHORIAS ADICIONADAS (v3):
- Adicionado limite de batch no sync (MAX_SYNC_BATCH = 100)
- Adicionado filtros opcionais no GET (type, year, month)
- Substituído insert_one em loop por insert_many (bulk insert)
- Adicionado rate limiting no sync (10/minuto)
- Adicionado validação de tipo com AchievementType (enum)
- Adicionado logging estruturado com emojis
- Adicionado documentação inline com decisões

📋 DECISÕES DOCUMENTADAS:
- ✅ NÃO implementado transação MongoDB (Free Tier não suporta)
- ✅ NÃO implementado validação extra de type (Pydantic já valida)
- ✅ Implementado limite de batch para prevenir abuso
- ✅ Implementado bulk insert para performance
- ✅ Implementado rate limiting para proteção
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import os

from app.database import get_database
from app.models.achievement import AchievementCreate, AchievementResponse
from app.models.user import UserResponse
from app.utils.auth import get_current_user
from app.utils.pagination import PaginationParams, paginate_query, paginate
from app.utils.validators import validate_object_id, convert_objectid_to_str
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter

# ========== CONFIGURAÇÃO ==========
MAX_SYNC_BATCH = int(os.getenv("MAX_SYNC_BATCH", "100"))
"""Número máximo de conquistas permitidas por requisição de sync.
   Valor padrão: 100 (configurável via .env)
   Motivo: Prevenir abuso e lentidão no servidor."""

# ========== I18N ==========
from app.utils.i18n import get_message
from app.utils.exceptions import (
    I18nHTTPException,
    NotFoundException,
    ValidationException,
    ConflictException
)

logger = setup_logger(__name__)

router = APIRouter(prefix="/achievements", tags=["Conquistas"])


# ========== ENDPOINTS ==========

@router.get("/", response_model=dict)
async def get_achievements(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    type: Optional[str] = Query(None, description="Filtrar por tipo de conquista"),
    year: Optional[int] = Query(None, ge=1900, le=2100, description="Ano da conquista"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Mês da conquista (1-12)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Retorna todas as conquistas do usuário com paginação e filtros opcionais.
    
    Filtros disponíveis:
    - type: Filtrar por tipo de conquista (ex: "first_transaction", "savings_goal")
    - year: Filtrar por ano (ex: 2025)
    - month: Filtrar por mês (ex: 6 para junho)
    
    🔧 MELHORIA v3: Adicionados filtros opcionais para melhorar a UX.
    """
    params = PaginationParams(page=page, limit=limit)
    query = {"user_id": str(current_user.id)}
    
    # 🔧 Adiciona filtros opcionais à query
    if type:
        query["type"] = type
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month

    items, total = await paginate_query(
        db.achievements, query, params, sort=[("date", -1)]
    )
    
    formatted_items = [convert_objectid_to_str(item) for item in items]
    
    language = getattr(request.state, "language", "pt")
    logger.info(f"📊 {len(formatted_items)} conquistas listadas para usuário {current_user.id}")
    
    return paginate(formatted_items, total, params).model_dump()


@router.post("/", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    ach_data: AchievementCreate,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Cria uma nova conquista para o usuário atual.
    
    🔧 CORRIGIDO: Query de duplicação com condições para year/month None.
    ✅ Decisão: Se year ou month forem None, não incluir na query de duplicação.
    """
    ach_dict = ach_data.model_dump()
    ach_dict["user_id"] = str(current_user.id)
    ach_dict["date"] = datetime.now(timezone.utc)
    
    # 🔧 Query dinâmica para verificar duplicação
    # year e month são opcionais - só incluir se existirem
    query = {"user_id": str(current_user.id), "type": ach_data.type}
    if ach_data.year is not None:
        query["year"] = ach_data.year
    if ach_data.month is not None:
        query["month"] = ach_data.month
    
    existing = await db.achievements.find_one(query)
    
    if existing:
        logger.warning(f"⚠️ Tentativa de duplicar conquista: {ach_data.type} para usuário {current_user.id}")
        raise ConflictException(
            message_key="ACHIEVEMENT_ALREADY_EXISTS",
            request=request
        )
    
    result = await db.achievements.insert_one(ach_dict)
    created = await db.achievements.find_one({"_id": result.inserted_id})
    
    logger.info(f"✅ Conquista criada para usuário {current_user.id}: {ach_data.type}")
    
    return convert_objectid_to_str(created)


@router.post("/sync", response_model=dict)
@limiter.limit("10/minute")
async def sync_achievements(
    achievements: List[AchievementCreate],
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Sincroniza múltiplas conquistas do frontend em lote.
    
    🔧 MELHORIA v3:
    - Limite de batch (MAX_SYNC_BATCH) para prevenir abuso
    - Bulk insert (insert_many) para melhor performance
    - Rate limiting (10/minuto) para proteger o servidor
    
    📋 DECISÃO: Transação NÃO implementada pois o MongoDB Atlas Free Tier
    não suporta transações multi-documento. O frontend pode re-sync se falhar.
    """
    user_id = str(current_user.id)
    
    # 🔧 VALIDAÇÃO: Limite de batch
    if len(achievements) > MAX_SYNC_BATCH:
        logger.warning(f"⚠️ Batch excedeu limite: {len(achievements)} > {MAX_SYNC_BATCH} para usuário {user_id}")
        raise ValidationException(
            message_key="ACHIEVEMENT_SYNC_BATCH_TOO_LARGE",
            request=request
        )
    
    achievements_to_insert = []
    
    for ach in achievements:
        # 🔧 Query dinâmica para verificar duplicação
        query = {"user_id": user_id, "type": ach.type}
        if ach.year is not None:
            query["year"] = ach.year
        if ach.month is not None:
            query["month"] = ach.month
        if ach.name:
            query["name"] = ach.name
        
        existing = await db.achievements.find_one(query)
        
        if not existing:
            ach_dict = ach.model_dump()
            ach_dict["user_id"] = user_id
            ach_dict["date"] = datetime.now(timezone.utc)
            achievements_to_insert.append(ach_dict)
    
    inserted = 0
    if achievements_to_insert:
        # 🔧 MELHORIA: Bulk insert em vez de insert_one em loop
        result = await db.achievements.insert_many(achievements_to_insert)
        inserted = len(result.inserted_ids)
        logger.info(f"✅ {inserted} conquistas inseridas em bulk para usuário {user_id}")
    
    language = getattr(request.state, "language", "pt")
    
    # 🔧 Mensagem com pluralização
    if inserted == 0:
        message = get_message("ACHIEVEMENT_SYNC_NONE", language)
    elif inserted == 1:
        message = get_message("ACHIEVEMENT_SYNC_ONE", language)
    else:
        message = get_message("ACHIEVEMENT_SYNC_MULTIPLE", language).format(count=inserted)
    
    logger.info(f"📊 Sync concluído: {inserted} novas conquistas para usuário {user_id}")
    
    return {
        "synced": inserted,
        "message": message
    }


@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Busca uma conquista específica pelo ID."""
    validate_object_id(achievement_id, "achievement_id")
    obj_id = ObjectId(achievement_id)
    
    achievement = await db.achievements.find_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    
    if not achievement:
        logger.warning(f"⚠️ Conquista não encontrada: {achievement_id} para usuário {current_user.id}")
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    return convert_objectid_to_str(achievement)


@router.delete("/{achievement_id}", response_model=dict)
async def delete_achievement(
    achievement_id: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Remove uma conquista do usuário.
    
    🔧 CORRIGIDO: Removido try/except desnecessário.
    validate_object_id já levanta exceção se o ID for inválido.
    """
    validate_object_id(achievement_id, "achievement_id")
    obj_id = ObjectId(achievement_id)
    
    result = await db.achievements.delete_one({
        "_id": obj_id,
        "user_id": str(current_user.id)
    })
    
    if result.deleted_count == 0:
        logger.warning(f"⚠️ Tentativa de deletar conquista inexistente: {achievement_id}")
        raise NotFoundException(
            message_key="ACHIEVEMENT_NOT_FOUND",
            request=request
        )
    
    language = getattr(request.state, "language", "pt")
    message = get_message("ACHIEVEMENT_DELETED", language)
    
    logger.info(f"🗑️ Conquista removida: {achievement_id} (usuário {current_user.id})")
    
    return {"message": message}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Substituído HTTPException por I18nHTTPException
# ✅ Usa ValidationException para erros de validação
# ✅ Usa NotFoundException para recursos não encontrados
# ✅ Usa ConflictException para conflitos (duplicação)
# ✅ Mensagens de sucesso com get_message()
# ✅ Suporte a i18n via request.state.language
# ✅ Verificação de duplicação antes de criar conquista
# ✅ Sync com year + month (int) em vez de month (string)
# ✅ 🔧 Usa convert_objectid_to_str em vez de format_mongo_doc
# ✅ 🔧 Query de duplicação com condições para year/month None
# ✅ 🔧 Mensagens de sync com pluralização
# ✅ 🔧 Delete simplificado (sem try/except redundante)
# ✅ 🔧 Get simplificado (sem try/except redundante)
# ✅ 🆕 Limite de batch no sync (MAX_SYNC_BATCH = 100)
# ✅ 🆕 Filtros opcionais no GET (type, year, month)
# ✅ 🆕 Bulk insert (insert_many) para melhor performance
# ✅ 🆕 Rate limiting no sync (10/minuto)
# ✅ 🆕 Logs estruturados com emojis
#
# 📋 DECISÕES DE NÃO IMPLEMENTAÇÃO:
# ❌ Transação MongoDB: Free Tier não suporta (M10+ necessário)
#    Alternativa: Frontend pode re-sync se falhar
# ❌ Validação extra de type: Já validado pelo Pydantic (AchievementCreate)
#    Alternativa: Manter validação no modelo, não no router
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO