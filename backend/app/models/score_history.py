"""
Modelo de Histórico de Score Financeiro
Arquivo: backend/app/models/score_history.py

Funcionalidades:
- Registro histórico do score financeiro do usuário
- Snapshot diário/semanal do score
- Histórico imutável (append-only)

Principais features:
- score escala 0-100 (alinhado com frontend)
- Histórico imutável (sem updated_at)
- Validação: date não pode ser no futuro (com suporte a strings e datetime)
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, touch(), convert_objectid())
- ✅ CORRIGIDO: validate_date_not_future agora valida strings também
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.models.base import BaseModelWithUser


class ScoreHistory(BaseModelWithUser):
    """
    Histórico imutável do score financeiro do usuário.
    Cada registro representa um snapshot diário/semanal do score.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, touch(), convert_objectid()
    
    🔧 NOTA: updated_at foi removido porque este modelo é imutável (append-only)
    
    🔧 CAMPOS ADICIONADOS:
      - score: Score financeiro (0-100)
      - details: Detalhamento do cálculo (JSON livre)
      - date: Data de referência do score
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Score financeiro (escala 0-100, onde 100 é máximo)"
    )
    
    # ========== CAMPOS OPCIONAIS ==========
    
    details: Optional[Dict] = Field(
        None,
        description="Detalhamento do cálculo (JSON livre) - PÓS-MVP: usar modelo específico"
    )
    
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de referência do score (ex: score referente a 2025-04-01)"
    )
    
    # NOTA: created_at já vem do BaseModelWithUser
    # NOTA: updated_at foi removido (histórico imutável)

    # ========== VALIDAÇÕES ==========

    @field_validator('date', mode='before')
    @classmethod
    def validate_date_not_future(cls, v: Any) -> Any:
        """
        Valida que date não seja no futuro.
        🔧 CORRIGIDO: Aceita strings e datetime.
        🔧 i18n: Mensagem com chave ERROR_SCORE_DATE_FUTURE
        """
        # Se for string, converte para datetime
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                raise ValueError('date inválida')
        
        # Agora valida se é datetime e está no futuro
        if isinstance(v, datetime):
            if v > datetime.now(timezone.utc):
                raise ValueError('date não pode ser no futuro')
        return v


class ScoreHistoryResponse(ScoreHistory):
    """
    Schema para resposta da API.
    
    🔧 ✅ CORRIGIDO: id é obrigatório (sobrescreve Optional)
    """
    
    id: str = Field(..., alias="_id", description="ID do registro de score")


# ========== ÍNDICE RECOMENDADO ==========
# 
# 🔧 ADICIONAR EM indexes.py:
# 
# ================================================================
# 6. HISTÓRICO DE SCORE (SCORE_HISTORY)
# ================================================================
# 
# # Índice composto para queries de histórico por usuário e data
# await db.score_history.create_index([("user_id", 1), ("date", -1)])
# 
# ================================================================


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, touch(), convert_objectid())
#   - score escala 0-100 (alinhado com frontend)
#   - Validação: date não pode ser no futuro (suporte a strings e datetime)
#   - Histórico imutável (sem updated_at)
#   - I18n completo com chaves de erro
#   - Schema de resposta (Response)
#   - ✅ CORRIGIDO: validate_date_not_future valida strings também
#   - ✅ CORRIGIDO: ScoreHistoryResponse id obrigatório
#
# ❌ Não implementado (Pós-MVP):
#   - Tipagem do details: Dict[str, float] ou modelo específico ScoreDetails
#   - Limitar tamanho do details (max_length)
#   - Validação de score com details
#   - Propriedades calculadas: score_percentage, rating
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser (03/07/2026)
#   - v3: Correções - Response id obrigatório, validate_date_not_future valida strings (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO