"""
Modelo de Histórico de Score Financeiro
Arquivo: backend/app/models/score_history.py
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict
from datetime import datetime, timezone
from bson import ObjectId


class ScoreHistory(BaseModel):
    """
    Histórico imutável do score financeiro do usuário.
    Cada registro representa um snapshot diário/semanal do score.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str                                    # referência ao usuário
    score: int = Field(..., ge=0, le=1000)          # score entre 0 e 1000 (ajuste conforme sua escala)
    details: Optional[Dict] = None                  # detalhamento do cálculo (JSON livre)
    
    # date = data de referência do score (ex: "score referente a 2025-04-01")
    # created_at = momento em que este registro foi inserido no banco
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # NOTA: updated_at foi removido porque este modelo é imutável (append-only)


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ updated_at removido (histórico imutável)
# ✅ score validado entre 0 e 1000
# ✅ Mantidos date e created_at (com documentação da diferença)
# ✅ details como Dict livre (aceitável para MVP)
#
# 📌 Pendente (infra): Adicionar índice composto (user_id, date) no database.py
#    para consultas eficientes de histórico