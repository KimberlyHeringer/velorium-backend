"""
Rotas de Notificações
Arquivo: backend/app/routes/notifications.py

Funcionalidades:
- POST /notifications/register-token: Registrar token push
- POST /notifications/enable: Ativar notificações
- POST /notifications/disable: Desativar notificações
- POST /notifications/test: Enviar notificação de teste
- GET /notifications/status: Status das notificações
- PUT /notifications/preferences: Atualizar preferências
- POST /notifications/trigger-daily: Acionar worker diário
- POST /notifications/cleanup-tokens: Limpar tokens inativos

🆕 NOVOS ENDPOINTS (CRUD):
- GET /notifications/: Listar notificações com paginação
- GET /notifications/unread: Contagem de não lidas
- GET /notifications/{id}: Buscar notificação específica
- PUT /notifications/{id}/read: Marcar como lida
- PUT /notifications/read-all: Marcar todas como lidas
- DELETE /notifications/{id}: Deletar notificação

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting por usuário
- Múltiplos tokens por usuário
- Templates em múltiplos idiomas
- Categorias de notificação (score, bills, goals, tips, all)
- Cache de insights (24h)
- Worker de limpeza de tokens inativos (30 dias)
- Validação de Expo token
- 🔧 NOVO: CRUD completo de notificações in-app

Versão: v2.4 (CRUD adicionado)
📅 ATUALIZADO EM: 14/07/2026
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, Query
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Literal
import os
import json
import httpx
from bson import ObjectId
from enum import Enum

from app.utils.auth import get_current_user
from app.models.user import UserResponse
from app.database import get_database
from app.utils.logger import setup_logger
from app.utils.currency import from_cents
from app.services.ia_service import obter_resposta_ia_async

# ========== IMPORTS CORRETOS ==========
from app.core.constants import INACTIVE_TOKEN_DAYS, EXPO_API_URL
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.notifications import send_push_notification

# ✅ CORRIGIDO: I18n imports com I18nHTTPException
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException
from app.utils.i18n import get_message

# ✅ CORRIGIDO: Imports do model e schemas (padronizado)
from app.models.notification import (
    NotificationType,
    NotificationCategory as NotificationCategoryEnum
)
from app.schemas.notification import (
    NotificationResponse as NotificationInAppResponse,
    NotificationListResponse,
    UnreadCountResponse,
    ReadAllResponse
)

logger = setup_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notificações"])


# ========== CONSTANTES ==========
MAX_INSTALLMENTS_DAYS_WARNING = 3  # Alertar sobre parcelas com vencimento em até 3 dias


# ========== ENUMS ==========

class NotificationCategory(str, Enum):
    """Categorias de notificação"""
    ALL = "all"
    SCORE = "score"
    BILLS = "bills"
    GOALS = "goals"
    TIPS = "tips"


# ========== SCHEMAS ==========

class RegisterTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Expo push token")
    device_name: Optional[str] = Field(None, max_length=100, description="Nome do dispositivo")
    device_platform: Optional[Literal["ios", "android", "web"]] = Field(
        None, description="ios, android, web"
    )
    
    @field_validator('token')
    @classmethod
    def validate_expo_token(cls, v: str) -> str:
        if not v.startswith("ExponentPushToken["):
            raise ValueError('Token deve ser um Expo push token válido')
        return v


class SendTestNotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Título da notificação")
    body: str = Field(..., min_length=1, max_length=500, description="Corpo da notificação")


class UpdatePreferencesRequest(BaseModel):
    categories: Optional[List[NotificationCategory]] = Field(None, description="Categorias ativas")
    push_enabled: Optional[bool] = Field(None, description="Ativar/desativar notificações")
    language: Optional[str] = Field(None, description="Idioma preferido (pt, en, es, zh)")


class NotificationResponse(BaseModel):
    success: bool
    message: str


class NotificationStatusResponse(BaseModel):
    push_enabled: bool
    has_token: bool
    devices_count: int
    categories: List[str]
    language: str
    platform: str
    last_notification_at: Optional[datetime] = None


# ========== FUNÇÕES AUXILIARES ==========

async def generate_daily_insight(user_id: str, db, language: str = "pt") -> Optional[str]:
    """
    Gera um insight financeiro diário usando IA no idioma do usuário.
    Cache de 24h para evitar chamadas repetidas à IA.
    """
    try:
        today = datetime.now(timezone.utc).date()
        today_start = datetime.combine(today, datetime.min.time())
        
        existing = await db.notification_logs.find_one({
            "user_id": user_id,
            "type": "daily_insight",
            "sent_at": {"$gte": today_start}
        })
        
        if existing:
            logger.debug(f"💾 Cache hit para insight do usuário {user_id}")
            return existing.get("message")
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return None
        
        score_doc = await db.score_history.find_one(
            {"user_id": user_id},
            sort=[("date", -1)]
        )
        score = score_doc.get("score", 0) if score_doc else 0
        
        today_date = datetime.now(timezone.utc)
        three_days_later = today_date + timedelta(days=3)
        upcoming_bills = await db.bills.find({
            "user_id": user_id,
            "paid": False,
            "installments.start_date": {"$lte": three_days_later}
        }).to_list(10)
        
        goals = await db.goals.find({
            "user_id": user_id,
            "completed": False,
            "current": {"$ne": 0}
        }).to_list(10)
        
        near_completion_goals = []
        for goal in goals:
            target = goal.get("target", 1)
            current = goal.get("current", 0)
            if target > 0 and (current / target) >= 0.8:
                near_completion_goals.append(goal)
        
        context = f"""
Dados financeiros do usuário:
- Score financeiro: {score}/1000
- Contas a vencer nos próximos 3 dias: {len(upcoming_bills)}
- Metas próximas da conclusão (>80%): {len(near_completion_goals)}

Gere uma mensagem curta (1-2 frases), motivadora e personalizada, 
que ajude o usuário a melhorar sua saúde financeira.
Seja direta e prática.
Responda no idioma: {language}
"""
        
        resposta = await obter_resposta_ia_async(
            system_message="Você é Veloria, uma assistente financeira personalizada.",
            user_message=context,
            conversation_history=""
        )
        
        return resposta.strip()
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar insight diário: {e}")
        return None


async def send_daily_notifications_worker(db):
    """
    Worker para enviar notificações proativas diariamente
    Deve ser chamado por scheduler às 09:00
    """
    logger.info("🚀 Iniciando worker de notificações diárias")
    
    users = await db.users.find({
        "push_enabled": True,
        "expo_push_tokens": {"$exists": True, "$ne": []}
    }).to_list(1000)
    
    sent_count = 0
    failed_count = 0
    skipped_count = 0
    
    for user in users:
        try:
            preferences = user.get("notification_preferences", {})
            categories = preferences.get("categories", ["all"])
            language = preferences.get("language", "pt")
            
            if "all" not in categories and "tips" not in categories:
                skipped_count += 1
                continue
            
            insight = await generate_daily_insight(str(user["_id"]), db, language)
            
            titles = {
                "pt": "💡 Veloria | Insight do Dia",
                "en": "💡 Veloria | Daily Insight",
                "es": "💡 Veloria | Perspectiva del Día",
                "zh": "💡 Veloria | 每日洞察"
            }
            title = titles.get(language, titles["pt"])
            
            tokens = user.get("expo_push_tokens") or []
            
            if insight:
                for token_info in tokens:
                    token = token_info.get("token")
                    if not token:
                        continue
                    
                    success = await send_push_notification(
                        token=token,
                        title=title,
                        body=insight[:250],
                        data={"type": "daily_insight", "screen": "Dashboard"}
                    )
                    
                    if success:
                        sent_count += 1
                        await db.notification_logs.insert_one({
                            "user_id": str(user["_id"]),
                            "type": "daily_insight",
                            "message": insight,
                            "language": language,
                            "sent_at": datetime.now(timezone.utc),
                            "success": True
                        })
                    else:
                        failed_count += 1
            else:
                fallback_messages = {
                    "pt": "💡 Acesse o app para ver seu score financeiro e dicas personalizadas!",
                    "en": "💡 Open the app to see your financial score and personalized tips!",
                    "es": "💡 Abre la app para ver tu puntuación financiera y consejos personalizados!",
                    "zh": "💡 打开应用程序查看您的财务评分和个性化提示！"
                }
                fallback_msg = fallback_messages.get(language, fallback_messages["pt"])
                
                fallback_titles = {
                    "pt": "💜 Veloria | Atualização Diária",
                    "en": "💜 Veloria | Daily Update",
                    "es": "💜 Veloria | Actualización Diaria",
                    "zh": "💜 Veloria | 每日更新"
                }
                fallback_title = fallback_titles.get(language, fallback_titles["pt"])
                
                for token_info in tokens:
                    token = token_info.get("token")
                    if not token:
                        continue
                    
                    await send_push_notification(
                        token=token,
                        title=fallback_title,
                        body=fallback_msg,
                        data={"type": "daily_reminder", "screen": "Dashboard"}
                    )
                    sent_count += 1
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar notificação para usuário {user.get('_id')}: {e}")
            failed_count += 1
    
    logger.info(f"✅ Worker finalizado: {sent_count} enviadas, {failed_count} falhas, {skipped_count} ignoradas")
    return {"sent": sent_count, "failed": failed_count, "skipped": skipped_count}


async def cleanup_inactive_tokens_worker(db):
    """
    Worker para limpar tokens inativos (mais de 30 dias).
    Deve ser chamado periodicamente (ex: semanalmente).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVE_TOKEN_DAYS)
    result = await db.users.update_many(
        {},
        {"$pull": {"expo_push_tokens": {"last_active": {"$lt": cutoff}}}}
    )
    logger.info(f"🧹 {result.modified_count} tokens inativos removidos")
    return result.modified_count


# ========== 🆕 FUNÇÃO AUXILIAR CRUD ==========

# ✅ CORRIGIDO: Adicionado request como parâmetro
async def _get_notification_or_404(notification_id: str, user_id: str, db, request: Request) -> dict:
    """
    Busca uma notificação e valida ownership.
    
    Args:
        notification_id: ID da notificação
        user_id: ID do usuário autenticado
        db: Conexão com o banco
        request: Request do FastAPI (para i18n)
    
    Returns:
        dict: Documento da notificação
    
    Raises:
        NotFoundException: Se notificação não existir
        ValidationException: Se notificação não pertencer ao usuário
    """
    try:
        notification = await db.notifications.find_one({
            "_id": ObjectId(notification_id)
        })
    except:
        # ✅ CORRIGIDO: Passando request
        raise NotFoundException(
            message_key="ERROR_NOTIFICATION_NOT_FOUND",
            request=request
        )
    
    if not notification:
        # ✅ CORRIGIDO: Passando request
        raise NotFoundException(
            message_key="ERROR_NOTIFICATION_NOT_FOUND",
            request=request
        )
    
    if notification.get("user_id") != user_id:
        raise ValidationException(
            message_key="ERROR_NOTIFICATION_UNAUTHORIZED",
            request=request
        )
    
    return notification


# ========== ENDPOINTS EXISTENTES (MANTIDOS) ==========

@router.post("/register-token", response_model=NotificationResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def register_push_token(
    request: Request,
    token_data: RegisterTokenRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Registra o token de push notification do dispositivo."""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        user = await db.users.find_one({"_id": ObjectId(current_user.id)})
        if not user:
            raise NotFoundException(
                message_key="ERROR_USER_NOT_FOUND",
                request=request
            )
        
        tokens = user.get("expo_push_tokens") or []
        
        token_exists = any(t.get("token") == token_data.token for t in tokens)
        
        if not token_exists:
            token_entry = {
                "token": token_data.token,
                "device_name": token_data.device_name,
                "device_platform": token_data.device_platform or "android",
                "registered_at": datetime.now(timezone.utc),
                "last_active": datetime.now(timezone.utc)
            }
            tokens.append(token_entry)
            
            await db.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {
                    "$set": {
                        "expo_push_tokens": tokens,
                        "push_enabled": True,
                        "push_updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"✅ Token registrado para usuário {current_user.id} - Dispositivo: {token_data.device_name or 'desconhecido'}")
        else:
            for t in tokens:
                if t.get("token") == token_data.token:
                    t["last_active"] = datetime.now(timezone.utc)
                    t["device_name"] = token_data.device_name or t.get("device_name")
                    break
            
            await db.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {
                    "$set": {
                        "expo_push_tokens": tokens,
                        "push_updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"🔄 Token reativado para usuário {current_user.id}")
        
        return NotificationResponse(
            success=True,
            message=get_message("SUCCESS_TOKEN_REGISTERED", language)
        )
    except Exception as e:
        logger.error(f"❌ Erro ao registrar token: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


@router.post("/enable", response_model=NotificationResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def enable_notifications(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Ativa notificações push para o usuário"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"push_enabled": True, "push_updated_at": datetime.now(timezone.utc)}}
    )
    logger.info(f"✅ Notificações ativadas para usuário {current_user.id}")
    return NotificationResponse(
        success=True,
        message=get_message("SUCCESS_NOTIFICATIONS_ENABLED", language)
    )


@router.post("/disable", response_model=NotificationResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def disable_notifications(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Desativa notificações push para o usuário (mantém os tokens)"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"push_enabled": False, "push_updated_at": datetime.now(timezone.utc)}}
    )
    logger.info(f"🔕 Notificações desativadas para usuário {current_user.id}")
    return NotificationResponse(
        success=True,
        message=get_message("SUCCESS_NOTIFICATIONS_DISABLED", language)
    )


@router.post("/test", response_model=NotificationResponse)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def send_test_notification(
    request: Request,
    notification: SendTestNotificationRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Envia uma notificação de teste para o dispositivo do usuário."""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise NotFoundException(
            message_key="ERROR_USER_NOT_FOUND",
            request=request
        )
    
    tokens = user.get("expo_push_tokens") or []
    if not tokens:
        raise ValidationException(
            message_key="ERROR_NO_PUSH_TOKEN",
            request=request
        )
    
    latest_token = max(tokens, key=lambda t: t.get("last_active", datetime.min))
    token = latest_token.get("token")
    
    success = await send_push_notification(
        token=token,
        title=notification.title,
        body=notification.body,
        data={"type": "test", "screen": "Dashboard"}
    )
    
    if success:
        logger.info(f"✅ Notificação de teste enviada para usuário {current_user.id}")
        return NotificationResponse(
            success=True,
            message=get_message("SUCCESS_TEST_NOTIFICATION_SENT", language)
        )
    else:
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_TEST_NOTIFICATION_FAILED",
            request=request
        )


@router.get("/status", response_model=NotificationStatusResponse)
async def get_notification_status(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna o status das notificações do usuário."""
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    
    if not user:
        return NotificationStatusResponse(
            push_enabled=False,
            has_token=False,
            devices_count=0,
            categories=["all"],
            language="pt",
            platform="android"
        )
    
    tokens = user.get("expo_push_tokens") or []
    has_token = len(tokens) > 0
    push_enabled = user.get("push_enabled", False) and has_token
    
    preferences = user.get("notification_preferences", {})
    categories = preferences.get("categories", ["all"])
    language = preferences.get("language", "pt")
    
    last_notification = await db.notification_logs.find_one(
        {"user_id": current_user.id, "success": True},
        sort=[("sent_at", -1)]
    )
    
    return NotificationStatusResponse(
        push_enabled=push_enabled,
        has_token=has_token,
        devices_count=len(tokens),
        categories=categories,
        language=language,
        platform="android",
        last_notification_at=last_notification.get("sent_at") if last_notification else None
    )


@router.put("/preferences", response_model=NotificationResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def update_notification_preferences(
    request: Request,
    preferences: UpdatePreferencesRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza as preferências de notificação do usuário."""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise NotFoundException(
            message_key="ERROR_USER_NOT_FOUND",
            request=request
        )
    
    update_data = {"push_updated_at": datetime.now(timezone.utc)}
    
    if preferences.categories is not None:
        update_data["notification_preferences.categories"] = [c.value for c in preferences.categories]
    
    if preferences.language is not None:
        if preferences.language not in ["pt", "en", "es", "zh"]:
            raise ValidationException(
                message_key="ERROR_INVALID_LANGUAGE",
                request=request
            )
        update_data["notification_preferences.language"] = preferences.language
    
    if preferences.push_enabled is not None:
        update_data["push_enabled"] = preferences.push_enabled
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    logger.info(f"✅ Preferências atualizadas para usuário {current_user.id}")
    return NotificationResponse(
        success=True,
        message=get_message("SUCCESS_PREFERENCES_UPDATED", language)
    )


@router.post("/trigger-daily", response_model=NotificationResponse)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def trigger_daily_notifications(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str = Query(..., description="Chave secreta de admin"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Endpoint para acionar o worker de notificações diárias."""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")
    
    if os.getenv("ENVIRONMENT") == "production" and not ADMIN_SECRET:
        logger.error("❌ ADMIN_SECRET não configurado em produção!")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )
    
    if not ADMIN_SECRET:
        logger.warning("⚠️ ADMIN_SECRET não configurado. Endpoint /trigger-daily está vulnerável!")
        if secret != "development-only-secret":
            raise ValidationException(
                message_key="ERROR_UNAUTHORIZED",
                request=request
            )
    else:
        if secret != ADMIN_SECRET:
            raise ValidationException(
                message_key="ERROR_UNAUTHORIZED",
                request=request
            )
    
    logger.info(f"🔔 Trigger manual de notificações diárias solicitado por {current_user.id}")
    
    background_tasks.add_task(send_daily_notifications_worker, db)
    
    return NotificationResponse(
        success=True,
        message=get_message("SUCCESS_NOTIFICATIONS_TRIGGERED", language)
    )


@router.post("/cleanup-tokens", response_model=NotificationResponse)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def cleanup_inactive_tokens(
    request: Request,
    secret: str = Query(..., description="Chave secreta de admin"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Endpoint para limpar tokens inativos (mais de 30 dias)."""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")
    
    if os.getenv("ENVIRONMENT") == "production" and not ADMIN_SECRET:
        logger.error("❌ ADMIN_SECRET não configurado em produção!")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )
    
    if not ADMIN_SECRET:
        if secret != "development-only-secret":
            raise ValidationException(
                message_key="ERROR_UNAUTHORIZED",
                request=request
            )
    else:
        if secret != ADMIN_SECRET:
            raise ValidationException(
                message_key="ERROR_UNAUTHORIZED",
                request=request
            )
    
    logger.info(f"🧹 Limpeza de tokens inativos solicitada por {current_user.id}")
    
    removed = await cleanup_inactive_tokens_worker(db)
    
    return NotificationResponse(
        success=True,
        message=f"{removed} tokens inativos removidos"
    )


# ========== 🆕 NOVOS ENDPOINTS CRUD ==========

@router.get("/", response_model=NotificationListResponse)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_notifications(
    request: Request,
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    unread_only: bool = Query(False, description="Filtrar apenas não lidas"),
    type: Optional[str] = Query(None, description="Filtrar por tipo"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Lista notificações do usuário com paginação.
    
    🔧 FILTROS:
      - unread_only: Apenas não lidas
      - type: Filtrar por tipo (bill, goal, etc)
      - category: Filtrar por categoria (finance, goals, etc)
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        # Monta query
        query = {"user_id": str(current_user.id)}
        
        if unread_only:
            query["read"] = False
        
        if type:
            # Valida se o tipo é válido
            try:
                NotificationType(type)
                query["type"] = type
            except ValueError:
                raise ValidationException(
                    message_key="ERROR_INVALID_NOTIFICATION_TYPE",
                    request=request
                )
        
        if category:
            # Valida se a categoria é válida
            try:
                NotificationCategoryEnum(category)
                query["category"] = category
            except ValueError:
                raise ValidationException(
                    message_key="ERROR_INVALID_CATEGORY",
                    request=request
                )
        
        # Contagem total
        total = await db.notifications.count_documents(query)
        
        # Contagem não lidas
        unread_query = query.copy()
        unread_query["read"] = False
        unread_count = await db.notifications.count_documents(unread_query)
        
        # Busca com paginação
        skip = (page - 1) * limit
        cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
        notifications = await cursor.to_list(limit)
        
        # Converte para response
        items = []
        for notif in notifications:
            notif["_id"] = str(notif["_id"])
            items.append(NotificationInAppResponse(**notif))
        
        has_more = total > (page * limit)
        
        return NotificationListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=has_more,
            unread_count=unread_count
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar notificações: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_NOTIFICATIONS_LIST_FAILED",
            request=request
        )


@router.get("/unread", response_model=UnreadCountResponse)
@limiter.limit("60/minute", key_func=get_user_rate_limit_key)
async def get_unread_count(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Retorna a contagem de notificações não lidas.
    """
    try:
        count = await db.notifications.count_documents({
            "user_id": str(current_user.id),
            "read": False
        })
        
        return UnreadCountResponse(unread_count=count)
        
    except Exception as e:
        logger.error(f"❌ Erro ao contar não lidas: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_NOTIFICATIONS_UNREAD_FAILED",
            request=request
        )


@router.get("/{notification_id}", response_model=NotificationInAppResponse)
@limiter.limit("60/minute", key_func=get_user_rate_limit_key)
async def get_notification(
    request: Request,
    notification_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Busca uma notificação específica.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        # ✅ CORRIGIDO: Passando request
        notification = await _get_notification_or_404(
            notification_id,
            str(current_user.id),
            db,
            request
        )
        
        notification["_id"] = str(notification["_id"])
        return NotificationInAppResponse(**notification)
        
    except (NotFoundException, ValidationException):
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao buscar notificação: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_NOTIFICATION_FETCH_FAILED",
            request=request
        )


@router.put("/{notification_id}/read", response_model=NotificationInAppResponse)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def mark_notification_as_read(
    request: Request,
    notification_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Marca uma notificação como lida.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        # ✅ CORRIGIDO: Passando request
        notification = await _get_notification_or_404(
            notification_id,
            str(current_user.id),
            db,
            request
        )
        
        if notification.get("read", False):
            # Já está lida, retorna como está
            notification["_id"] = str(notification["_id"])
            return NotificationInAppResponse(**notification)
        
        # Atualiza
        now = datetime.now(timezone.utc)
        await db.notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {
                "$set": {
                    "read": True,
                    "read_at": now,
                    "updated_at": now
                }
            }
        )
        
        # Busca a notificação atualizada
        updated = await db.notifications.find_one({"_id": ObjectId(notification_id)})
        updated["_id"] = str(updated["_id"])
        
        logger.info(f"✅ Notificação {notification_id} marcada como lida")
        return NotificationInAppResponse(**updated)
        
    except (NotFoundException, ValidationException):
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao marcar notificação como lida: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_NOTIFICATION_MARK_READ_FAILED",
            request=request
        )


@router.put("/read-all", response_model=ReadAllResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def mark_all_notifications_as_read(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Marca todas as notificações do usuário como lidas.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        now = datetime.now(timezone.utc)
        result = await db.notifications.update_many(
            {
                "user_id": str(current_user.id),
                "read": False
            },
            {
                "$set": {
                    "read": True,
                    "read_at": now,
                    "updated_at": now
                }
            }
        )
        
        updated_count = result.modified_count
        
        logger.info(f"✅ {updated_count} notificações marcadas como lidas para usuário {current_user.id}")
        
        return ReadAllResponse(
            success=True,
            message=get_message("SUCCESS_NOTIFICATIONS_READ_ALL", language, count=updated_count),
            updated_count=updated_count
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao marcar todas como lidas: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_NOTIFICATIONS_READ_ALL_FAILED",
            request=request
        )


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def delete_notification(
    request: Request,
    notification_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Deleta uma notificação.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    try:
        # ✅ CORRIGIDO: Passando request
        await _get_notification_or_404(
            notification_id,
            str(current_user.id),
            db,
            request
        )
        
        # Deleta
        await db.notifications.delete_one({"_id": ObjectId(notification_id)})
        
        logger.info(f"🗑️ Notificação {notification_id} deletada")
        
    except (NotFoundException, ValidationException):
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao deletar notificação: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_NOTIFICATION_DELETE_FAILED",
            request=request
        )


# ========== WORKERS PARA SCHEDULER ==========

async def run_daily_notifications_scheduler(db):
    """Função para ser chamada pelo scheduler interno (APScheduler) às 09:00"""
    logger.info("⏰ Scheduler: Executando notificações diárias")
    return await send_daily_notifications_worker(db)


async def run_cleanup_tokens_scheduler(db):
    """Função para ser chamada pelo scheduler interno (semanalmente)"""
    logger.info("⏰ Scheduler: Executando limpeza de tokens inativos")
    return await cleanup_inactive_tokens_worker(db)


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting por usuário
#   - Múltiplos tokens por usuário
#   - Templates em múltiplos idiomas
#   - Categorias de notificação
#   - Cache de insights (24h)
#   - Worker de limpeza de tokens inativos (30 dias)
#   - Validação de Expo token
#   - Literal para device_platform
#   - Forçar ADMIN_SECRET em produção
#   - 🆕 CRUD completo de notificações in-app
#   - 🆕 Paginação com filtros
#   - 🆕 Contagem de não lidas
#   - 🆕 Marcar todas como lidas
#
# ❌ Não implementado (Pós-MVP):
#   - Scheduler automático (APScheduler) - já existe em scheduler.py
#   - Agendamento personalizado
#   - Analytics de abertura
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n, rate limiting, multi-token, categorias (30/06/2026)
#   - v2.1: Correções de tokens, ADMIN_SECRET (01/07/2026)
#   - v2.2: Literal, validação Expo, cleanuptokens, índices (02/07/2026)
#   - v2.3: Refatoração - constants, rate_limiter, notifications utils (02/07/2026)
#   - v2.4: Adicionado CRUD in-app (13/07/2026)
#   - v2.4.1: Correção de imports e request no i18n (14/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO