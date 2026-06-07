"""
Modelo de Transações (Receitas e Despesas)
Arquivo: backend/app/models/transaction.py

🔧 CORRIGIDO:
- amount agora é int (centavos)
- payment_method agora é Literal com valores padronizados
- TransactionBalance com int (centavos)
- Removido round_amount (não necessário)
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Literal
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.validators import validate_date_not_future


class Transaction(BaseModel):
    """
    Modelo principal de Transação.
    Suporta receitas (income) e despesas (expense).
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")
    type: Literal["income", "expense"] = Field(..., description="Tipo: receita ou despesa")
    
    # 🔧 CORRIGIDO: float → int (centavos)
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    
    category: str = Field(..., max_length=50, description="Categoria da transação")
    description: Optional[str] = Field(None, max_length=200, description="Descrição opcional")
    date: datetime = Field(..., description="Data da transação")
    
    # 🔧 CORRIGIDO: Literal com valores padronizados
    payment_method: Optional[Literal["dinheiro", "cartao_credito", "cartao_debito", "pix", "transferencia", "boleto", "outros"]] = Field(
        None, description="Método de pagamento"
    )
    
    context: Literal["individual", "familia", "profissional"] = Field(
        default="individual", description="Contexto da transação"
    )
    family_id: Optional[str] = Field(None, description="ID da família (obrigatório se context='familia')")
    
    # ========== CAMPOS PARA CARTÃO DE CRÉDITO ==========
    card_id: Optional[str] = Field(None, description="ID do cartão usado (quando payment_method='cartao_credito')")
    installments: int = Field(default=1, ge=1, description="Número de parcelas (padrão 1)")
    first_due_date: Optional[datetime] = Field(None, description="Data da primeira parcela")
    
    # ========== METADADOS ==========
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def check_family_context(self):
        """Valida que se context for 'familia', family_id é obrigatório"""
        if self.context == "familia" and not self.family_id:
            raise ValueError("family_id é obrigatório quando context é 'familia'")
        return self

    @model_validator(mode='after')
    def validate_date(self):
        """Valida que a data não está no futuro"""
        if self.date:
            validate_date_not_future(self.date, "date")
        return self

    @model_validator(mode='after')
    def validate_credit_card_fields(self):
        """Valida campos de cartão de crédito quando payment_method é cartao_credito"""
        if self.payment_method == "cartao_credito" and self.type == "expense":
            if not self.card_id:
                raise ValueError("card_id é obrigatório quando payment_method é cartao_credito")
            if self.installments < 1:
                raise ValueError("installments deve ser maior que 0")
            if self.installments > 1 and not self.first_due_date:
                raise ValueError("first_due_date é obrigatório quando installments > 1")
        return self


class TransactionCreate(BaseModel):
    """Schema usado para CRIAR uma nova transação"""
    type: Literal["income", "expense"]
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS")
    category: str = Field(..., max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    date: Optional[datetime] = None
    payment_method: Optional[Literal["dinheiro", "cartao_credito", "cartao_debito", "pix", "transferencia", "boleto", "outros"]] = None
    context: Literal["individual", "familia", "profissional"] = "individual"
    family_id: Optional[str] = None
    card_id: Optional[str] = None
    installments: int = Field(default=1, ge=1)
    first_due_date: Optional[datetime] = None

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
        if self.payment_method == "cartao_credito" and self.type == "expense":
            if not self.card_id:
                raise ValueError("card_id é obrigatório quando payment_method é cartao_credito")
            if self.installments < 1:
                raise ValueError("installments deve ser maior que 0")
            if self.installments > 1 and not self.first_due_date:
                raise ValueError("first_due_date é obrigatório quando installments > 1")
        return self


class TransactionUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma transação existente"""
    type: Optional[Literal["income", "expense"]] = None
    amount: Optional[int] = Field(None, gt=0)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    date: Optional[datetime] = None
    payment_method: Optional[Literal["dinheiro", "cartao_credito", "cartao_debito", "pix", "transferencia", "boleto", "outros"]] = None
    context: Optional[Literal["individual", "familia", "profissional"]] = None
    family_id: Optional[str] = None
    card_id: Optional[str] = None
    installments: Optional[int] = Field(None, ge=1)
    first_due_date: Optional[datetime] = None

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
        if self.payment_method == "cartao_credito" and self.type == "expense":
            if not self.card_id:
                raise ValueError("card_id é obrigatório quando payment_method é cartao_credito")
            if self.installments is not None and self.installments < 1:
                raise ValueError("installments deve ser maior que 0")
            if self.installments is not None and self.installments > 1 and not self.first_due_date:
                raise ValueError("first_due_date é obrigatório quando installments > 1")
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
    amount: int  # 🔧 CORRIGIDO: int (centavos)
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
    # 🔧 CORRIGIDO: float → int (centavos)
    income: int = Field(..., description="Receitas em CENTAVOS")
    expense: int = Field(..., description="Despesas em CENTAVOS")
    balance: int = Field(..., description="Saldo em CENTAVOS")
    context: Optional[str] = None


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. amount: float → int (centavos)
2. payment_method: agora Literal com valores padronizados (dinheiro, cartao_credito, etc.)
3. TransactionBalance: income/expense/balance agora int (centavos)
4. Removido round_amount (não necessário para int)
5. Adicionados max_length em category e description
6. Adicionados descriptions em todos os Field()

⚠️ ATENÇÃO PARA O FRONTEND:
================================================================================
O frontend precisa enviar payment_method com os valores padronizados:
- "dinheiro" (antes "Dinheiro")
- "cartao_credito" (antes "Cartão de Crédito")
- "cartao_debito" (antes "Cartão de Débito")
- "pix" (antes "Pix")
- "transferencia" (antes "Transferência")
- "boleto" (antes "Boleto")
- "outros" (antes "Outros")

================================================================================
✅ STATUS: CONSISTENTE COM A ESTRATÉGIA DO PROJETO (centavos como int)
================================================================================
"""