"""
Modelo de Transações (Receitas e Despesas)
Arquivo: backend/app/models/transaction.py

🔧 MODIFICADO: Regra 2.12 - Integração com cartão de crédito
- Adicionados campos card_id, installments, first_due_date para despesas com cartão
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Literal
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import round_amount, validate_date_not_future


class Transaction(BaseModel):
    """
    Modelo principal de Transação.
    Suporta receitas (income) e despesas (expense).
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    type: Literal["income", "expense"]
    amount: float = Field(..., gt=0)
    category: str
    description: Optional[str] = None
    date: datetime
    payment_method: Optional[str] = None
    context: Literal["individual", "familia", "profissional"] = "individual"
    family_id: Optional[str] = None
    # 🔧 NOVOS CAMPOS PARA CARTÃO DE CRÉDITO (Regra 2.12)
    card_id: Optional[str] = Field(None, description="ID do cartão usado (quando payment_method = Cartão de Crédito)")
    installments: int = Field(1, ge=1, description="Número de parcelas (padrão 1)")
    first_due_date: Optional[datetime] = Field(None, description="Data da primeira parcela")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def check_family_context(self):
        """Valida que se context for 'familia', family_id é obrigatório"""
        if self.context == "familia" and not self.family_id:
            raise ValueError("family_id é obrigatório quando context é 'familia'")
        return self

    @model_validator(mode='after')
    def validate_date(self):
        """Valida que a data não está no futuro (opcional para MVP)"""
        if self.date:
            validate_date_not_future(self.date, "date")
        return self

    @model_validator(mode='after')
    def validate_credit_card_fields(self):
        """Valida campos de cartão de crédito quando payment_method é cartão"""
        if self.payment_method == "Cartão de Crédito" and self.type == "expense":
            if not self.card_id:
                raise ValueError("card_id é obrigatório quando payment_method é Cartão de Crédito")
            if self.installments < 1:
                raise ValueError("installments deve ser maior que 0")
            if self.installments > 1 and not self.first_due_date:
                raise ValueError("first_due_date é obrigatório quando installments > 1")
        return self

    @model_validator(mode='after')
    def round_amount_field(self):
        """Arredonda amount usando função centralizada"""
        if self.amount is not None:
            self.amount = round_amount(self.amount)
        return self


class TransactionCreate(BaseModel):
    """Schema usado para CRIAR uma nova transação"""
    type: Literal["income", "expense"]
    amount: float = Field(..., gt=0)
    category: str
    description: Optional[str] = None
    date: Optional[datetime] = None
    payment_method: Optional[str] = None
    context: Literal["individual", "familia", "profissional"] = "individual"
    family_id: Optional[str] = None
    # 🔧 NOVOS CAMPOS PARA CARTÃO DE CRÉDITO (Regra 2.12)
    card_id: Optional[str] = Field(None, description="ID do cartão usado (quando payment_method = Cartão de Crédito)")
    installments: int = Field(1, ge=1, description="Número de parcelas (padrão 1)")
    first_due_date: Optional[datetime] = Field(None, description="Data da primeira parcela")

    @model_validator(mode='after')
    def check_family_context(self):
        if self.context == "familia" and not self.family_id:
            raise ValueError("family_id é obrigatório quando context é 'familia'")
        return self

    @model_validator(mode='after')
    def validate_date(self):
        if self.date:
            validate_date_not_future(self.date, "date")
        return self

    @model_validator(mode='after')
    def validate_credit_card_fields(self):
        """Valida campos de cartão de crédito quando payment_method é cartão"""
        if self.payment_method == "Cartão de Crédito" and self.type == "expense":
            if not self.card_id:
                raise ValueError("card_id é obrigatório quando payment_method é Cartão de Crédito")
            if self.installments < 1:
                raise ValueError("installments deve ser maior que 0")
            if self.installments > 1 and not self.first_due_date:
                raise ValueError("first_due_date é obrigatório quando installments > 1")
        return self

    @model_validator(mode='after')
    def round_amount_field(self):
        if self.amount is not None:
            self.amount = round_amount(self.amount)
        return self


class TransactionUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma transação existente"""
    type: Optional[Literal["income", "expense"]] = None
    amount: Optional[float] = Field(None, gt=0)
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[datetime] = None
    payment_method: Optional[str] = None
    context: Optional[Literal["individual", "familia", "profissional"]] = None
    family_id: Optional[str] = None
    # 🔧 NOVOS CAMPOS PARA CARTÃO DE CRÉDITO (Regra 2.12)
    card_id: Optional[str] = Field(None, description="ID do cartão usado (quando payment_method = Cartão de Crédito)")
    installments: Optional[int] = Field(None, ge=1, description="Número de parcelas")
    first_due_date: Optional[datetime] = Field(None, description="Data da primeira parcela")

    @model_validator(mode='after')
    def check_family_context(self):
        if self.context == "familia" and self.family_id is None:
            raise ValueError("family_id é obrigatório quando context é 'familia'")
        return self

    @model_validator(mode='after')
    def validate_date(self):
        if self.date:
            validate_date_not_future(self.date, "date")
        return self

    @model_validator(mode='after')
    def validate_credit_card_fields(self):
        """Valida campos de cartão de crédito quando payment_method é cartão"""
        if self.payment_method == "Cartão de Crédito" and self.type == "expense":
            if not self.card_id:
                raise ValueError("card_id é obrigatório quando payment_method é Cartão de Crédito")
            if self.installments is not None and self.installments < 1:
                raise ValueError("installments deve ser maior que 0")
            if self.installments is not None and self.installments > 1 and not self.first_due_date:
                raise ValueError("first_due_date é obrigatório quando installments > 1")
        return self

    @model_validator(mode='after')
    def round_amount_field(self):
        if self.amount is not None:
            self.amount = round_amount(self.amount)
        return self


class TransactionResponse(BaseModel):
    """Schema usado para RESPOSTAS da API"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: str = Field(..., alias="_id")
    user_id: str
    type: str
    amount: float
    category: str
    description: Optional[str]
    date: datetime
    payment_method: Optional[str]
    context: str
    family_id: Optional[str]
    card_id: Optional[str] = None
    installments: int = 1
    first_due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TransactionBalance(BaseModel):
    """Schema para retorno de saldo"""
    income: float
    expense: float
    balance: float
    context: Optional[str] = None

# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Mantivemos float (não Decimal) por compatibilidade com MongoDB
# ✅ Adicionamos round(amount, 2) para evitar problemas de precisão
# ✅ Adicionamos validação context/family_id (obrigatório quando context="familia")
# ✅ Separação clara entre Create, Update, Response e Balance
#
# ⏳ Validação de data futura (date >= hoje): postergado (opcional para MVP)
# ⏳ updated_at automático: postergado (mantém atualização manual nas rotas)