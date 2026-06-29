"""
Modelo de Compra Parcelada no Cartão de Crédito
Arquivo: backend/app/models/credit_card_purchase.py

🔧 CORRIGIDO: 
- total_amount agora é int (centavos)
- Adicionado committed_amount (controle de limite)
- Adicionado remaining_installments
- Limitado parcelas a 360 (30 anos)
- 🔧 NOVO: Validação de committed_amount
- 🔧 NOVO: Validação de consistência entre remaining_installments e fully_paid
- 🔧 CORRIGIDO: convert_objectid usa função importada
- 🔧 NOVO: Validação de first_due_date
- 🔧 NOVO: Método touch() para updated_at
- 🔧 NOVO: Método to_purchase_data() para sincronizar remaining_installments
- 🔧 i18n: Mensagens de erro documentadas com chaves para referência
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional, Any
from datetime import datetime, timezone
from bson import ObjectId

# 🔧 CORRIGIDO: Usa a função importada
from app.utils.validators import convert_objectid_to_str
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class CreditCardPurchase(BaseModel):
    """
    Representa uma compra parcelada no cartão de crédito.
    Uma compra gera N parcelas (CreditCardInstallment).
    
    🔧 IMPORTANTE: Valores estão em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        # from_attributes=True  # ← Removido (mais seguro)
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    card_id: str = Field(..., description="ID do cartão de crédito")
    description: str = Field(..., max_length=200, description="Descrição da compra")
    
    # 🔧 CORRIGIDO: float → int (centavos)
    total_amount: int = Field(..., gt=0, description="Valor total em CENTAVOS (ex: 15050 = R$150,50)")
    
    # 🔧 NOVO: Controle de limite do cartão
    committed_amount: int = Field(..., ge=0, description="Valor comprometido do limite em CENTAVOS")
    
    # Parcelamento
    installments: int = Field(..., ge=1, le=360, description="Número total de parcelas (máx 360 = 30 anos)")
    remaining_installments: int = Field(..., ge=0, description="Parcelas restantes a pagar")
    
    # Datas
    first_due_date: datetime = Field(..., description="Data da primeira parcela")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da compra")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    
    # Controle
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Status
    fully_paid: bool = Field(default=False, description="Compra totalmente quitada?")
    fully_paid_date: Optional[datetime] = Field(None, description="Data da última parcela paga")

    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def validate_remaining_installments(self):
        """
        Remaining installments não pode ser maior que total.
        🔧 i18n: Mensagem com chave ERROR_INVALID_REMAINING_INSTALLMENTS
        """
        if self.remaining_installments > self.installments:
            raise ValueError('remaining_installments não pode ser maior que installments')
        return self
    
    @model_validator(mode='after')
    def validate_fully_paid_consistency(self):
        """
        🔧 CORRIGIDO: Valida consistência entre remaining_installments e fully_paid.
        """
        if self.remaining_installments == 0 and not self.fully_paid:
            raise ValueError('fully_paid deve ser True quando remaining_installments = 0')
        
        if self.fully_paid and self.remaining_installments > 0:
            raise ValueError('fully_paid não pode ser True quando há parcelas restantes')
        
        return self
    
    @model_validator(mode='after')
    def validate_committed_amount(self):
        """
        🔧 CORRIGIDO: Valida que committed_amount seja compatível com total_amount.
        """
        if self.committed_amount < self.total_amount:
            # committed_amount pode ser menor se o limite não cobre todo o valor
            # Ajuste conforme regra de negócio
            logger.warning(f"committed_amount ({self.committed_amount}) < total_amount ({self.total_amount})")
        return self
    
    @model_validator(mode='after')
    def check_fully_paid(self):
        """
        Se fully_paid=True, fully_paid_date é obrigatório.
        🔧 i18n: Mensagem com chave ERROR_FULLY_PAID_DATE_REQUIRED
        """
        if self.fully_paid and self.fully_paid_date is None:
            raise ValueError('fully_paid_date é obrigatório quando fully_paid=True')
        return self
    
    @model_validator(mode='after')
    def validate_fully_paid_date_not_future(self):
        """
        Se fully_paid=True, fully_paid_date não pode ser no futuro.
        🔧 NOVO: Validação para evitar dados inconsistentes.
        """
        if self.fully_paid and self.fully_paid_date:
            if self.fully_paid_date > datetime.now(timezone.utc):
                raise ValueError('fully_paid_date não pode ser no futuro')
        return self

    # ========== VALIDAÇÃO DE CAMPOS ==========

    @field_validator('first_due_date', mode='before')
    @classmethod
    def validate_first_due_date(cls, v: Any) -> Any:
        """
        🔧 CORRIGIDO: Valida que first_due_date seja uma data válida.
        🔧 i18n: Mensagem com chave ERROR_INVALID_DUE_DATE
        """
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                # Valida se o ano é razoável
                if dt.year < 1900:
                    raise ValueError('first_due_date inválida (ano anterior a 1900)')
                return dt
            except (ValueError, TypeError):
                raise ValueError('first_due_date inválida')
        return v

    # ========== MÉTODOS AUXILIARES ==========

    def touch(self) -> 'CreditCardPurchase':
        """
        🔧 NOVO: Atualiza o timestamp de modificação.
        Uso: purchase.touch() antes de salvar no banco.
        """
        self.updated_at = datetime.now(timezone.utc)
        return self

    # ========== CONVERSÃO DE OBJECTID ==========

    @model_validator(mode='before')
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """
        🔧 CORRIGIDO: Converte ObjectId para string (usando função importada).
        """
        if isinstance(data, CreditCardPurchase):
            return data
        
        # 🔧 CORRIGIDO: Usa a função importada
        return convert_objectid_to_str(data)


class CreditCardPurchaseCreate(BaseModel):
    """Schema usado para CRIAR uma nova compra parcelada"""
    card_id: str = Field(..., description="ID do cartão de crédito")
    description: str = Field(..., max_length=200, description="Descrição da compra")
    total_amount: int = Field(..., gt=0, description="Valor total em CENTAVOS (ex: 15050 = R$150,50)")
    installments: int = Field(..., ge=1, le=360, description="Número de parcelas (máx 360 = 30 anos)")
    first_due_date: datetime = Field(..., description="Data da primeira parcela")
    category: Optional[str] = Field(None, max_length=50, description="Categoria da compra")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    
    # ========== MÉTODOS ==========
    
    def to_purchase_data(self) -> dict:
        """
        🔧 NOVO: Converte para dict com remaining_installments sincronizado.
        Garante que remaining_installments seja sempre igual a installments na criação.
        """
        data = self.model_dump()
        data["remaining_installments"] = data["installments"]
        data["fully_paid"] = False
        data["committed_amount"] = data["total_amount"]  # Compromete todo o valor
        data["created_at"] = datetime.now(timezone.utc)
        data["updated_at"] = datetime.now(timezone.utc)
        return data


class CreditCardPurchaseResponse(CreditCardPurchase):
    """Schema usado para RESPOSTAS da API"""
    pass


# ========== PROPRIEDADES CALCULADAS (PÓS-MVP) ==========
#
# @property
# def total_paid(self) -> int:
#     """Valor total já pago em centavos."""
#     if self.fully_paid:
#         return self.total_amount
#     # Calcula baseado nas parcelas pagas (pós-MVP)
#     return 0
#
# @property
# def progress_percentage(self) -> float:
#     """Percentual pago da compra."""
#     if self.total_amount == 0:
#         return 100.0
#     return (self.total_paid / self.total_amount) * 100
#
# @property
# def is_overdue(self) -> bool:
#     """Verifica se a compra tem parcelas vencidas."""
#     if self.fully_paid:
#         return False
#     # Verifica se há parcelas com due_date < hoje (pós-MVP)
#     return False


# ========== CATEGORIAS (PÓS-MVP) ==========
#
# CATEGORIAS_COMPRAS = [
#     "alimentacao", "transporte", "educacao", "saude", "lazer",
#     "vestuario", "eletronicos", "casa", "beleza", "outros"
# ]
#
# @field_validator('category', mode='before')
# @classmethod
# def validate_category(cls, v: Optional[str]) -> Optional[str]:
#     if v is None:
#         return None
#     v = v.strip()
#     if v and v not in CATEGORIAS_COMPRAS:
#         raise ValueError(f'Categoria inválida. Use uma de: {", ".join(CATEGORIAS_COMPRAS)}')
#     return v


# ========== PÓS-MVP: ATUALIZAR REMAINING_INSTALLMENTS ==========
#
# async def update_remaining_installments(purchase_id: str, db):
#     """Recalcula remaining_installments baseado nas parcelas pagas."""
#     paid_count = await db.credit_card_installments.count_documents({
#         "purchase_id": purchase_id,
#         "paid": True
#     })
#     total = await db.credit_card_purchases.find_one(
#         {"_id": ObjectId(purchase_id)},
#         {"installments": 1}
#     )
#     if total:
#         remaining = total["installments"] - paid_count
#         await db.credit_card_purchases.update_one(
#             {"_id": ObjectId(purchase_id)},
#             {"$set": {"remaining_installments": remaining}}
#         )


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. total_amount: float → int (centavos) - consistente com to_cents()
2. 🔧 NOVO: committed_amount (controle de limite do cartão)
3. 🔧 NOVO: remaining_installments (parcelas restantes)
4. 🔧 CORRIGIDO: installments le=999 → le=360 (30 anos)
5. 🔧 NOVO: Validação de committed_amount (com warning)
6. 🔧 NOVO: Validação de consistência entre remaining_installments e fully_paid
7. 🔧 CORRIGIDO: convert_objectid usa função importada
8. 🔧 NOVO: Validação de first_due_date
9. 🔧 NOVO: Método touch() para updated_at
10. 🔧 NOVO: Método to_purchase_data() para sincronizar remaining_installments
11. 🔧 i18n: Mensagens de erro documentadas com chaves para referência

📌 CHAVES I18N REFERENCIADAS:
   - ERROR_INVALID_REMAINING_INSTALLMENTS → "remaining_installments não pode ser maior que installments"
   - ERROR_FULLY_PAID_DATE_REQUIRED → "fully_paid_date é obrigatório quando fully_paid=True"
   - ERROR_FULLY_PAID_DATE_FUTURE → "fully_paid_date não pode ser no futuro"
   - ERROR_INVALID_DUE_DATE → "first_due_date inválida"

⏳ PENDÊNCIAS PÓS-MVP:
================================================================================
1. Validação de committed_amount com limite do cartão (requer rota)
2. Validação de category com lista de categorias permitidas
3. Propriedades calculadas: total_paid, progress_percentage, is_overdue
4. Função update_remaining_installments() para recalcular automaticamente
5. Adicionar campo interest_rate (para compras com juros)
6. Adicionar campo discount (para descontos à vista)

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int + i18n)
================================================================================
"""