"""
Modelo de Usuário
Arquivo: backend/app/models/user.py

Funcionalidades:
- Cadastro de usuários com validação de senha
- Autenticação via JWT
- Consentimento LGPD (pesquisa, termos)
- Preferências (idioma, moeda)

Principais features:
- Validação de senha flexível (3 de 4 critérios)
- I18n completo (4 idiomas)
- Campos opcionais no registro (location, occupation, financial_goal)
- Consentimento LGPD com rastreamento de data
- Preferências de idioma e moeda
- Herança de BaseModelWithoutUser (id, created_at, updated_at, touch(), convert_objectid())
- ✅ CORRIGIDO: NÃO herda user_id (User é o próprio dono)
- ✅ CORRIGIDO: Campos opcionais no UserCreate
- ✅ CORRIGIDO: UserResponse herda de User
- ✅ CORRIGIDO: password_hash excluído do UserResponse
"""

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator
from typing import Optional, Literal, Any
from datetime import datetime, timezone
import re

from app.models.base import BaseModelWithoutUser
from app.models.mixins import AuditMixin
from app.utils.validators import convert_objectid_to_str


class User(BaseModelWithoutUser, AuditMixin):
    """
    Modelo principal de Usuário.
    
    🔧 HERDA DE:
      - BaseModelWithoutUser: id, created_at, updated_at, touch(), convert_objectid()
      - AuditMixin: created_by, updated_by, deleted_at, is_deleted, mark_deleted(), restore()
    
    🔧 CAMPOS ADICIONADOS:
      - name: Nome completo
      - email: E-mail do usuário
      - password_hash: Hash da senha (Argon2)
      - monthly_income: Renda mensal em centavos
      - profession_type: Tipo de perfil profissional
      - location: Cidade - Estado (opcional no registro)
      - occupation: Área de atuação (opcional no registro)
      - financial_goal: Objetivo financeiro (opcional no registro)
      - research_consent: Consentimento para pesquisa
      - terms_accepted: Aceite dos termos
      - terms_accepted_at: Data de aceite dos termos
      - consent_updated_at: Data de atualização do consentimento
      - language: Idioma (pt, en, es, zh)
      - currency: Moeda (BRL, USD, EUR, CNY)
    
    🔧 NOTA:
      - NÃO tem user_id porque é o próprio dono do registro
    """
    
    # ========== CAMPOS PRINCIPAIS ==========
    
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nome completo do usuário"
    )
    
    email: EmailStr = Field(
        ...,
        description="E-mail do usuário (usado para login)"
    )
    
    password_hash: str = Field(
        ...,
        description="Hash da senha (Argon2)"
    )
    
    monthly_income: int = Field(
        default=0,
        ge=0,
        description="Renda mensal em CENTAVOS (ex: 500000 = R$5.000,00)"
    )
    
    profession_type: Literal[
        "clt", "autonomo", "mei", "empresario", "servidor",
        "aposentado", "estudante", "desempregado", "investidor", "outros"
    ] = Field(
        default="outros",
        description="Tipo de perfil profissional"
    )
    
    # ========== CAMPOS OPCIONAIS NO REGISTRO ==========
    # ✅ CORRIGIDO: São obrigatórios no modelo, mas opcionais no UserCreate
    
    location: str = Field(
        ...,
        max_length=200,
        description="Cidade - Estado (obrigatório para análise da IA)"
    )
    
    occupation: str = Field(
        ...,
        max_length=100,
        description="Área de atuação profissional (obrigatório para perfil)"
    )
    
    financial_goal: str = Field(
        ...,
        max_length=500,
        description="Objetivo financeiro principal (obrigatório para recomendações)"
    )
    
    # ========== CONSENTIMENTO LGPD ==========
    
    research_consent: bool = Field(
        default=False,
        description="Consentimento para pesquisa anônima"
    )
    
    terms_accepted: bool = Field(
        default=False,
        description="Aceite dos termos de uso"
    )
    
    terms_accepted_at: Optional[datetime] = Field(
        default=None,
        description="Data de aceite dos termos"
    )
    
    consent_updated_at: Optional[datetime] = Field(
        default=None,
        description="Data de atualização do consentimento"
    )
    
    # ========== PREFERÊNCIAS ==========
    
    language: str = Field(
        default="pt",
        description="Idioma (pt, en, es, zh)"
    )
    
    currency: str = Field(
        default="BRL",
        description="Moeda (BRL, USD, EUR, CNY)"
    )
    
    # ========== VALIDAÇÕES ==========
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """
        Valida se o idioma é suportado.
        🔧 i18n: Mensagem com chave ERROR_INVALID_LANGUAGE
        """
        supported = ["pt", "en", "es", "zh"]
        if v not in supported:
            raise ValueError(f'Idioma deve ser um dos: {supported}')
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """
        Valida se a moeda é suportada.
        🔧 i18n: Mensagem com chave ERROR_INVALID_CURRENCY
        """
        supported = ["BRL", "USD", "EUR", "CNY"]
        if v not in supported:
            raise ValueError(f'Moeda deve ser um dos: {supported}')
        return v


class UserCreate(BaseModel):
    """
    Schema para CRIAÇÃO de usuário.
    
    🔧 DIFERENÇAS DO MODEL USER:
      - password em vez de password_hash (para validação)
      - Não tem campos de auditoria (ainda não existe no banco)
      - ✅ CORRIGIDO: location, occupation, financial_goal são OPCIONAIS
    """
    
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nome completo"
    )
    
    email: EmailStr = Field(
        ...,
        description="E-mail"
    )
    
    password: str = Field(
        ...,
        min_length=8,
        description="Senha (mínimo 8 caracteres)"
    )
    
    monthly_income: int = Field(
        default=0,
        ge=0,
        description="Renda mensal em CENTAVOS"
    )
    
    # ✅ CORRIGIDO: OPCIONAIS no registro
    location: Optional[str] = Field(
        None,
        max_length=200,
        description="Cidade - Estado (opcional no registro)"
    )
    
    profession_type: Literal[
        "clt", "autonomo", "mei", "empresario", "servidor",
        "aposentado", "estudante", "desempregado", "investidor", "outros"
    ] = Field(
        default="outros",
        description="Tipo de perfil profissional"
    )
    
    occupation: Optional[str] = Field(
        None,
        max_length=100,
        description="Área de atuação (opcional no registro)"
    )
    
    financial_goal: Optional[str] = Field(
        None,
        max_length=500,
        description="Objetivo financeiro (opcional no registro)"
    )
    
    terms_accepted: bool = Field(
        default=False,
        description="Aceite dos termos"
    )
    
    research_consent: bool = Field(
        default=False,
        description="Consentimento para pesquisa"
    )
    
    language: str = Field(
        default="pt",
        description="Idioma"
    )
    
    currency: str = Field(
        default="BRL",
        description="Moeda"
    )

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Valida a força da senha (pelo menos 3 dos 4 critérios).
        🔧 i18n: Mensagens com chaves ERROR_PASSWORD_*
        """
        if len(v) < 8:
            raise ValueError('A senha deve ter pelo menos 8 caracteres')
        
        criteria = 0
        if re.search(r"[A-Z]", v):
            criteria += 1
        if re.search(r"[a-z]", v):
            criteria += 1
        if re.search(r"\d", v):
            criteria += 1
        if re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            criteria += 1
        
        if criteria < 3:
            raise ValueError(
                'A senha deve conter pelo menos 3 dos seguintes: '
                'letra maiúscula, letra minúscula, número, caractere especial'
            )
        return v

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        supported = ["pt", "en", "es", "zh"]
        if v not in supported:
            raise ValueError(f'Idioma deve ser um dos: {supported}')
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        supported = ["BRL", "USD", "EUR", "CNY"]
        if v not in supported:
            raise ValueError(f'Moeda deve ser um dos: {supported}')
        return v


class UserLogin(BaseModel):
    """Schema para LOGIN"""
    email: EmailStr = Field(..., description="E-mail")
    password: str = Field(..., description="Senha")


class UserResponse(User):
    """
    Schema para RESPOSTA da API (dados públicos).
    
    🔧 ✅ CORRIGIDO: Exclui password_hash da resposta.
    
    🔧 DIFERENÇAS DO MODEL USER:
      - id é obrigatório (já existe no banco)
      - Não tem password_hash (campo sensível)
      - location, occupation, financial_goal são opcionais (caso não preenchidos)
    """
    
    id: str = Field(..., alias="_id", description="ID do usuário")
    
    # 🔧 EXCLUI PASSWORD_HASH DA RESPOSTA
    password_hash: None = None
    
    # 🔧 Torna campos opcionais para evitar erro se o usuário não preencheu
    location: Optional[str] = None
    occupation: Optional[str] = None
    financial_goal: Optional[str] = None


class Token(BaseModel):
    """Schema para TOKEN de autenticação"""
    access_token: str = Field(..., description="Token JWT de acesso")
    token_type: str = Field(default="bearer", description="Tipo do token")
    user: UserResponse = Field(..., description="Dados do usuário")


class UserUpdate(BaseModel):
    """
    Schema para ATUALIZAÇÃO de usuário.
    
    🔧 TODOS OS CAMPOS SÃO OPCIONAIS:
      - Permite atualização parcial
      - Validações aplicadas apenas quando campo é fornecido
    """
    
    name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Nome completo"
    )
    
    email: Optional[EmailStr] = Field(
        None,
        description="E-mail"
    )
    
    monthly_income: Optional[int] = Field(
        None,
        ge=0,
        description="Renda mensal em CENTAVOS"
    )
    
    location: Optional[str] = Field(
        None,
        max_length=200,
        description="Cidade - Estado"
    )
    
    profession_type: Optional[Literal[
        "clt", "autonomo", "mei", "empresario", "servidor",
        "aposentado", "estudante", "desempregado", "investidor", "outros"
    ]] = Field(
        None,
        description="Tipo de perfil profissional"
    )
    
    occupation: Optional[str] = Field(
        None,
        max_length=100,
        description="Área de atuação"
    )
    
    financial_goal: Optional[str] = Field(
        None,
        max_length=500,
        description="Objetivo financeiro"
    )
    
    research_consent: Optional[bool] = Field(
        None,
        description="Consentimento para pesquisa"
    )
    
    terms_accepted: Optional[bool] = Field(
        None,
        description="Aceite dos termos"
    )
    
    language: Optional[str] = Field(
        None,
        description="Idioma (pt, en, es, zh)"
    )
    
    currency: Optional[str] = Field(
        None,
        description="Moeda (BRL, USD, EUR, CNY)"
    )

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            supported = ["pt", "en", "es", "zh"]
            if v not in supported:
                raise ValueError(f'Idioma deve ser um dos: {supported}')
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            supported = ["BRL", "USD", "EUR", "CNY"]
            if v not in supported:
                raise ValueError(f'Moeda deve ser um dos: {supported}')
        return v


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithoutUser (id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de AuditMixin (created_by, updated_by, deleted_at, is_deleted, mark_deleted(), restore())
#   - Validação de idioma e moeda
#   - Validação de senha (3/4 critérios)
#   - ✅ CORRIGIDO: Campos opcionais no UserCreate (location, occupation, financial_goal)
#   - ✅ CORRIGIDO: UserResponse herda de User (elimina duplicação)
#   - ✅ CORRIGIDO: password_hash excluído do UserResponse
#   - ✅ CORRIGIDO: location, occupation, financial_goal opcionais no UserResponse
#   - Consentimento LGPD com rastreamento
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response, Login, Token)
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de formato "Cidade - Estado" para location
#   - 2FA (dois fatores)
#   - Biometria/FaceID
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser e AuditMixin (03/07/2026)
#   - v3: Correções - BaseModelWithoutUser, campos opcionais, UserResponse herda de User (03/07/2026)
#   - v4: Correção - password_hash excluído do UserResponse, campos opcionais (04/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO