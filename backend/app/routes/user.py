"""
Rotas de Usuário (Perfil, Senha, Consentimento, Preferências, Export, Delete)
Arquivo: backend/app/routes/user.py

Funcionalidades:
- GET /users/me: Dados do usuário logado
- PUT /users/profile: Atualizar perfil
- PUT /users/change-password: Alterar senha
- GET /users/preferences: Buscar preferências
- PUT /users/preferences: Atualizar preferências
- PUT /users/consent: Atualizar consentimento
- GET /users/consent-status: Status do consentimento
- GET /users/privacy-policy: Política de Privacidade
- GET /users/export: Exportar dados (LGPD)
- DELETE /users/delete: Solicitar exclusão (envia email)
- POST /users/delete/confirm: Confirmar exclusão (token)

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting em todos endpoints
- Confirmar exclusão por email (token + email)
- Remover campos sensíveis do export
- Validação de força de senha
- Fallback para email em caso de falha

Versão: v4.1 (refatorado)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import json
import re
import os
import secrets

from app.database import get_database
from app.models.user import UserResponse, UserUpdate
from app.utils.auth import get_current_user, get_password_hash, verify_password
from app.utils.logger import setup_logger
from app.utils.currency import from_cents
from app.utils.validators import convert_objectid_to_str, validate_object_id

# ========== NOVOS IMPORTS ==========
from app.core.constants import DELETE_TOKEN_EXPIRY_HOURS
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.validators_extras import validate_password_strength
from app.utils.user_tokens import (
    generate_delete_token,
    verify_delete_token,
    mark_token_as_used
)

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, ValidationException, NotFoundException, UnauthorizedException
from app.utils.i18n import get_message, get_language_from_request

logger = setup_logger(__name__)

router = APIRouter(prefix="/users", tags=["Usuário"])


# ========== SCHEMAS ==========

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class PreferencesUpdate(BaseModel):
    language: Optional[str] = None   # pt, en, es, zh
    currency: Optional[str] = None   # BRL, USD, EUR, CNY


class ConsentUpdate(BaseModel):
    terms_accepted: bool
    research_consent: bool


class ConsentStatusResponse(BaseModel):
    terms_accepted: bool
    research_consent: bool
    terms_accepted_at: Optional[datetime] = None


class ExportDataResponse(BaseModel):
    message: str
    data: Dict[str, Any]


class DeleteAccountRequest(BaseModel):
    confirm_delete: bool = True
    reason: Optional[str] = Field(None, max_length=500, description="Motivo da exclusão")


class DeleteAccountResponse(BaseModel):
    message: str
    user_id: str
    confirmation_sent: bool = True
    expires_in_hours: int = DELETE_TOKEN_EXPIRY_HOURS


class ConfirmDeleteRequest(BaseModel):
    token: str


class ConfirmDeleteResponse(BaseModel):
    message: str
    user_id: str


# ========== ENDPOINTS DE PERFIL ==========

@router.get("/me", response_model=UserResponse)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_me(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna os dados do usuário logado"""
    request.state.user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    user = convert_objectid_to_str(user) or {}
    
    if "monthly_income" in user and user["monthly_income"] is not None:
        user["monthly_income"] = from_cents(user["monthly_income"])
    
    return UserResponse(**user)


@router.put("/profile", response_model=UserResponse)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def update_profile(
    request: Request,
    profile_data: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza os dados do perfil do usuário"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    update_data = {}
    if profile_data.name is not None:
        update_data["name"] = profile_data.name
    if profile_data.email is not None:
        update_data["email"] = profile_data.email.lower()
    
    if not update_data:
        raise ValidationException(
            message_key="ERROR_NO_DATA_TO_UPDATE",
            request=request
        )
    
    if "email" in update_data:
        existing = await db.users.find_one({"email": update_data["email"]})
        if existing and str(existing["_id"]) != str(current_user.id):
            logger.warning(f"⚠️ Tentativa de usar email já cadastrado: {update_data['email']}")
            raise I18nHTTPException(
                status_code=400,
                message_key="AUTH_EMAIL_ALREADY_EXISTS",
                request=request
            )
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    updated_user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    updated_user = convert_objectid_to_str(updated_user) or {}
    
    if "monthly_income" in updated_user and updated_user["monthly_income"] is not None:
        updated_user["monthly_income"] = from_cents(updated_user["monthly_income"])
    
    logger.info(f"✅ Perfil atualizado para usuário {current_user.id}")
    
    return UserResponse(**updated_user)


@router.put("/change-password", response_model=dict)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Altera a senha do usuário"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        logger.warning(f"⚠️ Usuário não encontrado ao tentar alterar senha: {current_user.id}")
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    if not verify_password(password_data.current_password, user["password_hash"]):
        logger.warning(f"⚠️ Tentativa de alterar senha com senha atual incorreta para usuário {current_user.id}")
        raise UnauthorizedException(
            message_key="AUTH_INVALID_CREDENTIALS",
            request=request
        )
    
    try:
        validate_password_strength(password_data.new_password)
    except ValueError as e:
        raise ValidationException(
            message_key="AUTH_WEAK_PASSWORD",
            request=request
        )
    
    new_hash = get_password_hash(password_data.new_password)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    
    logger.info(f"✅ Senha alterada com sucesso para usuário {current_user.id}")
    
    return {"message": get_message("SUCCESS_PASSWORD_CHANGED", language)}


# ========== ENDPOINTS DE PREFERÊNCIAS ==========

@router.get("/preferences", response_model=dict)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_preferences(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna as preferências do usuário (idioma, moeda)"""
    request.state.user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        logger.warning(f"⚠️ Usuário não encontrado ao buscar preferências: {current_user.id}")
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    logger.debug(f"📊 Preferências recuperadas para usuário {current_user.id}")
    return {
        "language": user.get("language", "pt"),
        "currency": user.get("currency", "BRL")
    }


@router.put("/preferences", response_model=dict)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def update_preferences(
    request: Request,
    prefs: PreferencesUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza as preferências do usuário (idioma, moeda)"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    update_data = {}
    if prefs.language is not None:
        if prefs.language not in ["pt", "en", "es", "zh"]:
            logger.warning(f"⚠️ Idioma inválido solicitado: {prefs.language}")
            raise ValidationException(
                message_key="ERROR_INVALID_LANGUAGE",
                request=request
            )
        update_data["language"] = prefs.language
    if prefs.currency is not None:
        if prefs.currency not in ["BRL", "USD", "EUR", "CNY"]:
            logger.warning(f"⚠️ Moeda inválida solicitada: {prefs.currency}")
            raise ValidationException(
                message_key="ERROR_INVALID_CURRENCY",
                request=request
            )
        update_data["currency"] = prefs.currency
    
    if not update_data:
        raise ValidationException(
            message_key="ERROR_NO_DATA_TO_UPDATE",
            request=request
        )
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    logger.info(f"✅ Preferências atualizadas para usuário {current_user.id}: {update_data}")
    
    return {"message": get_message("SUCCESS_PREFERENCES_UPDATED", language)}


# ========== ENDPOINTS DE CONSENTIMENTO ==========

@router.put("/consent", response_model=dict)
@limiter.limit("10/minute", key_func=get_user_rate_limit_key)
async def update_consent(
    request: Request,
    consent_data: ConsentUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza o consentimento do usuário"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    update_fields = {
        "research_consent": consent_data.research_consent,
        "updated_at": datetime.now(timezone.utc),
        "consent_updated_at": datetime.now(timezone.utc)
    }
    if consent_data.terms_accepted:
        update_fields["terms_accepted"] = True
        update_fields["terms_accepted_at"] = datetime.now(timezone.utc)
    else:
        logger.warning(f"⚠️ Tentativa de desmarcar termos aceitos para usuário {current_user.id}")
        raise ValidationException(
            message_key="ERROR_CANNOT_UNACCEPT_TERMS",
            request=request
        )
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_fields}
    )
    
    logger.info(f"✅ Consentimento atualizado para usuário {current_user.id}: research_consent={consent_data.research_consent}")
    
    return {"message": get_message("SUCCESS_CONSENT_UPDATED", language)}


@router.get("/consent-status", response_model=ConsentStatusResponse)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_consent_status(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna o status de consentimento do usuário"""
    request.state.user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        logger.warning(f"⚠️ Usuário não encontrado ao buscar consentimento: {current_user.id}")
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    logger.debug(f"📊 Status de consentimento recuperado para usuário {current_user.id}")
    return ConsentStatusResponse(
        terms_accepted=user.get("terms_accepted", False),
        research_consent=user.get("research_consent", False),
        terms_accepted_at=user.get("terms_accepted_at")
    )


# ========== POLÍTICA DE PRIVACIDADE ==========

@router.get("/privacy-policy", response_model=dict)
@limiter.limit("30/minute", key_func=get_user_rate_limit_key)
async def get_privacy_policy(
    request: Request
):
    """Retorna o texto da Política de Privacidade (LGPD)"""
    request.state.user_id = "anonymous"
    
    logger.debug("📋 Política de privacidade solicitada")
    return {
        "title": "Política de Privacidade - Velorium",
        "last_updated": "2026-05-14",
        "content": """
# POLÍTICA DE PRIVACIDADE DO VELORIUM

## 1. INFORMAÇÕES COLETADAS
O Velorium coleta os seguintes dados:
- Dados cadastrais (nome, e-mail)
- Dados financeiros (transações, contas, cartões, metas)
- Score financeiro e histórico
- Preferências de idioma e moeda
- Consentimentos fornecidos

## 2. FINALIDADE DO TRATAMENTO
Os dados são utilizados para:
- Gestão financeira pessoal
- Cálculo do score financeiro
- Recomendações personalizadas (quando autorizado)
- Melhoria contínua do serviço

## 3. COMPARTILHAMENTO
Não compartilhamos seus dados pessoais com terceiros, exceto:
- Quando exigido por lei
- Com seu consentimento explícito

## 4. SEUS DIREITOS (LGPD)
Você tem direito a:
- Acessar seus dados
- Corrigir dados incorretos
- Exportar seus dados (via /users/export)
- Solicitar exclusão da conta (via DELETE /users/delete)
- Revogar consentimentos

## 5. RETENÇÃO DE DADOS
Seus dados são mantidos enquanto sua conta estiver ativa. Após exclusão, os dados são removidos em até 30 dias.

## 6. CONTATO
Para questões sobre privacidade, entre em contato: privacidade@velorium.com

## 7. CONSENTIMENTO
Ao usar o Velorium, você concorda com esta Política de Privacidade.
        """
    }


# ========== EXPORTAR DADOS DO USUÁRIO ==========

@router.get("/export", response_model=ExportDataResponse)
@limiter.limit("2/minute", key_func=get_user_rate_limit_key)
async def export_user_data(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Exporta todos os dados do usuário em formato JSON (LGPD)"""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    user_id = str(current_user.id)
    
    logger.info(f"📤 Iniciando exportação de dados para usuário {user_id}")
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user = convert_objectid_to_str(user) or {}
        user.pop("password_hash", None)
        user.pop("reset_token", None)
        user.pop("reset_token_expires", None)
        user.pop("refresh_tokens", None)
        user.pop("push_tokens", None)
        if "monthly_income" in user and user["monthly_income"] is not None:
            user["monthly_income"] = from_cents(user["monthly_income"])
    
    # Transações
    transactions = await db.transactions.find({"user_id": user_id}).to_list(10000)
    for t in transactions:
        t = convert_objectid_to_str(t) or {}
        if "amount" in t:
            t["amount"] = from_cents(t["amount"])
    
    # Contas a pagar
    bills = await db.bills.find({"user_id": user_id}).to_list(10000)
    for b in bills:
        b = convert_objectid_to_str(b) or {}
        if "amount" in b:
            b["amount"] = from_cents(b["amount"])
    
    # Cartões de crédito
    credit_cards = await db.credit_cards.find({"user_id": user_id}).to_list(10000)
    for c in credit_cards:
        c = convert_objectid_to_str(c) or {}
        if "total_limit" in c:
            c["total_limit"] = from_cents(c["total_limit"])
        if "used_limit" in c:
            c["used_limit"] = from_cents(c["used_limit"])
        if "committed_amount" in c:
            c["committed_amount"] = from_cents(c["committed_amount"])
    
    # Compras parceladas
    purchases = await db.credit_card_purchases.find({"user_id": user_id}).to_list(10000)
    for p in purchases:
        p = convert_objectid_to_str(p) or {}
        if "total_amount" in p:
            p["total_amount"] = from_cents(p["total_amount"])
    
    # Metas
    goals = await db.goals.find({"user_id": user_id}).to_list(10000)
    for g in goals:
        g = convert_objectid_to_str(g) or {}
        if "target" in g:
            g["target"] = from_cents(g["target"])
        if "current" in g:
            g["current"] = from_cents(g["current"])
    
    # Score financeiro
    score_history = await db.score_history.find({"user_id": user_id}).to_list(10000)
    for s in score_history:
        s = convert_objectid_to_str(s) or {}
    
    # Conquistas
    achievements = await db.achievements.find({"user_id": user_id}).to_list(10000)
    for a in achievements:
        a = convert_objectid_to_str(a) or {}
    
    # Perfil financeiro
    profile = await db.user_profiles.find_one({"user_id": user_id})
    if profile:
        profile = convert_objectid_to_str(profile) or {}
        if "dream_value" in profile and profile["dream_value"] is not None:
            profile["dream_value"] = from_cents(profile["dream_value"])
        if "next_year_goal_value" in profile and profile["next_year_goal_value"] is not None:
            profile["next_year_goal_value"] = from_cents(profile["next_year_goal_value"])
    
    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "user_profile": user,
        "transactions": transactions,
        "bills": bills,
        "credit_cards": credit_cards,
        "credit_card_purchases": purchases,
        "goals": goals,
        "score_history": score_history,
        "achievements": achievements,
        "financial_profile": profile
    }
    
    logger.info(f"✅ Exportação concluída para usuário {user_id}: {len(transactions)} transações, {len(goals)} metas")
    
    return ExportDataResponse(
        message=get_message("SUCCESS_DATA_EXPORTED", language),
        data=export_data
    )


# ========== DELETAR CONTA - COM CONFIRMAÇÃO POR EMAIL ==========

@router.delete("/delete", response_model=DeleteAccountResponse)
@limiter.limit("1/minute", key_func=get_user_rate_limit_key)
async def delete_account(
    request: Request,
    background_tasks: BackgroundTasks,
    delete_data: DeleteAccountRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Inicia o processo de exclusão da conta."""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    existing_token = await db.delete_tokens.find_one({
        "user_id": user_id,
        "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    
    if existing_token:
        token = existing_token["token"]
    else:
        token = await generate_delete_token(user_id, db)
    
    try:
        from app.services.email_service import send_delete_confirmation_email
        background_tasks.add_task(
            send_delete_confirmation_email,
            user.get("email"),
            user.get("name", "Usuário"),
            token,
            language
        )
        logger.info(f"📧 Email de exclusão enviado para {user.get('email')}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar email de exclusão: {e}")
        await db.failed_emails.insert_one({
            "user_id": user_id,
            "email": user.get("email"),
            "type": "delete_confirmation",
            "token": token,
            "error": str(e),
            "created_at": datetime.now(timezone.utc)
        })
    
    await db.delete_requests.insert_one({
        "user_id": user_id,
        "reason": delete_data.reason,
        "requested_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=DELETE_TOKEN_EXPIRY_HOURS),
        "completed": False
    })
    
    logger.warning(f"⚠️ Solicitação de exclusão de conta para usuário {user_id}")
    
    return DeleteAccountResponse(
        message=get_message("SUCCESS_DELETE_REQUESTED", language),
        user_id=user_id,
        confirmation_sent=True,
        expires_in_hours=DELETE_TOKEN_EXPIRY_HOURS
    )


@router.post("/delete/confirm", response_model=ConfirmDeleteResponse)
@limiter.limit("5/minute", key_func=get_user_rate_limit_key)
async def confirm_delete_account(
    request: Request,
    confirm_data: ConfirmDeleteRequest,
    db=Depends(get_database)
):
    """Confirma a exclusão da conta usando o token enviado por email."""
    language = getattr(request.state, "language", "pt")
    request.state.user_id = "anonymous"
    
    user_id = await verify_delete_token(confirm_data.token, db)
    if not user_id:
        raise ValidationException(
            message_key="ERROR_INVALID_DELETE_TOKEN",
            request=request
        )
    
    user_obj_id = ObjectId(user_id)
    
    user = await db.users.find_one({"_id": user_obj_id})
    if not user:
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    logger.warning(f"🗑️ Confirmando exclusão permanente da conta do usuário {user_id}")
    
    collections = [
        "users",
        "transactions",
        "bills",
        "credit_cards",
        "credit_card_purchases",
        "goals",
        "score_history",
        "achievements",
        "user_profiles",
        "refresh_token_blacklist"
    ]
    
    for collection_name in collections:
        if collection_name == "users":
            result = await db[collection_name].delete_one({"_id": user_obj_id})
            logger.debug(f"Coleção {collection_name}: {result.deleted_count} documento(s) removido(s)")
        else:
            result = await db[collection_name].delete_many({"user_id": user_id})
            logger.debug(f"Coleção {collection_name}: {result.deleted_count} documento(s) removido(s)")
    
    await db.refresh_token_blacklist.delete_many({"user_id": user_id})
    await mark_token_as_used(confirm_data.token, db)
    
    await db.delete_requests.update_one(
        {"user_id": user_id, "completed": False},
        {"$set": {"completed": True, "completed_at": datetime.now(timezone.utc)}}
    )
    
    logger.info(f"✅ Conta permanentemente removida: {user_id}")
    
    return ConfirmDeleteResponse(
        message=get_message("SUCCESS_ACCOUNT_DELETED", language),
        user_id=user_id
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting em todos endpoints
#   - Confirmar exclusão por email (token + email)
#   - Remover campos sensíveis do export
#   - Validação de força de senha
#   - Fallback para email em caso de falha
#   - Funções de token centralizadas em utils/user_tokens.py
#
# ❌ Não implementado (Pós-MVP):
#   - Mover privacy-policy para arquivo separado
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Rate limiting, confirmar exclusão (30/06/2026)
#   - v4: Correções de convert_objectid_to_str, email fallback (01/07/2026)
#   - v4.1: Refatoração - constants, rate_limiter, validators_extras, user_tokens (02/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO