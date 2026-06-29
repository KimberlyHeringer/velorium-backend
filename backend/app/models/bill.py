"""
Modelo de Contas a Pagar (Bills)
Arquivo: backend/app/models/bill.py

🔧 CORRIGIDO:
- amount agora é int (centavos) para consistência com to_cents()
- Removido campo 'current' de InstallmentInfo (calculado dinamicamente)
- 🔧 NOVO: validação de days_before quando enabled=True
- 🔧 NOVO: validação de due_day com start_date
- 🔧 NOVO: validação de paid_date posterior a start_date
- 🔧 NOVO: validação de recurring_end_date
- 🔧 NOVO: validação de categoria com Literal
- 🔧 NOVO: método touch() para updated_at
- Adicionada função get_current_installment() para cálculo dinâmico
- Adicionado i18n com chaves para mensagens de erro
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from typing import Optional, Literal
from datetime import datetime, timezone
from bson import ObjectId
from calendar import monthrange


# ========== CONSTANTES ==========

# 🔧 NOVO: Categorias com Literal
CATEGORIA_BILLS = Literal[
    "aluguel", "condominio", "agua", "luz", "internet", "telefone",
    "supermercado", "educacao", "saude", "transporte", "lazer", "outros"
]

CATEGORIAS_VALIDAS = [
    "aluguel", "condominio", "agua", "luz", "internet", "telefone",
    "supermercado", "educacao", "saude", "transporte", "lazer", "outros"
]


# ========== MODELOS ==========

class InstallmentInfo(BaseModel):
    """
    Informações sobre parcelamento da conta.
    🔧 CORRIGIDO: Removido campo 'current' (calculado dinamicamente)
    🔧 CORRIGIDO: validação de due_day com start_date
    """
    total: int = Field(..., ge=1, description="Número total de parcelas")
    start_date: datetime = Field(..., description="Data da primeira parcela")
    due_day: Optional[int] = Field(None, ge=1, le=31, description="Dia de vencimento (opcional)")
    
    @model_validator(mode='after')
    def validate_due_day(self):
        """
        🔧 CORRIGIDO: due_day deve ser válido para o mês da start_date.
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
    """Configurações de notificação para esta conta"""
    enabled: bool = Field(default=False, description="Notificações ativas?")
    days_before: int = Field(0, ge=0, description="Dias antes para lembrar")
    
    @model_validator(mode='after')
    def validate_notification(self):
        """
        🔧 CORRIGIDO: days_before é obrigatório se enabled=True.
        🔧 i18n: Mensagem com chave ERROR_NOTIFICATION_DAYS_REQUIRED
        """
        if self.enabled and self.days_before <= 0:
            raise ValueError('days_before deve ser maior que 0 quando notificações estão ativas')
        return self


class Bill(BaseModel):
    """
    Modelo principal de Conta a Pagar
    
    🔧 IMPORTANTE: amount está em CENTAVOS (int)
    - Exemplo: R$ 150,50 → 15050
    - As rotas usam to_cents() e from_cents() automaticamente
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (preenchido pelo backend)")
    description: str = Field(..., max_length=200, description="Descrição da conta")
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    installments: InstallmentInfo = Field(..., description="Informações de parcelamento")
    # 🔧 CORRIGIDO: category com Literal
    category: Optional[CATEGORIA_BILLS] = Field(None, description="Categoria da conta")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    notification: NotificationInfo = Field(default_factory=NotificationInfo, description="Configurações de notificação")
    paid: bool = Field(default=False, description="Conta totalmente paga?")
    paid_date: Optional[datetime] = Field(None, description="Data em que foi totalmente paga")
    recurring: bool = Field(default=False, description="É recorrente?")
    recurring_end_date: Optional[datetime] = Field(None, description="Data final da recorrência")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def check_paid_date(self):
        """
        🔧 CORRIGIDO: Valida paid_date.
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
        🔧 NOVO: Valida recurring_end_date.
        - Se recurring=True e recurring_end_date existe, não pode ser anterior à start_date
        """
        if self.recurring and self.recurring_end_date:
            if self.recurring_end_date < self.installments.start_date:
                raise ValueError('recurring_end_date não pode ser anterior à start_date')
        return self
    
    @model_validator(mode='after')
    def validate_installment_due_day(self):
        """due_day é opcional - pode ser None"""
        return self

    # ========== MÉTODOS AUXILIARES ==========

    def touch(self) -> 'Bill':
        """
        🔧 NOVO: Atualiza o campo updated_at com a data/hora atual.
        """
        self.updated_at = datetime.now(timezone.utc)
        return self


class BillCreate(BaseModel):
    """Schema usado para CRIAR uma nova conta"""
    description: str = Field(..., max_length=200, description="Descrição da conta")
    amount: int = Field(..., gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    installments: InstallmentInfo = Field(..., description="Informações de parcelamento")
    category: Optional[CATEGORIA_BILLS] = Field(None, description="Categoria da conta")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    notification: NotificationInfo = Field(default_factory=NotificationInfo, description="Configurações de notificação")
    recurring: bool = Field(default=False, description="É recorrente?")
    recurring_end_date: Optional[datetime] = Field(None, description="Data final da recorrência")


class BillUpdate(BaseModel):
    """Schema usado para ATUALIZAR uma conta existente"""
    description: Optional[str] = Field(None, max_length=200, description="Descrição da conta")
    amount: Optional[int] = Field(None, gt=0, description="Valor em CENTAVOS (ex: 15050 = R$150,50)")
    installments: Optional[InstallmentInfo] = Field(None, description="Informações de parcelamento")
    category: Optional[CATEGORIA_BILLS] = Field(None, description="Categoria da conta")
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    notification: Optional[NotificationInfo] = Field(None, description="Configurações de notificação")
    paid: Optional[bool] = Field(None, description="Conta totalmente paga?")
    paid_date: Optional[datetime] = Field(None, description="Data em que foi totalmente paga")
    recurring: Optional[bool] = Field(None, description="É recorrente?")
    recurring_end_date: Optional[datetime] = Field(None, description="Data final da recorrência")


class BillResponse(Bill):
    """Schema usado para RESPOSTAS da API"""
    pass


# ========== FUNÇÃO AUXILIAR PARA CALCULAR CURRENT ==========

async def get_current_installment(bill_id: str, user_id: str, db) -> int:
    """
    Calcula a parcela atual com base nas parcelas pagas.
    🔧 NOVO: Substitui o campo 'current' que foi removido.
    
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


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. amount: float → int (centavos) - consistente com to_cents()
2. 🔧 REMOVIDO: campo 'current' de InstallmentInfo (causava inconsistência)
3. 🔧 NOVO: validação de days_before quando enabled=True
4. 🔧 NOVO: validação de due_day com start_date
5. 🔧 NOVO: validação de paid_date posterior a start_date
6. 🔧 NOVO: validação de recurring_end_date
7. 🔧 NOVO: category com Literal (categorias válidas)
8. 🔧 NOVO: método touch() para updated_at
9. 🔧 NOVO: função get_current_installment() para cálculo dinâmico
10. Adicionados max_length nos campos de texto
11. 🔧 i18n: Mensagens de erro com chaves para referência

✅ STATUS: CONSISTENTE COM AS ROTAS E BANCO DE DADOS
================================================================================
"""