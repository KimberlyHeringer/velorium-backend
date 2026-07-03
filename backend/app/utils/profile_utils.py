"""
Funções Utilitárias para Perfil Financeiro
Arquivo: backend/app/utils/profile_utils.py

Funcionalidade: Centraliza funções relacionadas ao perfil financeiro
para reutilização na rota profile.py.

🔧 USO:
    from app.utils.profile_utils import (
        create_empty_profile,
        prepare_profile_response,
        ensure_profile_collection
    )
    
    await ensure_profile_collection(db)
    empty = create_empty_profile(user_id)
    response = prepare_profile_response(profile, fallback_user_id)

📋 ESTRUTURA:
    - create_empty_profile(): Cria perfil vazio com campos obrigatórios
    - prepare_profile_response(): Prepara perfil para resposta com fallback
    - ensure_profile_collection(): Garante que a coleção existe
"""

from datetime import datetime, timezone
from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def create_empty_profile(user_id: str) -> dict:
    """
    Cria um perfil vazio com campos obrigatórios.
    
    Args:
        user_id: ID do usuário
    
    Returns:
        dict: Dicionário com campos obrigatórios preenchidos
    
    Exemplo:
        >>> create_empty_profile("user123")
        {
            "id": "user123",
            "user_id": "user123",
            "created_at": datetime(...),
            "updated_at": datetime(...)
        }
    """
    now = datetime.now(timezone.utc)
    return {
        "id": user_id,
        "user_id": user_id,
        "created_at": now,
        "updated_at": now
    }


def prepare_profile_response(profile: dict, fallback_user_id: str = None) -> dict:
    """
    Prepara o perfil para resposta com os campos obrigatórios.
    
    Args:
        profile: Dicionário do perfil (pode ser None)
        fallback_user_id: ID do usuário para criar perfil vazio se profile for None
    
    Returns:
        dict: Dicionário preparado para resposta
    
    Exemplo:
        >>> profile = {"_id": ObjectId(...), "user_id": "user123"}
        >>> prepare_profile_response(profile)
        {"id": "user123", "user_id": "user123", ...}
        
        >>> prepare_profile_response(None, "user123")
        {"id": "user123", "user_id": "user123", ...}  # perfil vazio
    """
    if not profile:
        if fallback_user_id:
            return create_empty_profile(fallback_user_id)
        return {}
    
    result = convert_objectid_to_str(profile)
    
    if "_id" in profile:
        result["id"] = str(profile["_id"])
    elif "id" not in result:
        result["id"] = result.get("user_id") or "unknown"
    
    return result


async def ensure_profile_collection(db) -> bool:
    """
    Garante que a coleção user_profiles existe.
    
    Args:
        db: Conexão com o banco de dados
    
    Returns:
        bool: True se a coleção existe ou foi criada
    
    Exemplo:
        await ensure_profile_collection(db)
    """
    collections = await db.list_collection_names()
    if "user_profiles" not in collections:
        logger.warning("⚠️ Coleção 'user_profiles' não existe, criando...")
        await db.create_collection("user_profiles")
        logger.info("✅ Coleção 'user_profiles' criada com sucesso")
    return True


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Funções reutilizáveis para perfil
# ✅ create_empty_profile com campos obrigatórios
# ✅ prepare_profile_response com fallback
# ✅ ensure_profile_collection com logs
# ✅ Conversão de ObjectId centralizada
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO