"""
Rotas de Autenticação
Arquivo: backend/app/routes/auth.py

Funcionalidades:
- POST /auth/register: Registrar novo usuário (com validação de termos)
- POST /auth/login: Login com rate limiting (5/min)
- POST /auth/refresh: Refresh token
- GET /auth/me: Perfil do usuário autenticado
- POST /auth/logout: Logout (com revogação de token)
- POST /auth/forgot-password: Solicitar redefinição de senha
- POST /auth/reset-password: Redefinir senha com token

Principais features:
- I18n completo com suporte a 4 idiomas
- Rate limiting no login (5/minuto)
- Refresh token com blacklist
- Validação de força de senha
- Logs de auditoria no login
- Validação de termos aceitos
- 🔧 CORRIGIDO: login usa model_validate em vez de criação manual
- 🔧 CORRIGIDO: Cria perfil vazio no registro do usuário

Versão: v5 (criação de perfil vazio no registro)
📅 ATUALIZADO EM: 20/07/2026
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from datetime import datetime, timedelta, timezone
from typing import Annotated
import secrets
from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field

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
    oauth2_scheme,
    refresh_access_token
)
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.logger import setup_logger

# ========== NOVOS IMPORTS ==========
from app.utils.validators_extras import validate_password_strength
from app.utils.profile_utils import create_empty_profile

# ========== I18N ==========
from app.utils.exceptions import I18nHTTPException, ValidationException, UnauthorizedException
from app.utils.i18n import get_message, get_language_from_request

# ========== CONFIGURAÇÃO DE LOG ==========
logger = setup_logger(__name__)

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
    """
    Registra um novo usuário no sistema.
    
    🔧 VALIDAÇÕES:
        - Termos de uso aceitos (terms_accepted = True)
        - Email único (não pode existir outro usuário com mesmo email)
        - Senha forte (3/4 critérios)
    
    🔧 CORRIGIDO:
        - Cria perfil vazio automaticamente após o registro
        - Usa create_empty_profile() do profile_utils
    
    Returns:
        dict: {message, id} com ID do usuário criado
    """
    language = getattr(request.state, "language", "pt")
    
    # Verifica se os termos foram aceitos
    if not user_data.terms_accepted:
        raise ValidationException(
            message_key="AUTH_TERMS_REQUIRED",
            request=request
        )

    # Verifica se o email já está cadastrado
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        logger.warning(f"⚠️ Tentativa de registro com email já existente: {user_data.email.lower()}")
        raise I18nHTTPException(
            status_code=400,
            message_key="AUTH_EMAIL_ALREADY_EXISTS",
            request=request
        )

    # Valida força da senha
    try:
        validate_password_strength(user_data.password)
    except ValueError as e:
        logger.warning(f"⚠️ Senha fraca no registro: {str(e)}")
        raise ValidationException(
            message_key="AUTH_WEAK_PASSWORD",
            request=request
        )

    # Gera hash da senha
    hashed = get_password_hash(user_data.password)

    # Prepara dados do usuário
    user_dict = user_data.model_dump(exclude={"password"})
    user_dict["password_hash"] = hashed
    user_dict["email"] = user_data.email.lower()
    user_dict["created_at"] = datetime.now(timezone.utc)
    user_dict["updated_at"] = datetime.now(timezone.utc)

    # Insere usuário no banco
    result = await db.users.insert_one(user_dict)
    user_id = str(result.inserted_id)
    
    # 🔧 CORRIGIDO: Cria perfil vazio para o usuário
    try:
        empty_profile = create_empty_profile(user_id)
        await db.user_profiles.insert_one(empty_profile)
        logger.info(f"📝 Perfil vazio criado para usuário: {user_data.email.lower()}")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao criar perfil vazio para {user_data.email.lower()}: {e}")
        # Não falha o registro se o perfil não for criado
    
    logger.info(f"✅ Novo usuário registrado: {user_data.email.lower()}")
    
    return {"message": get_message("SUCCESS_CREATED", language), "id": user_id}


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    user_data: UserLogin,
    db=Depends(get_database)
):
    """
    Login do usuário com rate limiting (5/min).
    
    🔧 CORRIGIDO: Usa UserResponse.model_validate() em vez de criação manual.
    Isso garante que campos opcionais sejam tratados corretamente.
    
    🔧 AUDITORIA:
        - Registra IP e User-Agent no login
        - Logs de tentativas bem-sucedidas e falhas
    
    Returns:
        LoginResponse: access_token, refresh_token, user data
    """
    language = getattr(request.state, "language", "pt")
    
    # Busca usuário no banco
    db_user = await db.users.find_one({"email": user_data.email.lower()})
    
    # Verifica credenciais
    if not db_user or not verify_password(user_data.password, db_user["password_hash"]):
        logger.warning(f"⚠️ Tentativa de login falhou para email: {user_data.email.lower()}")
        raise UnauthorizedException(
            message_key="AUTH_INVALID_CREDENTIALS",
            request=request
        )

    # Gera par de tokens
    token_pair = generate_token_pair(str(db_user["_id"]))

    # 🔧 CORRIGIDO: Usar model_validate em vez de criar manualmente
    # Isso garante que:
    # 1. _id seja convertido para id automaticamente
    # 2. Campos opcionais sejam tratados corretamente
    # 3. Validações do modelo sejam aplicadas
    user_response = UserResponse.model_validate(db_user)

    # 📝 Log de auditoria
    await db.audit_logs.insert_one({
        "action": "login",
        "user_id": str(db_user["_id"]),
        "email": db_user["email"],
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "timestamp": datetime.now(timezone.utc)
    })

    logger.info(f"✅ Usuário logado: {user_data.email.lower()}")
    
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
    """
    Renova o access token usando refresh token.
    
    🔧 VALIDAÇÕES:
        - Refresh token não pode estar na blacklist
        - Refresh token deve ser válido e não expirado
    
    Returns:
        TokenPair: Novo par de tokens (access + refresh)
    """
    language = getattr(request.state, "language", "pt")
    
    # Verifica se o token está na blacklist
    if await is_token_blacklisted(req.refresh_token, db):
        logger.warning("⚠️ Tentativa de usar refresh token revogado")
        raise UnauthorizedException(
            message_key="AUTH_TOKEN_REVOKED",
            request=request
        )
    
    try:
        return await refresh_access_token(req.refresh_token, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao renovar token: {e}")
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
    """
    Retorna o perfil do usuário autenticado.
    
    🔧 VALIDAÇÕES:
        - Token não pode estar na blacklist
        - Usuário deve existir no banco
    
    Returns:
        UserResponse: Dados do usuário (sem password_hash)
    """
    language = getattr(request.state, "language", "pt")
    
    # Verifica se o token está na blacklist
    if await is_token_blacklisted(token, db):
        logger.warning("⚠️ Tentativa de usar token revogado no /me")
        raise UnauthorizedException(
            message_key="AUTH_TOKEN_REVOKED",
            request=request
        )
    
    # Busca usuário atual
    current_user = await get_current_user(token, db)
    
    # Verifica se o usuário existe no banco
    db_user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not db_user:
        logger.warning(f"⚠️ Usuário não encontrado: {current_user.id}")
        raise UnauthorizedException(
            message_key="AUTH_USER_NOT_FOUND",
            request=request
        )
    
    logger.debug(f"📊 Perfil recuperado para usuário: {current_user.email}")
    return current_user


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    logout_data: LogoutRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Logout do usuário com revogação do token.
    
    🔧 VALIDAÇÕES:
        - Refresh token deve pertencer ao usuário logado
        - Token é adicionado à blacklist
    
    Returns:
        dict: Mensagem de sucesso
    """
    language = getattr(request.state, "language", "pt")
    
    # Valida o refresh token
    try:
        payload = decode_token(logout_data.refresh_token)
        if payload.user_id != current_user.id:
            logger.warning(f"⚠️ Tentativa de logout com token de outro usuário: {current_user.id}")
            raise UnauthorizedException(
                message_key="AUTH_TOKEN_INVALID",
                request=request
            )
    except Exception as e:
        logger.warning(f"⚠️ Erro ao validar refresh token no logout: {e}")
        raise UnauthorizedException(
            message_key="AUTH_TOKEN_INVALID",
            request=request
        )
    
    # Adiciona token à blacklist
    await add_token_to_blacklist(logout_data.refresh_token, current_user.id, db)
    
    logger.info(f"✅ Usuário fez logout: {current_user.email}")
    
    return {"message": get_message("SUCCESS_LOGOUT", language)}


