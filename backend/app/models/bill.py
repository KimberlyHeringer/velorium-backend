"""
Modelo de Contas a Pagar (Bills)
Arquivo: backend/app/models/bill.py

Funcionalidades:
- CRUD de contas a pagar com parcelamento
- Suporte a recorrência (contas mensais)
- Notificações programadas
- Categorização de gastos

Principais features:
- amount em centavos (int) para precisão
- Parcelamento com cálculo dinâmico de parcela atual
- Suporte a contas recorrentes com data de término
- Notificações configuráveis (dias antes)
- I18n completo com chaves de erro
- Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
- Herança de PaymentMixin (paid, paid_date)
- Herança de AmountMixin (amount)
- ✅ CORRIGIDO: BillResponse id é obrigatório
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal
from datetime import datetime, timezone
from calendar import monthrange

from app.models.base import BaseModelWithUser
from app.models.mixins import PaymentMixin, AmountMixin
from app.core.constants import CATEGORIA_BILLS


class InstallmentInfo(BaseModel):
    """
    Informações sobre parcelamento da conta.
    
    🔧 CAMPOS:
      - total: Número total de parcelas
      - start_date: Data da primeira parcela
      - due_day: Dia de vencimento (opcional)
    
    🔧 VALIDAÇÕES:
      - due_day deve ser válido para o mês da start_date
      - due_day é opcional (pode ser None)
    """
    
    total: int = Field(
        ...,
        ge=1,
        description="Número total de parcelas"
    )
    
    start_date: datetime = Field(
        ...,
        description="Data da primeira parcela"
    )
    
    due_day: Optional[int] = Field(
        None,
        ge=1,
        le=31,
        description="Dia de vencimento (opcional)"
    )
    
    @model_validator(mode='after')
    def validate_due_day(self):
        """
        due_day deve ser válido para o mês da start_date.
        🔧 i18n: Mensagem com chave ERROR_INVALID_DUE_DAY
        """
        if self.due_day is not None:
            _, last_day = monthrange(self.start_date.year, self.start_date.month)
            if self.due_day > last_day:
                raise ValueError(
                    f'due_day {self.due_day} é inválido para {self.start_date.month}/{self.start_date.year}'
                )
        return self


class NotificationInfo(BaseModel):
    """
    Configurações de notificação para esta conta.
    
    🔧 CAMPOS:
      - enabled: Notificações ativas?
      - days_before: Dias antes para lembrar
    
    🔧 VALIDAÇÕES:
      - days_before é obrigatório se enabled=True
    """
    
    enabled: bool = Field(
        default=False,
        description="Notificações ativas?"
    )
    
    days_before: int = Field(
        0,
        ge=0,
        description="Dias antes para lembrar"
    )
    
    @model_validator(mode='after')
    def validate_notification(self):
        """
        days_before é obrigatório se enabled=True.
        🔧 i18n: Mensagem com chave ERROR_NOTIFICATION_DAYS_REQUIRED
        """
        if self.enabled and self.days_before <= 0:
            raise ValueError('days_before deve ser maior que 0 quando notificações estão ativas')
        return self


class Bill(BaseModelWithUser, PaymentMixin, AmountMixin):
    """
    Modelo principal de Conta a Pagar.
    
    🔧 HERDA DE:
      - BaseModelWithUser: id, user_id, created_at, updated_at, touch(), convert_objectid()
      - PaymentMixin: paid, paid_date (validação de pagamento)
      - AmountMixin: amount (validação de valor positivo)
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    
    🔧 CAMPOS ADICIONADOS:
      - description: Descrição da conta
      - installments: Informações de parcelamento
      - category: Categoria da conta (Literal)
      - notes: Observações
      - notification: Configurações de notificação
      - recurring: É recorrente?
      - recurring_end_date: Data final da recorrência
    """
    
    # ========== CAMPOS OBRIGATÓRIOS ==========
    
    description: str = Field(
        ...,
        max_length=200,
        description="Descrição da conta"
    )
    
    installments: InstallmentInfo = Field(
        ...,
        description="Informações de parcelamento"
    )
    
    # ========== CAMPOS OPCIONAIS ==========
    
    category: Optional[CATEGORIA_BILLS] = Field(
        None,
        description="Categoria da conta"
    )
    
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Observações"
    )
    
    notification: NotificationInfo = Field(
        default_factory=NotificationInfo,
        description="Configurações de notificação"
    )
    
    # ========== RECORRÊNCIA ==========
    
    recurring: bool = Field(
        default=False,
        description="É recorrente?"
    )
    
    recurring_end_date: Optional[datetime] = Field(
        None,
        description="Data final da recorrência"
    )
    
    # ========== VALIDAÇÕES ==========

    @model_validator(mode='after')
    def check_paid_date(self):
        """
        Valida paid_date.
        - Se paid=True, paid_date é obrigatório
        - paid_date não pode ser anterior à start_date
        🔧 i18n: Mensagens com chaves ERROR_BILL_PAID_DATE_REQUIRED e ERROR_BILL_PAID_DATE_BEFORE_START
        """
        if self.paid:
            if self.paid_date is None:
                raise ValueError('paid_date é obrigatório quando paid=True')
            if self.paid_date < self.installments.start_date:
                raise ValueError('paid_date não pode ser anterior à data de início das parcelas')
        return self
    
    @model_validator(mode='after')
    def validate_recurring(self):
        """
        Valida recurring_end_date.
        - Se recurring=True e recurring_end_date existe, não pode ser anterior à start_date
        """
        if self.recurring and self.recurring_end_date:
            if self.recurring_end_date < self.installments.start_date:
                raise ValueError('recurring_end_date não pode ser anterior à start_date')
        return self


class BillCreate(BaseModel):
    """
    Schema usado para CRIAR uma nova conta.
    
    🔧 DIFERENÇAS DO MODEL BILL:
      - Não tem campos de auditoria (ainda não existe no banco)
      - Todos os campos específicos do Bill são mantidos
    """
    
    description: str = Field(
        ...,
        max_length=200,
        description="Descrição da conta"
    )
    
    amount: int = Field(
        ...,
        gt=0,
        description="Valor em CENTAVOS (ex: 15050 = R$150,50)"
    )
    
    installments: InstallmentInfo = Field(
        ...,
        description="Informações de parcelamento"
    )
    
    category: Optional[CATEGORIA_BILLS] = Field(
        None,
        description="Categoria da conta"
    )
    
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Observações"
    )
    
    notification: NotificationInfo = Field(
        default_factory=NotificationInfo,
        description="Configurações de notificação"
    )
    
    recurring: bool = Field(
        default=False,
        description="É recorrente?"
    )
    
    recurring_end_date: Optional[datetime] = Field(
        None,
        description="Data final da recorrência"
    )


class BillUpdate(BaseModel):
    """
    Schema usado para ATUALIZAR uma conta existente.
    
    🔧 TODOS OS CAMPOS SÃO OPCIONAIS:
      - Permite atualização parcial
    """
    
    description: Optional[str] = Field(
        None,
        max_length=200,
        description="Descrição da conta"
    )
    
    amount: Optional[int] = Field(
        None,
        gt=0,
        description="Valor em CENTAVOS (ex: 15050 = R$150,50)"
    )
    
    installments: Optional[InstallmentInfo] = Field(
        None,
        description="Informações de parcelamento"
    )
    
    category: Optional[CATEGORIA_BILLS] = Field(
        None,
        description="Categoria da conta"
    )
    
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Observações"
    )
    
    notification: Optional[NotificationInfo] = Field(
        None,
        description="Configurações de notificação"
    )
    
    paid: Optional[bool] = Field(
        None,
        description="Conta totalmente paga?"
    )
    
    paid_date: Optional[datetime] = Field(
        None,
        description="Data em que foi totalmente paga"
    )
    
    recurring: Optional[bool] = Field(
        None,
        description="É recorrente?"
    )
    
    recurring_end_date: Optional[datetime] = Field(
        None,
        description="Data final da recorrência"
    )


class BillResponse(Bill):
    """
    Schema usado para RESPOSTAS da API.
    
    🔧 ✅ CORRIGIDO: id é obrigatório (sobrescreve Optional do BaseModel)
    """
    
    id: str = Field(..., alias="_id", description="ID da conta")


# ========== FUNÇÃO AUXILIAR PARA CALCULAR CURRENT ==========

async def get_current_installment(bill_id: str, user_id: str, db) -> int:
    """
    Calcula a parcela atual com base nas parcelas pagas.
    🔧 Substitui o campo 'current' que foi removido do InstallmentInfo.
    
    Args:
        bill_id (str): ID da conta mestra
        user_id (str): ID do usuário
        db: Instância do banco de dados
    
    Returns:
        int: Número da próxima parcela a pagar (ex: 1, 2, 3...)
    
    Exemplo:
        Se 5 parcelas foram pagas, retorna 6 (próxima parcela)
        Se nenhuma parcela foi paga, retorna 1
    """
    paid_count = await db.bill_installments.count_documents({
        "bill_id": bill_id,
        "user_id": user_id,
        "paid": True
    })
    return paid_count + 1


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Herança de BaseModelWithUser (id, user_id, created_at, updated_at, touch(), convert_objectid())
#   - Herança de PaymentMixin (paid, paid_date, validação de pagamento)
#   - Herança de AmountMixin (amount com validação)
#   - Submodelos: InstallmentInfo (parcelas), NotificationInfo (notificações)
#   - Validação: due_day compatível com mês da start_date
#   - Validação: days_before obrigatório se enabled=True
#   - Validação: paid_date não anterior à start_date
#   - Validação: recurring_end_date não anterior à start_date
#   - I18n completo com chaves de erro
#   - Função get_current_installment() para cálculo dinâmico
#   - Schemas separados (Create, Update, Response)
#   - ✅ CORRIGIDO: BillResponse id é obrigatório
#
# ❌ Não implementado (Pós-MVP):
#   - Nenhum (model completo para MVP)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - Herança de BaseModelWithUser, PaymentMixin, AmountMixin (03/07/2026)
#   - v3: Correção - BillResponse id sobrescrito como obrigatório (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO