"""
Rotas de Autenticação
Arquivo: backend/app/routes/auth.py

🔧 CORRIGIDO (VERSÃO FINAL):
- monthly_income agora tratado como int (centavos)
- 🔧 NOVO: I18n com I18nHTTPException
- 🔧 i18n: Todas as mensagens de erro substituídas
- 🔧 NOVO: Logout com refresh token no body
- 🔧 NOVO: Rate limiting no login (5/minuto)
- 🔧 NOVO: Validação de refresh_token no logout
- 🔧 NOVO: Verificação de blacklist no /me
- 🔧 NOVO: Validação de terms_accepted no registro
- 🔧 NOVO: Logs de auditoria no login
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from datetime import datetime, timedelta, timezone
from typing import Annotated
import secrets
from bson import ObjectId

from app.database import get_database
from app.models.user import UserCreate, UserLogin, UserResponse
from app.utils.auth import (
    get_password_hash,
    verify_password,
    generate_token_pair,
    TokenPair,
    get_current_user,
    is_token_blacklisted,
    add_token_to_blacklist,
    decode_token,
    oauth2_scheme
)
from app.utils.rate_limiter import limiter
from app.utils.logger import setup_logger
from app.utils.validators import validate_password_strength

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, ValidationException, UnauthorizedException
from app.utils.i18n import get_message, get_language_from_request

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# ========== SCHEMAS ==========

class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class LogoutRequest(BaseModel):
    refresh_token: str


# ========== ENDPOINTS ==========

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user_data: UserCreate,
    db=Depends(get_database)
):
    # 🔧 NOVO: Valida se os termos foram aceitos
    if not user_data.terms_accepted:
        raise ValidationException(
            message_key="AUTH_TERMS_REQUIRED",
            request=request
        )

    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise I18nHTTPException(
            status_code=400,
            message_key="AUTH_EMAIL_ALREADY_EXISTS",
            request=request
        )

    try:
        validate_password_strength(user_data.password)
    except ValueError as e:
        raise ValidationException(
            message_key="AUTH_WEAK_PASSWORD",
            request=request
        )

    hashed = get_password_hash(user_data.password)

    user_dict = user_data.model_dump(exclude={"password"})
    user_dict["password_hash"] = hashed
    user_dict["email"] = user_data.email.lower()
    user_dict["created_at"] = datetime.now(timezone.utc)
    user_dict["updated_at"] = datetime.now(timezone.utc)

    result = await db.users.insert_one(user_dict)
    logger.info(f"Novo usuário registrado: {user_data.email.lower()}")
    
    language = getattr(request.state, "language", "pt")
    return {"message": get_message("SUCCESS_CREATED", language), "id": str(result.inserted_id)}


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # 🔧 NOVO: Rate limiting específico para login
async def login(
    request: Request,
    user_data: UserLogin,
    db=Depends(get_database)
):
    db_user = await db.users.find_one({"email": user_data.email.lower()})
    if not db_user or not verify_password(user_data.password, db_user["password_hash"]):
        logger.warning(f"Tentativa de login falhou para email: {user_data.email.lower()}")
        raise UnauthorizedException(
            message_key="AUTH_INVALID_CREDENTIALS",
            request=request
        )

    token_pair = generate_token_pair(str(db_user["_id"]))

    user_response = UserResponse(
        id=str(db_user["_id"]),
        name=db_user["name"],
        email=db_user["email"],
        monthly_income=db_user.get("monthly_income", 0),
        location=db_user.get("location"),
        profession_type=db_user.get("profession_type", "outros"),
        occupation=db_user.get("occupation"),
        financial_goal=db_user.get("financial_goal"),
        created_at=db_user["created_at"],
        research_consent=db_user.get("research_consent", False),
        terms_accepted=db_user.get("terms_accepted", False),
        terms_accepted_at=db_user.get("terms_accepted_at"),
        language=db_user.get("language", "pt"),
        currency=db_user.get("currency", "BRL")
    )

    # 🔧 NOVO: Log de auditoria
    await db.audit_logs.insert_one({
        "action": "login",
        "user_id": str(db_user["_id"]),
        "email": db_user["email"],
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "timestamp": datetime.now(timezone.utc)
    })

    logger.info(f"Usuário logado: {user_data.email.lower()}")
    return LoginResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
        user=user_response
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    request: Request,
    req: RefreshTokenRequest,
    db=Depends(get_database)
):
    from app.utils.auth import refresh_access_token
    
    if await is_token_blacklisted(req.refresh_token, db):
        raise UnauthorizedException(
            message_key="AUTH_TOKEN_REVOKED",
            request=request
        )
    
    try:
        return await refresh_access_token(req.refresh_token, db)
    except HTTPException:
        raise
    except Exception:
        raise UnauthorizedException(
            message_key="AUTH_INVALID_REFRESH_TOKEN",
            request=request
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db=Depends(get_database)
):
    # 🔧 NOVO: Verifica se o token está na blacklist
    if await is_token_blacklisted(token, db):
        raise UnauthorizedException(
            message_key="AUTH_TOKEN_REVOKED",
            request=request
        )
    
    current_user = await get_current_user(token, db)
    
    # Verifica se o usuário ainda existe
    db_user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not db_user:
        raise UnauthorizedException(
            message_key="AUTH_USER_NOT_FOUND",
            request=request
        )
    return current_user


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    logout_data: LogoutRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    # 🔧 NOVO: Valida se o refresh token pertence ao usuário
    try:
        payload = decode_token(logout_data.refresh_token)
        if payload.get("sub") != current_user.id:
            raise UnauthorizedException(
                message_key="AUTH_TOKEN_INVALID",
                request=request
            )
    except Exception:
        raise UnauthorizedException(
            message_key="AUTH_TOKEN_INVALID",
            request=request
        )
    
    await add_token_to_blacklist(logout_data.refresh_token, current_user.id, db)
    logger.info(f"Usuário fez logout: {current_user.email}")
    
    language = getattr(request.state, "language", "pt")
    return {"message": get_message("SUCCESS_LOGOUT", language)}


@router.post("/forgot-password", response_model=dict)
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    db=Depends(get_database)
):
    user = await db.users.find_one({"email": forgot_data.email})
    
    language = getattr(request.state, "language", "pt")
    
    if not user:
        return {"message": get_message("INFO_PASSWORD_RESET_EMAIL_SENT", language)}
    
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "reset_token": token,
            "reset_token_expires": expires
        }}
    )
    
    try:
        from app.services.email_service import email_service
        await email_service.send_password_reset_email(
            to_email=user["email"],
            reset_token=token,
            language=language
        )
        logger.info(f"Email de redefinição enviado para: {user['email']}")
    except ImportError:
        reset_link = f"https://velorium-frontend.com/reset-password?token={token}"
        logger.info(f"🔐 [MOCK] Link para redefinir senha: {reset_link}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar email para {user['email']}: {e}")
    
    return {"message": get_message("INFO_PASSWORD_RESET_EMAIL_SENT", language)}


@router.post("/reset-password", response_model=dict)
async def reset_password(
    request: Request,
    reset_data: ResetPasswordRequest,
    db=Depends(get_database)
):
    try:
        validate_password_strength(reset_data.new_password)
    except ValueError as e:
        raise ValidationException(
            message_key="AUTH_WEAK_PASSWORD",
            request=request
        )
    
    user = await db.users.find_one({
        "reset_token": reset_data.token,
        "reset_token_expires": {"$gt": datetime.now(timezone.utc)}
    })
    if not user:
        raise I18nHTTPException(
            status_code=400,
            message_key="AUTH_INVALID_RESET_TOKEN",
            request=request
        )
    
    new_hash = get_password_hash(reset_data.new_password)
    
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": new_hash,
            "reset_token": None,
            "reset_token_expires": None,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    logger.info(f"Senha redefinida para usuário: {user['email']}")
    
    language = getattr(request.state, "language", "pt")
    return {"message": get_message("SUCCESS_PASSWORD_RESET", language)}


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. 🔧 NOVO: Rate limiting no login (5/minuto)
2. 🔧 NOVO: Validação de refresh_token no logout
3. 🔧 NOVO: Verificação de blacklist no /me
4. 🔧 NOVO: Validação de terms_accepted no registro
5. 🔧 NOVO: Logs de auditoria no login
6. 🔧 i18n: Todas as mensagens substituídas
7. 🔧 CORRIGIDO: UserResponse com None em vez de ""
8. 🔧 CORRIGIDO: refresh_access_token com db

📌 CHAVES I18N REFERENCIADAS:
   - AUTH_TERMS_REQUIRED → "Você deve aceitar os termos de uso"
   - AUTH_TOKEN_INVALID → "Token inválido"
   - AUTH_USER_NOT_FOUND → "Usuário não encontrado"
   - AUTH_EMAIL_ALREADY_EXISTS → "Email já cadastrado"
   - AUTH_INVALID_CREDENTIALS → "Email ou senha inválidos"
   - AUTH_TOKEN_REVOKED → "Token revogado. Faça login novamente."
   - AUTH_INVALID_REFRESH_TOKEN → "Refresh token inválido ou expirado"
   - AUTH_INVALID_RESET_TOKEN → "Token inválido ou expirado"
   - AUTH_WEAK_PASSWORD → "Senha muito fraca"
   - SUCCESS_LOGOUT → "Logout realizado com sucesso. Token revogado."
   - SUCCESS_PASSWORD_RESET → "Senha alterada com sucesso."
   - SUCCESS_CREATED → "Criado com sucesso"
   - INFO_PASSWORD_RESET_EMAIL_SENT → "Se o email estiver cadastrado, você receberá um link de redefinição."

✅ STATUS: PRONTO PARA PRODUÇÃO
================================================================================
"""