@router.post("/forgot-password", response_model=dict)
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    db=Depends(get_database)
):
    """
    Solicita redefinição de senha (envia email com token).
    
    🔧 FLUXO:
        1. Busca usuário pelo email
        2. Gera token seguro (32 bytes)
        3. Salva token no banco com expiração (15 minutos)
        4. Envia email com link de redefinição
    
    🔧 SEGURANÇA:
        - Retorna mesma mensagem para email existente ou não (evita enumeração)
        - Token expira em 15 minutos
    
    Returns:
        dict: Mensagem de confirmação
    """
    language = getattr(request.state, "language", "pt")
    
    # Busca usuário pelo email
    user = await db.users.find_one({"email": forgot_data.email})
    
    # 🔧 SEGURANÇA: Mesma resposta para email existente ou não
    if not user:
        logger.info(f"🔐 Tentativa de recuperação para email não cadastrado: {forgot_data.email}")
        return {"message": get_message("INFO_PASSWORD_RESET_EMAIL_SENT", language)}
    
    # Gera token seguro
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    # Salva token no banco
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "reset_token": token,
            "reset_token_expires": expires
        }}
    )
    
    # Envia email (ou mock em desenvolvimento)
    try:
        from app.services.email_service import email_service
        await email_service.send_password_reset_email(
            to_email=user["email"],
            reset_token=token,
            language=language
        )
        logger.info(f"📧 Email de redefinição enviado para: {user['email']}")
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
    """
    Redefine a senha usando token recebido por email.
    
    🔧 VALIDAÇÕES:
        - Token deve existir e não estar expirado
        - Nova senha deve ser forte (3/4 critérios)
    
    Returns:
        dict: Mensagem de sucesso
    """
    language = getattr(request.state, "language", "pt")
    
    # Valida força da nova senha
    try:
        validate_password_strength(reset_data.new_password)
    except ValueError as e:
        logger.warning(f"⚠️ Senha fraca na redefinição: {str(e)}")
        raise ValidationException(
            message_key="AUTH_WEAK_PASSWORD",
            request=request
        )
    
    # Busca usuário com token válido
    user = await db.users.find_one({
        "reset_token": reset_data.token,
        "reset_token_expires": {"$gt": datetime.now(timezone.utc)}
    })
    
    if not user:
        logger.warning(f"⚠️ Tentativa de redefinição com token inválido ou expirado")
        raise I18nHTTPException(
            status_code=400,
            message_key="AUTH_INVALID_RESET_TOKEN",
            request=request
        )
    
    # Gera novo hash da senha
    new_hash = get_password_hash(reset_data.new_password)
    
    # Atualiza usuário
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": new_hash,
            "reset_token": None,
            "reset_token_expires": None,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    logger.info(f"✅ Senha redefinida para usuário: {user['email']}")
    
    return {"message": get_message("SUCCESS_PASSWORD_RESET", language)}


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - I18n completo (4 idiomas)
#   - Rate limiting no login (5/min)
#   - Refresh token com blacklist
#   - Validação de força de senha (3/4 critérios)
#   - Logs de auditoria no login
#   - Validação de termos aceitos no registro
#   - Validação de refresh token no logout
#   - Verificação de blacklist no /me
#   - 🔧 CORRIGIDO: login usa model_validate em vez de criação manual
#   - 🔧 CORRIGIDO: Cria perfil vazio no registro do usuário
#   - 🔧 CORRIGIDO: Documentação completa de cada endpoint
#   - 🔧 CORRIGIDO: Logs estruturados com níveis apropriados
#   - 🔧 CORRIGIDO: Tratamento de erros com i18n
#
# ❌ Não implementado (Pós-MVP):
#   - 2FA (dois fatores)
#   - Biometria/FaceID
#   - Notificação de novo login
#   - Recaptcha no registro
#   - Verificação de email
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: I18n e correções (25/05/2026)
#   - v3: Refatoração - validate_password_strength movido para utils/validators_extras.py (02/07/2026)
#   - v4: Correção - login usa model_validate (05/07/2026)
#   - v5: ADICIONADO - Cria perfil vazio no registro do usuário (20/07/2026)
#   - v5.1: ADICIONADO - Documentação completa de cada endpoint (20/07/2026)
#   - v5.2: CORRIGIDO - Logs estruturados com níveis apropriados (20/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO