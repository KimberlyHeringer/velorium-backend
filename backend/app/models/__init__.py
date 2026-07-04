"""
Models do MongoDB
Arquivo: backend/app/models/__init__.py

Funcionalidades:
- Exporta todos os models do sistema
- Exporta classes base (BaseModelWithoutUser, BaseModelWithUser)
- Exporta mixins para reutilização
- Centraliza imports para facilitar o uso

Principais features:
- Importação simplificada (from app.models import User, Transaction)
- Exportação de base e mixins
- Facilita a manutenção e organização do código
"""

# ===== EXPORTAÇÃO DA BASE =====
from .base import BaseModelWithoutUser, BaseModelWithUser

# ===== EXPORTAÇÃO DOS MODELS EXISTENTES =====
from .user import User, UserCreate, UserUpdate, UserResponse, UserLogin, Token
from .transaction import (
    Transaction, 
    TransactionCreate, 
    TransactionUpdate, 
    TransactionResponse,
    TransactionBalance
)
from .profile import UserProfile, UserProfileCreate, UserProfileResponse
from .bill import Bill, BillCreate, BillUpdate, BillResponse, InstallmentInfo, NotificationInfo
from .bill_installment import BillInstallmentBase, BillInstallmentCreate, BillInstallmentResponse
from .credit_card import CreditCardBase, CreditCardCreate, CreditCardUpdate, CreditCardResponse
from .credit_card_purchase import (
    CreditCardPurchase,
    CreditCardPurchaseCreate,
    CreditCardPurchaseUpdate,
    CreditCardPurchaseResponse
)
from .credit_card_installment import CreditCardInstallment, CreditCardInstallmentResponse
from .goal import Goal, GoalCreate, GoalUpdate, GoalResponse
from .achievement import Achievement, AchievementCreate, AchievementUpdate, AchievementResponse
from .score_history import ScoreHistory, ScoreHistoryResponse
from .investment import Investment, InvestmentCreate, InvestmentUpdate, InvestmentResponse

# ===== EXPORTAÇÃO DOS MIXINS =====
from .mixins import (
    TimestampMixin,
    ObjectIdMixin,
    PaymentMixin,
    AmountMixin,
    DateMixin,
    AuditMixin
)

# ===== LISTA COMPLETA PARA EXPORTAÇÃO =====
__all__ = [
    # Base
    'BaseModelWithoutUser',
    'BaseModelWithUser',
    
    # Mixins
    'TimestampMixin',
    'ObjectIdMixin',
    'PaymentMixin',
    'AmountMixin',
    'DateMixin',
    'AuditMixin',
    
    # User
    'User',
    'UserCreate',
    'UserUpdate',
    'UserResponse',
    'UserLogin',
    'Token',
    
    # Transaction
    'Transaction',
    'TransactionCreate',
    'TransactionUpdate',
    'TransactionResponse',
    'TransactionBalance',
    
    # Profile
    'UserProfile',
    'UserProfileCreate',
    'UserProfileResponse',
    
    # Bill
    'Bill',
    'BillCreate',
    'BillUpdate',
    'BillResponse',
    'InstallmentInfo',
    'NotificationInfo',
    
    # Bill Installment
    'BillInstallmentBase',
    'BillInstallmentCreate',
    'BillInstallmentResponse',
    
    # Credit Card
    'CreditCardBase',
    'CreditCardCreate',
    'CreditCardUpdate',
    'CreditCardResponse',
    
    # Credit Card Purchase
    'CreditCardPurchase',
    'CreditCardPurchaseCreate',
    'CreditCardPurchaseUpdate',
    'CreditCardPurchaseResponse',
    
    # Credit Card Installment
    'CreditCardInstallment',
    'CreditCardInstallmentResponse',
    
    # Goal
    'Goal',
    'GoalCreate',
    'GoalUpdate',
    'GoalResponse',
    
    # Achievement
    'Achievement',
    'AchievementCreate',
    'AchievementUpdate',
    'AchievementResponse',
    
    # Score History
    'ScoreHistory',
    'ScoreHistoryResponse',
    
    # Investment
    'Investment',
    'InvestmentCreate',
    'InvestmentUpdate',
    'InvestmentResponse',
]


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Exportação de todos os models existentes
#   - Exportação de BaseModelWithoutUser e BaseModelWithUser
#   - Exportação de todos os mixins
#   - Importação centralizada para facilitar o uso
#
# ❌ Não implementado (Pós-MVP):
#   - Nenhum (arquivo de exportação)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#   - v2: Adicionado BaseModelWithoutUser (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO