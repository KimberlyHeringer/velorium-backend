"""
Rotas de Usuário (Perfil, Senha, Consentimento, Preferências, Export, Delete)
Arquivo: backend/app/routes/user.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId
import json

from app.database import get_database
from app.models.user import UserResponse, UserUpdate
from app.utils.auth import get_current_user, get_password_hash, verify_password
from app.utils.rate_limiter import limiter
from fastapi import Request

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


class DeleteAccountResponse(BaseModel):
    message: str
    user_id: str


# ========== ENDPOINTS DE PERFIL ==========

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    update_data = {}
    if profile_data.name is not None:
        update_data["name"] = profile_data.name
    if profile_data.email is not None:
        update_data["email"] = profile_data.email.lower()
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar")
    
    if "email" in update_data:
        existing = await db.users.find_one({"email": update_data["email"]})
        if existing and str(existing["_id"]) != str(current_user.id):
            raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    updated_user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    updated_user["_id"] = str(updated_user["_id"])
    return UserResponse(**updated_user)


@router.put("/change-password", response_model=dict)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if not verify_password(password_data.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Senha atual incorreta")
    
    new_hash = get_password_hash(password_data.new_password)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Senha alterada com sucesso"}


# ========== ENDPOINTS DE PREFERÊNCIAS ==========

@router.get("/preferences", response_model=dict)
async def get_preferences(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Retorna as preferências do usuário (idioma, moeda)"""
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {
        "language": user.get("language", "pt"),
        "currency": user.get("currency", "BRL")
    }


@router.put("/preferences", response_model=dict)
async def update_preferences(
    prefs: PreferencesUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """Atualiza as preferências do usuário (idioma, moeda)"""
    update_data = {}
    if prefs.language is not None:
        if prefs.language not in ["pt", "en", "es", "zh"]:
            raise HTTPException(status_code=400, detail="Idioma inválido")
        update_data["language"] = prefs.language
    if prefs.currency is not None:
        if prefs.currency not in ["BRL", "USD", "EUR", "CNY"]:
            raise HTTPException(status_code=400, detail="Moeda inválida")
        update_data["currency"] = prefs.currency
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhuma preferência para atualizar")
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_data}
    )
    
    return {"message": "Preferências atualizadas com sucesso"}


# ========== ENDPOINTS DE CONSENTIMENTO ==========

@router.put("/consent", response_model=dict)
async def update_consent(
    consent_data: ConsentUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    update_fields = {
        "research_consent": consent_data.research_consent,
        "updated_at": datetime.now(timezone.utc),
        "consent_updated_at": datetime.now(timezone.utc)
    }
    if consent_data.terms_accepted:
        update_fields["terms_accepted"] = True
        update_fields["terms_accepted_at"] = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail="Os Termos de Uso não podem ser desmarcados depois de aceitos.")
    
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": update_fields}
    )
    return {"message": "Consentimento atualizado com sucesso"}


@router.get("/consent-status", response_model=ConsentStatusResponse)
async def get_consent_status(
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    user = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return ConsentStatusResponse(
        terms_accepted=user.get("terms_accepted", False),
        research_consent=user.get("research_consent", False),
        terms_accepted_at=user.get("terms_accepted_at")
    )


# ========== #31 - POLÍTICA DE PRIVACIDADE ==========

@router.get("/privacy-policy", response_model=dict)
async def get_privacy_policy():
    """
    Retorna o texto da Política de Privacidade (LGPD)
    """
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


# ========== #32 - EXPORTAR DADOS DO USUÁRIO ==========

@router.get("/export", response_model=ExportDataResponse)
@limiter.limit("2/minute")
async def export_user_data(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Exporta todos os dados do usuário em formato JSON (LGPD - Direito de Portabilidade)
    """
    user_id = str(current_user.id)
    
    # Busca dados de todas as coleções
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user["_id"] = str(user["_id"])
        # Remove campos sensíveis que não devem ser exportados
        user.pop("password_hash", None)
        user.pop("reset_token", None)
        user.pop("reset_token_expires", None)
    
    # Transações
    transactions = await db.transactions.find({"user_id": user_id}).to_list(10000)
    for t in transactions:
        t["_id"] = str(t["_id"])
    
    # Contas a pagar
    bills = await db.bills.find({"user_id": user_id}).to_list(10000)
    for b in bills:
        b["_id"] = str(b["_id"])
    
    # Cartões de crédito
    credit_cards = await db.credit_cards.find({"user_id": user_id}).to_list(10000)
    for c in credit_cards:
        c["_id"] = str(c["_id"])
    
    # Compras parceladas
    purchases = await db.credit_card_purchases.find({"user_id": user_id}).to_list(10000)
    for p in purchases:
        p["_id"] = str(p["_id"])
    
    # Metas
    goals = await db.goals.find({"user_id": user_id}).to_list(10000)
    for g in goals:
        g["_id"] = str(g["_id"])
    
    # Score financeiro
    score_history = await db.score_history.find({"user_id": user_id}).to_list(10000)
    for s in score_history:
        s["_id"] = str(s["_id"])
    
    # Conquistas
    achievements = await db.achievements.find({"user_id": user_id}).to_list(10000)
    for a in achievements:
        a["_id"] = str(a["_id"])
    
    # Perfil financeiro
    profile = await db.user_profiles.find_one({"user_id": user_id})
    if profile:
        profile["_id"] = str(profile["_id"])
    
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
    
    return ExportDataResponse(
        message="Dados exportados com sucesso. Este arquivo contém todas as suas informações do Velorium.",
        data=export_data
    )


# ========== #33 - DELETAR CONTA (DIREITO AO ESQUECIMENTO) ==========

@router.delete("/delete", response_model=DeleteAccountResponse)
@limiter.limit("1/minute")
async def delete_account(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Remove permanentemente todos os dados do usuário (LGPD - Direito ao Esquecimento)
    """
    user_id = str(current_user.id)
    user_obj_id = ObjectId(user_id)
    
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
            # Deleta o documento do usuário
            await db[collection_name].delete_one({"_id": user_obj_id})
        else:
            # Deleta todos os documentos associados ao usuário
            await db[collection_name].delete_many({"user_id": user_id})
    
    # Remove tokens da blacklist específicos do usuário
    await db.refresh_token_blacklist.delete_many({"user_id": user_id})
    
    return DeleteAccountResponse(
        message="Sua conta e todos os dados associados foram permanentemente removidos do Velorium. Agradecemos por ter usado nosso serviço.",
        user_id=user_id
    )


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ #31 - Política de Privacidade (endpoint GET /users/privacy-policy)
# ✅ #32 - Exportar dados (endpoint GET /users/export) com rate limit 2/min
# ✅ #33 - Deletar conta (endpoint DELETE /users/delete) com rate limit 1/min
# ✅ Dados sensíveis (password_hash, reset_token) excluídos do export
# ✅ Todas as coleções relevantes são limpas ao deletar conta
# ✅ Retorno estruturado com mensagem amigável