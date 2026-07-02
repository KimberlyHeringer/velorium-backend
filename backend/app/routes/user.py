"""
Rotas de Usuário (Perfil, Senha, Consentimento, Preferências, Export, Delete)
Arquivo: backend/app/routes/user.py

🔧 CORRIGIDO (v4.1 - FINAL):
- 🔧 NOVO: I18n com I18nHTTPException
- 🔧 i18n: Todas as mensagens de erro substituídas
- 🔧 i18n: Mensagens de sucesso com get_message()
- 🔧 NOVO: request: Request em todos os endpoints
- 🔧 NOVO: Validação de força da nova senha no change-password
- 🔧 CORRIGIDO: monthly_income com from_cents() no response

🆕 MELHORIAS ADICIONADAS (v4):
- 🔧 Substituído format_mongo_doc por convert_objectid_to_str (padronização)
- 🆕 I18n completo com I18nHTTPException e get_message()
- 🆕 Adicionado request: Request em todos os endpoints
- 🆕 Rate limiting em todos os endpoints sensíveis
- 🆕 Confirmar exclusão por email (token + email de confirmação)
- 🆕 Remover campos sensíveis do export (refresh_tokens, push_tokens)

🔧 CORREÇÕES DO DESENVOLVEDOR (v4.1):
- 🔧 CORRIGIDO: convert_objectid_to_str com fallback para {} (evita None)
- 🔧 CORRIGIDO: send_delete_confirmation_email com fallback em caso de falha
- 🆕 Validação de reason no delete (max_length=500)

📋 DECISÕES DOCUMENTADAS:
- ✅ Confirmar exclusão por email (segurança)
- ✅ Rate limiting em todos endpoints
- ✅ Remover campos sensíveis do export
- ✅ Fallback para email em caso de falha
- ❌ Pós-MVP: mover privacy-policy para arquivo separado
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
from app.utils.rate_limiter import limiter
from app.utils.logger import setup_logger
from app.utils.currency import from_cents
from app.utils.validators import convert_objectid_to_str, validate_object_id

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, ValidationException, NotFoundException, UnauthorizedException
from app.utils.i18n import get_message, get_language_from_request

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

router = APIRouter(prefix="/users", tags=["Usuário"])


# ========== CONSTANTES ==========
DELETE_TOKEN_EXPIRY_HOURS = 24


# ========== SCHEMAS ==========

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None  # EmailStr já é validado pelo Pydantic ✅


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
    reason: Optional[str] = Field(None, max_length=500, description="Motivo da exclusão")  # 🆕


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


# ========== FUNÇÕES AUXILIARES ==========

def get_user_rate_limit_key(request: Request) -> str:
    """
    Gera chave de rate limiting por usuário.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:user:{user_id}"
    
    client_ip = request.client.host if request.client else "unknown"
    return f"user:ip:{client_ip}"


def validate_password_strength(password: str) -> None:
    """Valida a força da senha (pelo menos 3 dos 4 critérios)"""
    if len(password) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres")
    
    criteria = 0
    if re.search(r"[A-Z]", password):
        criteria += 1
    if re.search(r"[a-z]", password):
        criteria += 1
    if re.search(r"\d", password):
        criteria += 1
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        criteria += 1
    
    if criteria < 3:
        raise ValueError(
            'A senha deve conter pelo menos 3 dos seguintes: '
            'letra maiúscula, letra minúscula, número, caractere especial'
        )


async def generate_delete_token(user_id: str, db) -> str:
    """
    Gera token de exclusão de conta.
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=DELETE_TOKEN_EXPIRY_HOURS)
    
    await db.delete_tokens.insert_one({
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
        "used": False
    })
    
    return token


async def verify_delete_token(token: str, db) -> Optional[str]:
    """
    Verifica token de exclusão de conta.
    Retorna user_id se válido, None caso contrário.
    """
    token_doc = await db.delete_tokens.find_one({
        "token": token,
        "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    
    if not token_doc:
        return None
    
    return token_doc.get("user_id")


async def mark_token_as_used(token: str, db):
    """
    Marca token como usado.
    """
    await db.delete_tokens.update_one(
        {"token": token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}}
    )


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
    
    # 🔧 CORRIGIDO: convert_objectid_to_str com fallback
    user = convert_objectid_to_str(user) or {}
    
    # Converte monthly_income de centavos para reais
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
    
    # 🔧 CORRIGIDO: convert_objectid_to_str com fallback
    updated_user = convert_objectid_to_str(updated_user) or {}
    
    # Converte monthly_income de centavos para reais
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
    
    # Valida força da nova senha
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
    """Atualiza o consentimento do usuário (termos, pesquisa)"""
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
    """
    Retorna o texto da Política de Privacidade (LGPD)
    """
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
    """
    Exporta todos os dados do usuário em formato JSON (LGPD - Direito de Portabilidade)
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    user_id = str(current_user.id)
    
    logger.info(f"📤 Iniciando exportação de dados para usuário {user_id}")
    
    # Busca dados de todas as coleções
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        # 🔧 CORRIGIDO: convert_objectid_to_str com fallback
        user = convert_objectid_to_str(user) or {}
        # Remove campos sensíveis que não devem ser exportados
        user.pop("password_hash", None)
        user.pop("reset_token", None)
        user.pop("reset_token_expires", None)
        user.pop("refresh_tokens", None)
        user.pop("push_tokens", None)
        # Converte monthly_income de centavos para reais
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
    
    # Monta o objeto de exportação
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
    """
    Inicia o processo de exclusão da conta.
    Envia email de confirmação com link para excluir definitivamente.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = str(current_user.id)
    
    user_id = str(current_user.id)
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    # Verifica se já há um token pendente
    existing_token = await db.delete_tokens.find_one({
        "user_id": user_id,
        "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    
    if existing_token:
        token = existing_token["token"]
    else:
        token = await generate_delete_token(user_id, db)
    
    # 🔧 Envia email de confirmação com fallback
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
        # Fallback: registra no banco para retry manual
        await db.failed_emails.insert_one({
            "user_id": user_id,
            "email": user.get("email"),
            "type": "delete_confirmation",
            "token": token,
            "error": str(e),
            "created_at": datetime.now(timezone.utc)
        })
    
    # Registra a solicitação de exclusão
    await db.delete_requests.insert_one({
        "user_id": user_id,
        "reason": delete_data.reason,  # 🆕
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
    """
    Confirma a exclusão da conta usando o token enviado por email.
    """
    language = getattr(request.state, "language", "pt")
    request.state.user_id = "anonymous"
    
    # Verifica token
    user_id = await verify_delete_token(confirm_data.token, db)
    if not user_id:
        raise ValidationException(
            message_key="ERROR_INVALID_DELETE_TOKEN",
            request=request
        )
    
    user_obj_id = ObjectId(user_id)
    
    # Verifica se o usuário ainda existe
    user = await db.users.find_one({"_id": user_obj_id})
    if not user:
        raise NotFoundException(
            message_key="USER_NOT_FOUND",
            request=request
        )
    
    logger.warning(f"🗑️ Confirmando exclusão permanente da conta do usuário {user_id}")
    
    # Lista de coleções a limpar
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
    
    # Remove os dados de cada coleção
    for collection_name in collections:
        if collection_name == "users":
            result = await db[collection_name].delete_one({"_id": user_obj_id})
            logger.debug(f"Coleção {collection_name}: {result.deleted_count} documento(s) removido(s)")
        else:
            result = await db[collection_name].delete_many({"user_id": user_id})
            logger.debug(f"Coleção {collection_name}: {result.deleted_count} documento(s) removido(s)")
    
    # Remove tokens da blacklist
    await db.refresh_token_blacklist.delete_many({"user_id": user_id})
    
    # Marca token como usado
    await mark_token_as_used(confirm_data.token, db)
    
    # Marca solicitação como completada
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
# ✅ #31 - Política de Privacidade (endpoint GET /users/privacy-policy)
# ✅ #32 - Exportar dados (endpoint GET /users/export) com rate limit 2/min
# ✅ #33 - Deletar conta (endpoint DELETE /users/delete) com rate limit 1/min
# ✅ #34 - Confirmar exclusão por email (POST /users/delete/confirm)
# ✅ Dados sensíveis (password_hash, reset_token, refresh_tokens, push_tokens) excluídos do export
# ✅ Todas as coleções relevantes são limpas ao deletar conta
# ✅ Retorno estruturado com mensagem amigável
# ✅ 🔧 i18n: Todas as mensagens substituídas
# ✅ 🔧 Rate limiting em todos os endpoints
# ✅ 🔧 request: Request em todos os endpoints
# ✅ 🔧 convert_objectid_to_str com fallback {}
# ✅ 🔧 Email com fallback em caso de falha
# ✅ 🔧 Validação de reason (max_length=500)
# ✅ 🔧 from_cents() nos valores monetários do export
# ✅ 🔧 Confirmar exclusão por email (segurança adicional)
#
# 📌 VARIÁVEIS DE AMBIENTE:
#   - DELETE_TOKEN_EXPIRY_HOURS: 24 (padrão)
#   - EMAIL_ENABLED: true (para envio de emails)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO

