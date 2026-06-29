"""
Modelo de Parcelas de Cartão de Crédito
Arquivo: backend/app/models/credit_card_installment.py

🔧 CORRIGIDO:
- amount agora é int (centavos) para consistência com to_cents()
- 🔧 NOVO: Validação de amount > 0 (já tem gt=0)
- 🔧 i18n: Mensagens de erro documentadas com chaves para referência
- 🔧 NOVO: Método touch() para atualizar updated_at
- 🔧 NOVO: model_validator para conversão de ObjectId (com verificação de instância)
- 🔧 NOVO: Índices documentados para performance
- 🔧 CORRIGIDO: convert_objectid com loop genérico e verificação de instância
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional, Any
from datetime import datetime, timezone
from bson import ObjectId


class CreditCardInstallment(BaseModel):
    """
    Modelo de uma parcela individual de uma compra no cartão de crédito.
    Cada compra parcelada gera N parcelas.
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    - As rotas devem usar to_cents() e from_cents()
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        # from_attributes=True  # ← Removido (mais seguro)
    )

    id: Optional[str] = Field(None, alias="_id")
    purchase_id: str = Field(..., description="ID da compra original")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    card_id: str = Field(..., description="ID do cartão usado")
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    due_date: datetime = Field(..., description="Data de vencimento da parcela")
    paid: bool = Field(default=False, description="Se já foi paga")
    paid_date: Optional[datetime] = Field(None, description="Data do pagamento")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def check_paid_date(self):
        """
        Se a parcela está marcada como paga (paid=True),
        o campo paid_date não pode ser None.
        
        🔧 i18n: Mensagem com chave ERROR_PAID_DATE_REQUIRED
        """
        if self.paid and self.paid_date is None:
            raise ValueError('paid_date é obrigatório quando paid=True')
        return self
    
    @model_validator(mode='after')
    def validate_paid_date_not_future(self):
        """
        Se a parcela está paga, a data de pagamento não pode ser no futuro.
        
        🔧 NOVO: Validação para evitar dados inconsistentes.
        🔧 i18n: Mensagem com chave ERROR_PAID_DATE_FUTURE
        """
        if self.paid and self.paid_date:
            if self.paid_date > datetime.now(timezone.utc):
                raise ValueError('paid_date não pode ser no futuro')
        return self
    
    @field_validator('due_date', mode='before')
    @classmethod
    def validate_due_date(cls, v: Any) -> Any:
        """
        Valida que due_date seja uma data válida.
        🔧 i18n: Mensagem com chave ERROR_INVALID_DUE_DATE
        """
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                # 🔧 OPCIONAL: Valida se o ano é razoável
                if dt.year < 1900:
                    raise ValueError('due_date inválida (ano anterior a 1900)')
                return dt
            except (ValueError, TypeError):
                raise ValueError('due_date inválida')
        return v

    # ========== MÉTODOS AUXILIARES ==========

    def touch(self) -> 'CreditCardInstallment':
        """
        🔧 NOVO: Atualiza o timestamp de modificação.
        Uso: installment.touch() antes de salvar no banco.
        """
        self.updated_at = datetime.now(timezone.utc)
        return self

    # ========== CONVERSÃO DE OBJECTID ==========

    @model_validator(mode='before')
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """
        🔧 CORRIGIDO: Converte ObjectId para string.
        🔧 CORRIGIDO: Ignora se já for uma instância do modelo.
        🔧 CORRIGIDO: Loop genérico para todos os campos.
        """
        # Ignora se já for uma instância do modelo
        if isinstance(data, CreditCardInstallment):
            return data
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, ObjectId):
                    data[key] = str(value)
        return data


class CreditCardInstallmentResponse(CreditCardInstallment):
    """
    Schema para respostas da API.
    Força que o campo id seja obrigatório (não opcional).
    """
    id: str = Field(..., description="ID único da parcela")


# ========== ÍNDICES RECOMENDADOS ==========
# 
# 🔧 ADICIONAR EM indexes.py:
# 
# ================================================================
# 9. PARCELAS DE CARTÃO DE CRÉDITO (CREDIT_CARD_INSTALLMENTS)
# ================================================================
# 
# # Índice por usuário e vencimento (para listagem de parcelas a pagar)
# await db.credit_card_installments.create_index([("user_id", 1), ("due_date", 1)])
# 
# # Índice por compra (para buscar parcelas de uma compra específica)
# await db.credit_card_installments.create_index([("purchase_id", 1)])
# 
# # Índice por cartão e vencimento (para faturas)
# await db.credit_card_installments.create_index([("card_id", 1), ("due_date", 1)])
# 
# # Índice composto para status + vencimento (filtrar parcelas pendentes)
# await db.credit_card_installments.create_index([("user_id", 1), ("paid", 1), ("due_date", 1)])
# 
# ================================================================


# ========== PROPRIEDADES CALCULADAS (PÓS-MVP) ==========
#
# @property
# def is_overdue(self) -> bool:
#     """Verifica se a parcela está vencida."""
#     if self.paid:
#         return False
#     return self.due_date < datetime.now(timezone.utc)
#
# @property
# def days_overdue(self) -> int:
#     """Calcula dias de atraso."""
#     if self.paid or not self.is_overdue:
#         return 0
#     return (datetime.now(timezone.utc) - self.due_date).days


# ========== VALIDAÇÃO DE OBJECT ID (PÓS-MVP - OPCIONAL) ==========
#
# @field_validator('user_id', 'purchase_id', 'card_id', mode='before')
# @classmethod
# def validate_object_id_fields(cls, v: Any) -> str:
#     """Valida se o campo é um ObjectId válido."""
#     if v is None:
#         raise ValueError('ID é obrigatório')
#     
#     if isinstance(v, ObjectId):
#         return str(v)
#     
#     v = str(v).strip()
#     if not v:
#         raise ValueError('ID é obrigatório')
#     
#     if len(v) != 24 or not all(c in '0123456789abcdefABCDEF' for c in v):
#         raise ValueError('ID inválido')
#     
#     return v


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. amount: float → int (centavos) - consistente com to_cents()
2. Removido round_amount (não necessário para int)
3. Adicionados descriptions em todos os Field()
4. 🔧 NOVO: Validação de paid_date não futuro
5. 🔧 NOVO: Validação de due_date com field_validator
6. 🔧 NOVO: Método touch() para updated_at
7. 🔧 NOVO: model_validator para conversão de ObjectId
8. 🔧 NOVO: Índices documentados para performance
9. 🔧 CORRIGIDO: convert_objectid com verificação de instância
10. 🔧 CORRIGIDO: convert_objectid com loop genérico
11. 🔧 i18n: Mensagens de erro documentadas com chaves para referência

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_PAID_DATE_REQUIRED → "paid_date é obrigatório quando paid=True"
   - ERROR_PAID_DATE_FUTURE → "paid_date não pode ser no futuro"
   - ERROR_INVALID_DUE_DATE → "due_date inválida"

⏳ PENDÊNCIAS PÓS-MVP:
================================================================================
1. Adicionar validação de due_date >= hoje (depende da regra de negócio)
2. Propriedades calculadas: is_overdue, days_overdue
3. Validação de ObjectId para campos de ID (user_id, purchase_id, card_id)
4. from_attributes=True (avaliar se necessário)

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int + i18n)
================================================================================
"""