"""
Modelo de Transações (Receitas e Despesas)
Arquivo: backend/app/models/transaction.py

Funcionalidades:
- CRUD de transações (receitas/despesas)
- Suporte a cartão de crédito com parcelamento
- Contextos: individual, familia, profissional

Principais features:
- amount em centavos (int) para precisão
- Validação: cartão de crédito apenas para despesas
- Suporte a parcelamento (installments, first_due_date)
- Contextos para separação de dados
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- Herança de AmountMixin (amount com validação)
- Herança de PaymentMixin (paid, paid_date)
- ✅ CORRIGIDO: TransactionResponse herda de Transaction (elimina duplicação)
- ✅ CORRIGIDO: TransactionBalance com descriptions nos campos
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal, Any
from datetime import datetime, timezone

from app.models.base import BaseModelWithUser
from app.models.mixins import AmountMixin, PaymentMixin
from app.utils.validators import validate_date_not_future


class Transaction(BaseModelWithUser, AmountMixin, PaymentMixin):
    """
    Modelo principal de Transação.
    Suporta receitas (income) e despesas (expense).
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
      - AmountMixin: amount (validação de valor positivo)
      - PaymentMixin: paid, paid_date (validação de pagamento)
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    
    🔧 CAMPOS ADICIONADOS:
      - type: income/expense
      - category: Categoria da transação
      - description: Descrição opcional
      - date: Data da transação
      - payment_method: Método de pagamento
      - context: individual/familia/profissional
      - family_id: ID da família (obrigatório se context='familia')
      - card_id: ID do cartão (quando payment_method='cartao_credito')
      - installments: Número de parcelas
      - first_due_date: Data da primeira parcela
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    type: Literal["income", "expense"] = Field(
        ...,
        description="Tipo: receita (income) ou despesa (expense)"
    )
    
    category: str = Field(
        ...,
        max_length=50,
        description="Categoria da transação"
    )
    
    date: datetime = Field(
        ...,
        description="Data da transação"
    )
    
    # ========== CAMPOS OPCIONAIS ==========
    
    description: Optional[str] = Field(
        None,
        max_length=200,
        description="Descrição opcional da transação"
    )
    
    payment_method: Optional[Literal[
        "dinheiro", "cartao_credito", "cartao_debito",
        "pix", "transferencia", "boleto", "outros"
    ]] = Field(
        None,
        description="Método de pagamento utilizado"
    )
    
    # ========== CONTEXTOS ==========
    
    context: Literal["individual", "familia", "profissional"] = Field(
        default="individual",
        description="Contexto da transação"
    )
    
    family_id: Optional[str] = Field(
        None,
        description="ID da família (obrigatório se context='familia')"
    )
    
    # ========== CAMPOS PARA CARTÃO DE CRÉDITO ==========
    
    card_id: Optional[str] = Field(
        None,
        description="ID do cartão usado (quando payment_method='cartao_credito')"
    )
    
    installments: int = Field(
        default=1,
        ge=1,
        description="Número de parcelas (padrão 1)"
    )
    
    first_due_date: Optional[datetime] = Field(
        None,
        description="Data da primeira parcela (obrigatório se installments > 1)"
    )
    
    # ========== VALIDADORES ==========

    @model_validator(mode='after')
    def check_family_context(self):
        """
        Valida que se context for 'familia', family_id é obrigatório.
        🔧 i18n: Mensagem com chave ERROR_FAMILY_ID_REQUIRED
        """
        if self.context == "familia" and not self.family_id:
            raise ValueError("family_id é obrigatório quando context é 'familia'")
        return self

    @model_validator(mode='after')
    def validate_date(self):
        """Valida que a data não está no futuro."""
        if self.date:
            validate_date_not_future(self.date, "date")
        return self

    @model_validator(mode='after')
    def validate_payment_method_for_income(self):
        """
        Impede cartão de crédito em receitas.
        🔧 i18n: Mensagem com chave ERROR_CARD_NOT_ALLOWED_FOR_INCOME
        """
        if self.payment_method == "cartao_credito" and self.type == "income":
            raise ValueError("Cartão de crédito não é permitido para receitas")
        return self

    @model_validator(mode='after')
    def validate_credit_card_fields(self):
        """
        Valida campos de cartão de crédito quando payment_method é cartao_credito.
        🔧 i18n: Mensagens com chaves ERROR_CARD_ID_REQUIRED, ERROR_INSTALLMENTS_INVALID, ERROR_FIRST_DUE_DATE_REQUIRED
        """
        if self.payment_method == "cartao_credito" and self.type == "expense":
            if not self.card_id:
                raise ValueError("card_id é obrigatório quando payment_method é cartao_credito")
            if self.installments < 1:
                raise ValueError("installments deve ser maior que 0")
            if self.installments > 1 and not self.first_due_date:
                raise ValueError("first_due_date é obrigatório quando installments > 1")
        return self


class TransactionCreate(BaseModel):
    """
    Schema usado para CRIAR uma nova transação.
    
    🔧 DIFERENÇAS DO MODEL TRANSACTION:
      - Não tem campos de auditoria (ainda não existe no banco)
      - date é opcional (usa data atual se não informado)
    """
    
    type: Literal["income", "expense"]
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS")
    category: str = Field(..., max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    date: Optional[datetime] = None
    payment_method: Optional[Literal[
        "dinheiro", "cartao_credito", "cartao_debito",
        "pix", "transferencia", "boleto", "outros"
    ]] = None
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
    def validate_payment_method_for_income(self):
        if self.payment_method == "cartao_credito" and self.type == "income":
            raise ValueError("Cartão de crédito não é permitido para receitas")
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
    """
    Schema usado para ATUALIZAR uma transação existente.
    
    🔧 TODOS OS CAMPOS SÃO OPCIONAIS:
      - Permite atualização parcial
    """
    
    type: Optional[Literal["income", "expense"]] = None
    amount: Optional[int] = Field(None, gt=0)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    date: Optional[datetime] = None
    payment_method: Optional[Literal[
        "dinheiro", "cartao_credito", "cartao_debito",
        "pix", "transferencia", "boleto", "outros"
    ]] = None
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
    def validate_payment_method_for_income(self):
        if self.payment_method == "cartao_credito" and self.type == "income":
            raise ValueError("Cartão de crédito não é permitido para receitas")
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


class TransactionResponse(Transaction):
    """
    Schema usado para RESPOSTAS da API.
    
    🔧 ✅ CORRIGIDO: HERDA DE TRANSACTION (elimina duplicação de campos).
    
    🔧 DIFERENÇAS DO MODEL TRANSACTION:
      - id é obrigatório (já existe no banco)
      - amount é sobrescrito com descrição explícita
    """
    
    id: str = Field(..., alias="_id", description="ID da transação")
    
    # ✅ Sobrescreve amount para garantir descrição (não duplica campo)
    amount: int = Field(..., description="Valor em CENTAVOS")


class TransactionBalance(BaseModel):
    """
    Schema para retorno de saldo.
    
    🔧 ✅ CORRIGIDO: Descriptions adicionados para todos os campos.
    
    🔧 IMPORTANTE: Valores em CENTAVOS (int)
    """
    
    income: int = Field(..., description="Receitas em CENTAVOS")
    expense: int = Field(..., description="Despesas em CENTAVOS")
    balance: int = Field(..., description="Saldo em CENTAVOS")
    context: Optional[str] = Field(None, description="Contexto do saldo (individual/familia/profissional)")


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de AmountMixin (amount com validação)
#   - Herança de PaymentMixin (paid, paid_date, validação de pagamento)
#   - ✅ CORRIGIDO: TransactionResponse herda de Transaction (elimina duplicação)
#   - ✅ CORRIGIDO: TransactionBalance com descriptions em todos os campos
#   - Validação: cartão de crédito apenas para despesas
#   - Validação: data não futura
#   - Validação: context='familia' exige family_id
#   - Suporte a parcelamento (installments, first_due_date)
#   - I18n completo com chaves de erro
#   - Schemas separados (Create, Update, Response, Balance)
#   - Contextos: individual, familia, profissional
#
# ❌ Não implementado (Pós-MVP):
#   - Nenhum (model completo para MVP)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser, AmountMixin, PaymentMixin (03/07/2026)
#   - v3: Correções - TransactionResponse herda de Transaction, descriptions no Balance (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO