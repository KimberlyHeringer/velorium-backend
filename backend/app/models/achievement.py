"""
Modelo de Conquistas do Usuário (sincronizado)
Arquivo: backend/app/models/achievement.py
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId
import re


class Achievement(BaseModel):
    """Modelo de uma conquista desbloqueada pelo usuário"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    type: str            # month_closed, goal_completed, etc.
    month: Optional[str] = None   # para conquistas de mês fechado (MM/YYYY)
    name: Optional[str] = None    # nome da conquista
    description: str               # texto descritivo
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    automatica: bool = True       # conquista automática ou manual?

    # ========== VALIDAÇÕES ==========
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Valida se o tipo de conquista é permitido"""
        tipos_validos = [
            'month_closed',      # Fechou o mês no azul
            'goal_completed',    # Completou uma meta
            'score_milestone',   # Atingiu uma pontuação de score
            'first_transaction', # Primeira transação cadastrada
            'savings_milestone', # Atingiu meta de economia
            'debt_paid'          # Pagou uma dívida
        ]
        if v not in tipos_validos:
            raise ValueError(f'Tipo de conquista inválido. Use um dos: {tipos_validos}')
        return v
    
    @field_validator('month')
    @classmethod
    def validate_month(cls, v: Optional[str]) -> Optional[str]:
        """Valida se o mês está no formato MM/YYYY (quando informado)"""
        if v is not None:
            if not re.match(r'^\d{2}/\d{4}$', v):
                raise ValueError('Mês deve estar no formato MM/YYYY (ex: 12/2025)')
            
            # Valida se o mês é entre 01 e 12
            mes = int(v.split('/')[0])
            if mes < 1 or mes > 12:
                raise ValueError('Mês deve ser entre 01 e 12')
        return v


class AchievementCreate(BaseModel):
    """Schema para criação de conquista"""
    type: str
    month: Optional[str] = None
    name: Optional[str] = None
    description: str
    automatica: bool = True


class AchievementResponse(Achievement):
    """Schema para resposta da API"""
    id: str


"""
================================================================================
📋 FEEDBACK DO ARQUIVO (MVP)

✅ O QUE FOI MODIFICADO/MELHORADO NESTA VERSÃO:
--------------------------------------------------------------------------------
1. Adicionado validação para o campo 'type' - só aceita tipos pré-definidos
2. Adicionado validação para o campo 'month' - formato MM/YYYY e mês entre 01-12
3. Importado 're' (regex) e 'field_validator' do Pydantic
4. Adicionados comentários explicativos nas validações

✅ O QUE ESTÁ BOM E PODE MANTER:
--------------------------------------------------------------------------------
1. Uso de timezone.utc para datas (evita problemas com fusos)
2. Campo 'automatica' com default True (boa experiência para usuário)
3. Herança entre Achievement e AchievementResponse
4. Alias "_id" para compatibilidade com MongoDB

⚠️ PENDÊNCIAS PARA VERSÕES FUTURAS (NÃO CRÍTICAS PARA MVP):
--------------------------------------------------------------------------------
1. Adicionar índices no MongoDB (database.py):
   - achievements: [("user_id", 1), ("type", 1), ("date", -1)]
   - achievements: [("user_id", 1), ("month", 1)]

2. Renomear campo 'automatica' para 'is_automatic' (consistência com inglês) - 
   ⚠️ Isso exigirá alteração no frontend, então NÃO FAZER AGORA.

3. Adicionar campo 'earned_at' separado do 'date' (data que ganhou vs data que foi registrada)

4. Internacionalização (i18n) do campo 'description' para apps multilíngues

================================================================================
✅ STATUS: APROVADO PARA MVP
================================================================================
"""