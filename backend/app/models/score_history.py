"""
Modelo de Histórico de Score Financeiro
Arquivo: backend/app/models/score_history.py

🔧 CORRIGIDO:
- 🔧 CORRIGIDO: score escala 0-100 (alinhado com frontend)
- 🔧 MELHORADO: Documentação do campo date
- 🔧 NOVO: model_validator para conversão de ObjectId
- 🔧 NOVO: Validação de date não futura
- 🔧 NOTA: updated_at removido (histórico imutável)
- 🔧 NOTA: Índice composto (user_id, date) adicionado no indexes.py
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import convert_objectid_to_str


class ScoreHistory(BaseModel):
    """
    Histórico imutável do score financeiro do usuário.
    Cada registro representa um snapshot diário/semanal do score.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    
    # 🔧 CORRIGIDO: escala 0-100 (alinhado com frontend)
    score: int = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Score financeiro (escala 0-100, onde 100 é máximo)"
    )
    
    details: Optional[Dict] = Field(
        None, 
        description="Detalhamento do cálculo (JSON livre) - PÓS-MVP: usar modelo específico"
    )
    
    # 🔧 MELHORADO: Documentação mais clara
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data de referência do score (ex: score referente a 2025-04-01)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Data em que este registro foi inserido no banco"
    )
    
    # NOTA: updated_at foi removido porque este modelo é imutável (append-only)

    # ========== VALIDAÇÕES ==========

    @field_validator('date', mode='before')
    @classmethod
    def validate_date_not_future(cls, v: Any) -> Any:
        """
        🔧 NOVO: Valida que date não seja no futuro.
        🔧 i18n: Mensagem com chave ERROR_SCORE_DATE_FUTURE
        """
        if isinstance(v, datetime):
            if v > datetime.now(timezone.utc):
                raise ValueError('date não pode ser no futuro')
        return v

    # ========== CONVERSÃO DE OBJECTID ==========

    @model_validator(mode='before')
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """
        🔧 NOVO: Converte ObjectId para string.
        """
        if isinstance(data, ScoreHistory):
            return data
        
        return convert_objectid_to_str(data)


class ScoreHistoryResponse(ScoreHistory):
    """Schema para resposta da API"""
    id: str = Field(..., description="ID do registro de score")
    
    # ========== PROPRIEDADES CALCULADAS (PÓS-MVP) ==========
    #
    # @computed_field
    # @property
    # def score_percentage(self) -> float:
    #     """Score como percentual (0-100%)."""
    #     return (self.score / 100) * 100
    #
    # @computed_field
    # @property
    # def rating(self) -> str:
    #     """Classificação do score."""
    #     if self.score >= 80:
    #         return "excelente"
    #     elif self.score >= 60:
    #         return "bom"
    #     elif self.score >= 40:
    #         return "regular"
    #     elif self.score >= 20:
    #         return "baixo"
    #     else:
    #         return "critico"


# ========== PÓS-MVP: MODELO ESPECÍFICO PARA DETAILS ==========
#
# from pydantic import computed_field
#
# class ScoreDetails(BaseModel):
#     """Detalhamento do cálculo do score financeiro"""
#     categories: Dict[str, float] = Field(
#         default_factory=dict,
#         description="Pontuação por categoria (0-1)"
#     )
#     factors: Dict[str, float] = Field(
#         default_factory=dict,
#         description="Fatores considerados no cálculo"
#     )
#     weights: Dict[str, float] = Field(
#         default_factory=dict,
#         description="Pesos aplicados a cada fator"
#     )
#     
#     @computed_field
#     @property
#     def total_score(self) -> float:
#         if not self.factors or not self.weights:
#             return 0.0
#         total = sum(self.factors.get(k, 0) * self.weights.get(k, 0) for k in self.factors)
#         return round(total, 4)


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. 🔧 CORRIGIDO: score escala 0-100 (alinhado com frontend)
2. 🔧 MELHORADO: Documentação do campo date
3. 🔧 NOVO: model_validator para conversão de ObjectId
4. 🔧 NOVO: Validação de date não futura
5. 🔧 NOTA: updated_at removido (histórico imutável)
6. 🔧 NOTA: Índice composto (user_id, date) adicionado no indexes.py

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_SCORE_DATE_FUTURE → "date não pode ser no futuro"

⏳ PENDÊNCIAS PÓS-MVP:
================================================================================
1. Tipagem do details: Dict[str, float] ou modelo específico ScoreDetails
2. Limitar tamanho do details (max_length)
3. Validação de score com details
4. Propriedades calculadas: score_percentage, rating

================================================================================
✅ STATUS: APROVADO PARA MVP
================================================================================
"""