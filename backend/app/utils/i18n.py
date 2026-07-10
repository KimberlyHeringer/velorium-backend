"""
Internacionalização (i18n) - Dicionário de Mensagens
Arquivo: backend/app/utils/i18n.py

Funcionalidade: Gerencia mensagens traduzidas para os idiomas suportados.
Idiomas: pt (português), en (inglês), es (espanhol), zh (chinês simplificado)

🔧 USO:
    from app.utils.i18n import get_message, get_language_from_request
    
    mensagem = get_message("ACHIEVEMENT_NOT_FOUND", "pt")
    
    # Ou com request automatico
    lang = get_language_from_request(request)
    mensagem = get_message("ACHIEVEMENT_NOT_FOUND", lang)

📋 ESTRUTURA:
    MESSAGES[idioma][chave] = "mensagem traduzida"
"""

from typing import Dict, Optional
from fastapi import Request


# ========== DICIONÁRIO DE MENSAGENS ==========

MESSAGES: Dict[str, Dict[str, str]] = {
    # ============================================================
    # PORTUGUÊS (pt)
    # ============================================================
    "pt": {
        # ---------- Sucesso ----------
        "SUCCESS_CREATED": "Criado com sucesso",
        "SUCCESS_UPDATED": "Atualizado com sucesso",
        "SUCCESS_DELETED": "Removido com sucesso",
        
        # ---------- Erros Comuns ----------
        "ERROR_NOT_FOUND": "Não encontrado",
        "ERROR_UNAUTHORIZED": "Não autorizado",
        "ERROR_FORBIDDEN": "Acesso negado",
        "ERROR_SERVER": "Erro interno do servidor",
        "ERROR_VALIDATION": "Dados inválidos",
        "ERROR_CONFLICT": "Conflito - recurso já existe",
        "ERROR_NO_DATA_TO_UPDATE": "Nenhum dado para atualizar",
        "ERROR_INVALID_DATE_RANGE": "A data inicial não pode ser maior que a data final",
        "ERROR_PAGINATION_FAILED": "Erro ao processar paginação: {error}",
        "ERROR_INVALID_ID": "{field_name} inválido",
        "ERROR_DATE_FUTURE": "não pode ser uma data futura",
        
        # ---------- Autenticação ----------
        "AUTH_INVALID_CREDENTIALS": "E-mail ou senha inválidos",
        "AUTH_EMAIL_ALREADY_EXISTS": "E-mail já cadastrado",
        "AUTH_WEAK_PASSWORD": "Senha muito fraca",
        "AUTH_INVALID_TOKEN": "Token inválido ou expirado",
        "AUTH_TOKEN_REFRESHED": "Token atualizado com sucesso",
        "AUTH_TOKEN_REVOKED": "Token revogado",
        "AUTH_USER_NOT_FOUND": "Usuário não encontrado",
        "AUTH_INVALID_REFRESH_TOKEN": "Refresh token inválido",
        "AUTH_TOKEN_EXPIRED": "Token expirado",
        
        # ---------- Conquistas (Achievements) ----------
        "ACHIEVEMENT_NOT_FOUND": "Conquista não encontrada",
        "ACHIEVEMENT_CREATED": "Conquista criada com sucesso",
        "ACHIEVEMENT_UPDATED": "Conquista atualizada com sucesso",
        "ACHIEVEMENT_DELETED": "Conquista removida com sucesso",
        "ACHIEVEMENT_ALREADY_EXISTS": "Esta conquista já foi registrada",
        "ACHIEVEMENT_SYNC_NONE": "Nenhuma nova conquista para sincronizar",
        "ACHIEVEMENT_SYNC_ONE": "1 conquista sincronizada com sucesso",
        "ACHIEVEMENT_SYNC_MULTIPLE": "{count} conquistas sincronizadas com sucesso",
        "ACHIEVEMENT_SYNC_BATCH_TOO_LARGE": "Número máximo de conquistas por sincronização é {MAX}. Envie em lotes menores.",
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "Tipo de conquista inválido",
        "ERROR_INVALID_MONTH": "Mês deve ser entre 1 e 12",
        "ERROR_INVALID_YEAR": "Ano deve ser entre 1900 e 2100",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "Descrição não pode estar vazia",
        
        # ---------- Contas a Pagar (Bills) ----------
        "BILL_NOT_FOUND": "Conta não encontrada",
        "BILL_NO_DATA_TO_UPDATE": "Nenhum dado para atualizar",
        "BILL_CREATED": "Conta criada com sucesso",
        "BILL_UPDATED": "Conta atualizada com sucesso",
        "BILL_DELETED": "Conta removida com sucesso",
        "BILL_ALREADY_PAID": "Conta já está paga",
        "BILL_PAYMENT_FAILED": "Erro ao processar pagamento",
        "ERROR_MAX_INSTALLMENTS_EXCEEDED": "Número máximo de parcelas é {MAX}",
        "ERROR_INVALID_INSTALLMENTS": "Número de parcelas inválido",
        "ERROR_TOTAL_LESS_THAN_PAID": "Total de parcelas não pode ser menor que o já pago",
        "ERROR_AMOUNT_INVALID": "Valor inválido. Deve ser maior que zero",
        "ERROR_START_DATE_PAST": "Data de início não pode ser no passado",
        "ERROR_INVALID_DUE_DAY": "Dia de vencimento inválido para o mês",
        "ERROR_CREATE_BILL_FAILED": "Erro interno ao criar conta",
        
        # ---------- Parcelas de Contas (Bill Installments) ----------
        "INSTALLMENT_NOT_FOUND": "Parcela não encontrada",
        "INSTALLMENT_ALREADY_PAID": "Esta parcela já está paga",
        "INSTALLMENT_NOT_PAID": "Esta parcela não está paga",
        "INSTALLMENT_PAID_SUCCESS": "Parcela paga com sucesso",
        "INSTALLMENTS_ALL_PAID": "Todas as parcelas foram pagas com sucesso",
        "INSTALLMENTS_ALREADY_PAID": "Todas as parcelas já estavam pagas",
        "INSTALLMENT_NOT_YET_DUE": "Esta parcela ainda não venceu",
        "INSTALLMENT_UNPAY_SUCCESS": "Pagamento desmarcado com sucesso",
        "INSTALLMENT_UNPAY_WINDOW_EXPIRED": "Não é possível desmarcar pagamentos com mais de 30 dias",
        "INSTALLMENT_UNPAY_SUCCESS_BUT_BILL_PAID": "Pagamento desmarcado com sucesso, mas a conta mestra permanece como paga. Verifique a consistência.",
        
        # ---------- Cartões de Crédito ----------
        "ERROR_CARD_NOT_FOUND": "Cartão não encontrado",
        "ERROR_CARD_HAS_PURCHASES": "Cartão possui compras associadas. Remova as compras primeiro.",
        "SUCCESS_CARD_DELETED": "Cartão removido com sucesso",
        "ERROR_CANNOT_REDUCE_LIMIT": "Não é possível reduzir o limite abaixo do valor já utilizado (R$ {value:.2f})",
        "SUCCESS_LIMITS_RECALCULATED": "Limites recalculados com sucesso.",
        "CARD_LIMIT_EXCEEDED": "Limite do cartão excedido",
        "CARD_INVALID_CLOSING_DAY": "Dia de fechamento inválido",
        "CARD_INVALID_DUE_DAY": "Dia de vencimento inválido",
        "CARD_CREATED": "Cartão criado com sucesso",
        "CARD_UPDATED": "Cartão atualizado com sucesso",
        
        # ---------- Compras Parceladas (Credit Card Purchases) ----------
        "ERROR_PURCHASE_NOT_FOUND": "Compra não encontrada",
        "ERROR_INSUFFICIENT_LIMIT": "Limite insuficiente. Disponível: R$ {available:.2f}, Necessário: R$ {required:.2f}",
        "ERROR_CANNOT_EDIT_PAID_INSTALLMENTS": "Não é possível editar compra com parcelas já pagas",
        "SUCCESS_PURCHASE_DELETED": "Compra e parcelas excluídas com sucesso",
        "SUCCESS_INSTALLMENT_PAID": "Parcela marcada como paga e compromisso reduzido",
        "SUCCESS_INSTALLMENT_UNPAY": "Pagamento desmarcado com sucesso",
        "ERROR_FIRST_DUE_DATE_PAST": "A data da primeira parcela não pode ser no passado",
        "ERROR_INVALID_INTEREST_RATE": "Taxa de juros inválida. Deve ser entre 0% e 100%",
        
        # ---------- Metas (Goals) ----------
        "ERROR_GOAL_NOT_FOUND": "Meta não encontrada",
        "SUCCESS_GOAL_DELETED": "Meta deletada com sucesso",
        "GOAL_CREATED": "Meta criada com sucesso",
        "GOAL_UPDATED": "Meta atualizada com sucesso",
        "GOAL_COMPLETED": "Meta concluída! Parabéns!",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "Valor atual não pode ser maior que o valor alvo",
        
        # ---------- IA ----------
        "ERROR_USER_NOT_FOUND": "Usuário não encontrado.",
        "ERROR_TERMS_NOT_ACCEPTED": "Para usar o assistente, você precisa aceitar os Termos de Uso. Acesse Configurações > Consentimento.",
        "ERROR_IA_REQUEST_FAILED": "Não foi possível processar sua solicitação. Tente novamente mais tarde.",
        "SUCCESS_FEEDBACK_RECEIVED": "Feedback recebido com sucesso!",
        "ERROR_AUDIT_NOT_FOUND": "Interação não encontrada.",
        "IA_TIMEOUT": "IA demorou muito para responder",
        "ERROR_RESEARCH_CONSENT_REQUIRED": "Para enviar feedback, você precisa aceitar o consentimento de pesquisa. Acesse Configurações > Consentimento.",
        
        # ---------- IA Service ----------
        "IA_ERROR_GENERIC": "Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente mais tarde.",
        "IA_ERROR_TIMEOUT": "A resposta está demorando mais que o esperado. Tente novamente em alguns instantes.",
        "IA_OUT_OF_SCOPE": "Desculpe, só posso ajudar com perguntas sobre finanças pessoais. Posso ajudar com economia, investimentos ou planejamento financeiro?",
        "IA_CACHE_HIT": "Usando resposta em cache",
        
        # ---------- Score ----------
        "SCORE_CALCULATED": "Score calculado com sucesso",
        "SCORE_UPDATED": "Score atualizado com sucesso",
        "SCORE_CACHE_HIT": "Score obtido do cache",
        "SCORE_CACHE_MISS": "Score não encontrado no cache, calculando...",
        "SCORE_CACHE_EXPIRED": "Cache expirado, recalculando...",
        "SCORE_CACHE_SAVED": "Score salvo no cache",
        "SCORE_CACHE_INVALIDATED": "Cache de score invalidado",
        "SCORE_CACHE_ERROR": "Erro ao acessar cache do score",
        "SCORE_VARIATION_LIMITED": "Variação limitada a ±5 pontos",
        "SCORE_NO_USER": "Usuário não encontrado",
        "SCORE_GOALS_ERROR": "Erro ao buscar metas",
        "SCORE_CALCULATION_STARTED": "Iniciando cálculo de score",
        
        # ---------- Score Ranges (para anonimizer) ----------
        "SCORE_RANGE_0_20": "0-20",
        "SCORE_RANGE_20_40": "20-40",
        "SCORE_RANGE_40_60": "40-60",
        "SCORE_RANGE_60_80": "60-80",
        "SCORE_RANGE_80_100": "80-100",
        
        # ---------- Expense Ranges (para anonimizer) ----------
        "EXPENSE_RANGE_0_100": "0-100",
        "EXPENSE_RANGE_100_500": "100-500",
        "EXPENSE_RANGE_500_1000": "500-1000",
        "EXPENSE_RANGE_1000_5000": "1000-5000",
        "EXPENSE_RANGE_5000_PLUS": "5000+",
        
        # ---------- Email ----------
        "EMAIL_RESET_SUBJECT": "Redefinição de Senha - Velorium",
        "EMAIL_DELETE_SUBJECT": "Confirmação de Exclusão de Conta - Velorium",
        "EMAIL_TEST_SUBJECT": "Teste de Email - Velorium",
        
        # ---------- Audit ----------
        "AUDIT_COLLECTION_NONE": "Collection não pode ser None",
        "AUDIT_DOC_ID_EMPTY": "doc_id não pode ser vazio",
        "AUDIT_DOC_ID_INVALID": "doc_id inválido",
        "AUDIT_USER_ID_EMPTY": "user_id não pode ser vazio",
        "AUDIT_USER_ID_INVALID": "user_id inválido",
        "AUDIT_DB_NONE": "db não pode ser None",
        "AUDIT_ERROR_SAVING": "Erro ao salvar auditoria",
        
        # ---------- Transações ----------
        "ERROR_TRANSACTION_NOT_FOUND": "Transação não encontrada.",
        "ERROR_CREATE_TRANSACTION_FAILED": "Erro interno ao criar transação.",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "Não é possível deletar despesa com parcelas pagas no cartão.",
        "SUCCESS_TRANSACTION_DELETED": "Transação deletada com sucesso.",
        "SUCCESS_BULK_CATEGORIZED": "{count} transações recategorizadas com sucesso.",
        "SUCCESS_BALANCE_RECALCULATED": "Saldo recalculado com sucesso.",
        "ERROR_BULK_LIMIT_EXCEEDED": "Limite de 100 transações por requisição excedido.",
        "ERROR_INVALID_CATEGORY": "Categoria inválida. Use: {categories}",
        
        # ---------- Notificações ----------
        "SUCCESS_TOKEN_REGISTERED": "Token registrado com sucesso",
        "SUCCESS_NOTIFICATIONS_ENABLED": "Notificações ativadas",
        "SUCCESS_NOTIFICATIONS_DISABLED": "Notificações desativadas",
        "SUCCESS_TEST_NOTIFICATION_SENT": "Notificação de teste enviada",
        "ERROR_TEST_NOTIFICATION_FAILED": "Falha ao enviar notificação de teste",
        "ERROR_NO_PUSH_TOKEN": "Nenhum token de push registrado",
        "NOTIFICATION_DAILY_INSIGHT_TITLE": "💡 Veloria - Insight do Dia",
        "NOTIFICATION_DAILY_REMINDER_TITLE": "💜 Veloria - Atualização Diária",
        "NOTIFICATION_SENT": "Notificação enviada com sucesso",
        "NOTIFICATION_FAILED": "Falha ao enviar notificação",
        
        # ---------- Rate Limiting ----------
        "RATE_LIMIT_EXCEEDED": "Muitas requisições. Tente novamente mais tarde",
        
        # ---------- Perfil (Profile) ----------
        "ERROR_PROFILE_NOT_FOUND": "Perfil não encontrado para o usuário {user_id}",
        "ERROR_PROFILE_COLLECTION": "Erro ao criar/verificar coleção de perfis: {error}",
        "ERROR_PROFILE_CREATE_FAILED": "Erro ao criar perfil para o usuário {user_id}",
        "ERROR_PROFILE_UPDATE_FAILED": "Erro ao atualizar perfil do usuário {user_id}",
        "PROFILE_CACHE_HIT": "Perfil obtido do cache para {user_id}",
        "PROFILE_CACHE_MISS": "Perfil não encontrado no cache para {user_id}",
        "PROFILE_CACHE_SET": "Perfil armazenado em cache para {user_id}",
        "PROFILE_CACHE_INVALIDATED": "Cache de perfil invalidado para {user_id}",
        "SUCCESS_PROFILE_UPDATED": "Perfil atualizado com sucesso",
        "ERROR_INVALID_PROFILE_DATA": "Dados do perfil inválidos",
        
        # ---------- Investimentos ----------
        "ERROR_INVESTMENT_NOT_FOUND": "Investimento não encontrado",
        "ERROR_SOLD_VALUE_REQUIRED": "Valor de venda é obrigatório ao marcar como vendido",
        "ERROR_INVESTMENT_ALREADY_SOLD": "Investimento já foi vendido",
        "ERROR_CANNOT_UPDATE_SOLD_INVESTMENT": "Não é possível atualizar preço de investimento vendido",
        "ERROR_QUANTITY_NOT_DEFINED": "Investimento sem quantidade definida",
        "SUCCESS_INVESTMENT_DELETED": "Investimento removido com sucesso",
        "INVESTMENT_CREATED": "Investimento criado com sucesso",
        "INVESTMENT_UPDATED": "Investimento atualizado com sucesso",
        
        # ---------- Usuário ----------
        "ERROR_INVALID_CURRENT_PASSWORD": "Senha atual incorreta",
        "SUCCESS_PASSWORD_CHANGED": "Senha alterada com sucesso",
        "ERROR_INVALID_LANGUAGE": "Idioma inválido",
        "ERROR_INVALID_CURRENCY": "Moeda inválida",
        "SUCCESS_PREFERENCES_UPDATED": "Preferências atualizadas com sucesso",
        "ERROR_CANNOT_UNACCEPT_TERMS": "Os Termos de Uso não podem ser desmarcados depois de aceitos",
        "SUCCESS_CONSENT_UPDATED": "Consentimento atualizado com sucesso",
        "SUCCESS_DATA_EXPORTED": "Dados exportados com sucesso",
        "SUCCESS_ACCOUNT_DELETED": "Sua conta e todos os dados associados foram permanentemente removidos",
        "USER_UPDATED": "Usuário atualizado com sucesso",
        "USER_DELETED": "Usuário removido com sucesso",
        
        # ---------- Cache ----------
        "BALANCE_CACHE_HIT": "Saldo obtido do cache",
        "BALANCE_CACHE_SAVED": "Saldo salvo no cache",
        "BALANCE_CACHE_INVALIDATED": "Cache de saldo invalidado",
        "BALANCE_CACHE_ERROR": "Erro ao acessar cache de saldo",
        "BALANCE_CALCULATION_ERROR": "Erro ao calcular saldo",
        "REDIS_CONNECTION_ERROR": "Erro ao conectar Redis",
        "DB_NONE": "db não pode ser None",
        "USER_ID_EMPTY": "user_id não pode ser vazio",
        
        # ---------- Currency ----------
        "CURRENCY_TO_CENTS": "Conversão to_cents",
        "CURRENCY_FROM_CENTS": "Conversão from_cents",
        "CURRENCY_NEGATIVE_VALUE": "Valor não pode ser negativo",
        
        # ---------- Dates ----------
        "ERROR_DATE_PAST": "Data não pode ser no passado",
        "ERROR_DATE_FUTURE": "Data não pode ser no futuro",
        "ERROR_INVALID_DUE_DAY": "Dia de vencimento inválido",
        "ERROR_START_DATE_PAST": "Data de início não pode ser no passado",
        
        # ---------- Installments ----------
        "ERROR_INSTALLMENTS_PARTS_ZERO": "Número de parcelas deve ser maior que zero",
        "ERROR_INSTALLMENTS_TOTAL_ZERO": "Valor total deve ser maior que zero",
        "ERROR_INSTALLMENTS_INTEREST_NEGATIVE": "Taxa de juros não pode ser negativa",
        "ERROR_INSTALLMENTS_INTEREST_HIGH": "Taxa de juros não pode ser maior que 100%",
        
        # ---------- Notifications ----------
        "NOTIFICATION_EXPO_ERROR": "Erro no Expo",
        "NOTIFICATION_SEND_ERROR": "Erro ao enviar notificação",
        "NOTIFICATION_TIMEOUT": "Timeout ao enviar notificação",
        "NOTIFICATION_INVALID_TOKEN": "Token inválido",
        "NOTIFICATION_EMPTY_TOKEN": "Token vazio",
        "NOTIFICATION_EMPTY_TITLE": "Título vazio",
        "NOTIFICATION_EMPTY_BODY": "Corpo vazio",
        "NOTIFICATION_EMPTY_TOKEN_LIST": "Lista de tokens vazia",
        "NOTIFICATION_NO_VALID_TOKENS": "Nenhum token válido encontrado",
        "NOTIFICATION_BULK_ERROR": "Erro ao enviar notificações em lote",
        "NOTIFICATION_EXPO_URL_MISSING": "URL da API Expo não configurada",
        "NOTIFICATION_NO_TICKET": "Ticket não recebido para o token",
        
        # ---------- Scheduler ----------
        "SCHEDULER_WORKER_SCORE_LOADED": "✅ Worker de score carregado com sucesso",
        "SCHEDULER_WORKER_SCORE_NOT_AVAILABLE": "⚠️ Worker de score não disponível: {error}",
        "SCHEDULER_WORKER_SCORE_ERROR": "❌ Erro ao carregar worker de score: {error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_LOADED": "✅ Worker de notificações carregado com sucesso",
        "SCHEDULER_WORKER_NOTIFICATIONS_NOT_AVAILABLE": "⚠️ Worker de notificações não disponível: {error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_ERROR": "❌ Erro ao carregar worker de notificações: {error}",
        "SCHEDULER_ALREADY_INITIALIZED": "⚠️ Scheduler já foi inicializado",
        "SCHEDULER_DEV_MODE": "ℹ️ Ambiente de desenvolvimento detectado. Workers NÃO serão agendados.",
        "SCHEDULER_NO_WORKERS": "❌ Nenhum worker disponível. Scheduler não será iniciado.",
        "SCHEDULER_SCORE_SCHEDULED": "⏰ Worker de score agendado para 03:00",
        "SCHEDULER_SCORE_NOT_SCHEDULED": "⚠️ Worker de score NÃO agendado (não disponível)",
        "SCHEDULER_NOTIFICATIONS_SCHEDULED": "⏰ Worker de notificações agendado para 09:00",
        "SCHEDULER_NOTIFICATIONS_NOT_SCHEDULED": "⚠️ Worker de notificações NÃO agendado (não disponível)",
        "SCHEDULER_STARTED": "✅ Scheduler iniciado com sucesso!",
        "SCHEDULER_NO_JOBS": "⚠️ Nenhum worker agendado. Scheduler não foi iniciado.",
        "SCHEDULER_SHUTDOWN": "🛑 Scheduler desligado",
        "SCHEDULER_SHUTDOWN_ERROR": "❌ Erro ao desligar scheduler: {error}",

        # ---------- Score Cache ----------
        "SCORE_CACHE_REDIS_CONNECTED": "✅ Redis conectado com sucesso para cache de score",
        "SCORE_CACHE_REDIS_NOT_CONFIGURED": "ℹ️ Redis não configurado - usando MongoDB como cache",
        "SCORE_CACHE_REDIS_NOT_INSTALLED": "ℹ️ Redis não instalado - usando MongoDB como cache",
        "SCORE_CACHE_REDIS_ERROR": "❌ Erro ao conectar Redis: {error}",
        "SCORE_CACHE_USER_ID_INVALID": "❌ user_id inválido: {user_id}",
        "SCORE_CACHE_REDIS_HIT": "✅ Score obtido do Redis para usuário {user_id}",
        "SCORE_CACHE_REDIS_MISS": "ℹ️ Score não encontrado no Redis para {user_id}",
        "SCORE_CACHE_REDIS_GET_ERROR": "⚠️ Erro ao buscar score no Redis para {user_id}: {error}",
        "SCORE_CACHE_REDIS_SET": "💾 Score armazenado no Redis para {user_id} (TTL: {ttl}s)",
        "SCORE_CACHE_REDIS_SET_ERROR": "⚠️ Erro ao armazenar score no Redis para {user_id}: {error}",
        "SCORE_CACHE_REDIS_INVALIDATED": "🗑️ Cache Redis invalidado para usuário {user_id}",
        "SCORE_CACHE_REDIS_INVALIDATE_ERROR": "⚠️ Erro ao invalidar cache Redis para {user_id}: {error}",
        "SCORE_CACHE_REDIS_BATCH_INVALIDATED": "🗑️ Cache invalidado para {count} usuários ({errors} erros)",
        "SCORE_CACHE_MONGODB_HIT": "✅ Score obtido do MongoDB para usuário {user_id}",
        "SCORE_CACHE_MONGODB_MISS": "ℹ️ Score não encontrado no MongoDB para {user_id}",
        "SCORE_CACHE_MONGODB_GET_ERROR": "⚠️ Erro ao buscar score no MongoDB para {user_id}: {error}",
        "SCORE_CACHE_MONGODB_SET": "💾 Score armazenado no MongoDB para {user_id}",
        "SCORE_CACHE_MONGODB_SET_ERROR": "⚠️ Erro ao armazenar score no MongoDB para {user_id}: {error}",
        "SCORE_CACHE_FINAL_HIT": "✅ Score final obtido do cache para {user_id}",
        "SCORE_CACHE_FINAL_HIT_MONGODB": "✅ Score final obtido do MongoDB para {user_id}",
        "SCORE_CACHE_MISS_RECALCULATING": "🔄 Cache miss para usuário {user_id} - recalculando score...",
        "SCORE_CACHE_RECALCULATED": "✅ Score recalculado para usuário {user_id}",
        "SCORE_CACHE_DB_NONE": "❌ db não pode ser None para o usuário {user_id}",

        # ---------- User Tokens ----------
        "USER_TOKENS_USER_ID_INVALID": "❌ user_id inválido: {user_id}",
        "USER_TOKENS_TOKEN_INVALID": "❌ token inválido: {token}",
        "USER_TOKENS_DB_NONE": "❌ db não pode ser None",
        "USER_TOKENS_GENERATING": "🔄 Gerando token de exclusão para usuário {user_id}",
        "USER_TOKENS_GENERATED": "✅ Token gerado para usuário {user_id} (expira em {expiry_hours} horas)",
        "USER_TOKENS_GENERATE_ERROR": "❌ Erro ao gerar token para usuário {user_id}: {error}",
        "USER_TOKENS_VERIFYING": "🔍 Verificando token {token}",
        "USER_TOKENS_INVALID": "⚠️ Token inválido ou expirado: {token}",
        "USER_TOKENS_VERIFIED": "✅ Token verificado para usuário {user_id}",
        "USER_TOKENS_VERIFY_ERROR": "❌ Erro ao verificar token: {error}",
        "USER_TOKENS_MARKING_USED": "📝 Marcando token como usado: {token}",
        "USER_TOKENS_MARKED_USED": "✅ Token marcado como usado: {token}",
        "USER_TOKENS_NOT_FOUND": "⚠️ Token não encontrado: {token}",
        "USER_TOKENS_MARK_ERROR": "❌ Erro ao marcar token como usado: {error}",
        "USER_TOKENS_DELETED_EXPIRED": "🗑️ {count} tokens expirados removidos",
        "USER_TOKENS_DELETE_EXPIRED_ERROR": "❌ Erro ao remover tokens expirados: {error}",
        "USER_TOKENS_RATE_LIMIT": "⛔ Limite de geração de tokens excedido para usuário {user_id}. Aguarde 1 hora.",

        # ---------- Validações Extras (Validators) ----------
        "VALIDATION_INSTALLMENTS_NONE": "Número de parcelas não informado",
        "VALIDATION_INSTALLMENTS_ZERO": "Número de parcelas inválido: {installments}",
        "VALIDATION_INSTALLMENTS_MAX": "Número máximo de parcelas é {max}. Recebido: {installments}",
        "VALIDATION_INSTALLMENTS_OK": "✅ Parcelas válidas: {installments}",
        "VALIDATION_INSTALLMENTS_TYPE": "Número de parcelas deve ser um número inteiro. Recebido: {type}",
        "VALIDATION_AMOUNT_NONE": "Valor não informado",
        "VALIDATION_AMOUNT_ZERO": "Valor inválido: {amount}. Deve ser maior que zero",
        "VALIDATION_AMOUNT_OK": "✅ Valor válido: {amount}",
        "VALIDATION_AMOUNT_TYPE": "Valor deve ser um número inteiro. Recebido: {type}",
        "VALIDATION_INTEREST_RATE_NONE": "Taxa de juros não informada",
        "VALIDATION_INTEREST_RATE_INVALID": "Taxa de juros inválida: {rate}%. Deve ser entre 0% e 100%",
        "VALIDATION_INTEREST_RATE_OK": "✅ Taxa de juros válida: {rate}%",
        "VALIDATION_INTEREST_RATE_TYPE": "Taxa de juros deve ser um número. Recebido: {type}",
        "VALIDATION_QUANTITY_NONE": "Quantidade não informada",
        "VALIDATION_QUANTITY_ZERO": "Quantidade inválida: {quantity}. Deve ser maior que zero",
        "VALIDATION_QUANTITY_OK": "✅ Quantidade válida: {quantity}",
        "VALIDATION_QUANTITY_TYPE": "Quantidade deve ser um número. Recebido: {type}",
        "VALIDATION_PRICE_NONE": "Preço não informado",
        "VALIDATION_PRICE_ZERO": "Preço inválido: {price}. Deve ser maior que zero",
        "VALIDATION_PRICE_OK": "✅ Preço válido: {price}",
        "VALIDATION_PRICE_TYPE": "Preço deve ser um número. Recebido: {type}",
        "VALIDATION_PASSWORD_NONE": "Senha não informada",
        "VALIDATION_PASSWORD_LENGTH": "A senha deve ter pelo menos 8 caracteres",
        "VALIDATION_PASSWORD_CRITERIA": "A senha deve conter pelo menos 3 dos seguintes: letra maiúscula, letra minúscula, número, caractere especial",
        "VALIDATION_PASSWORD_OK": "✅ Senha forte",
        "VALIDATION_PASSWORD_TYPE": "Senha deve ser uma string. Recebido: {type}",

        # ---------- Notifications Worker ----------
        "NOTIFICATION_TOKEN_FOUND": "✅ Token encontrado para usuário {user_id}",
        "NOTIFICATION_TOKEN_NOT_FOUND": "ℹ️ Nenhum token encontrado para usuário {user_id}",
        "NOTIFICATION_TOKEN_ERROR": "❌ Erro ao buscar token para usuário {user_id}: {error}",
        "NOTIFICATION_USER_DATA": "📊 Dados do usuário {user_id}: score={score}",
        "NOTIFICATION_USER_DATA_ERROR": "❌ Erro ao buscar dados do usuário {user_id}: {error}",
        "NOTIFICATION_IA_ERROR": "❌ Erro ao gerar mensagem IA: {error}",
        "NOTIFICATION_NO_TOKEN": "ℹ️ Usuário {user_id} não tem token de notificação",
        "NOTIFICATION_DAILY_TITLE": "🌅 Bom dia! Sua dose diária de finanças",
        "NOTIFICATION_SENT_SUCCESS": "✅ Notificação enviada para usuário {user_id} - Score: {score}",
        "NOTIFICATION_SENT_FAILED": "❌ Falha ao enviar notificação para usuário {user_id}",
        "NOTIFICATION_SEND_ERROR": "❌ Erro ao enviar notificação para usuário {user_id}: {error}",
        "NOTIFICATION_WORKER_START": "🚀 Iniciando worker de notificações proativas...",
        "NOTIFICATION_WORKER_USERS": "📊 Encontrados {total} usuários com notificações ativas",
        "NOTIFICATION_WORKER_USER_ERROR": "❌ Erro ao processar usuário {user_id}: {error}",
        "NOTIFICATION_WORKER_DONE": "✅ Worker concluído! {success}/{total} enviadas em {duration}s",
        "NOTIFICATION_WORKER_FATAL": "❌ Falha fatal no worker de notificações: {error}",
        "NOTIFICATION_FALLBACK_HIGH": "🏆 Excelente! Seu score está em {score}. Continue assim!",
        "NOTIFICATION_FALLBACK_MEDIUM": "📈 Bom trabalho! Seu score é {score}. Com pequenos ajustes, você chega lá!",
        "NOTIFICATION_FALLBACK_LOW": "💪 Você está no caminho! Score {score}. Foque em reduzir gastos.",
        "NOTIFICATION_FALLBACK_VERY_LOW": "🌟 Vamos começar? Seu score é {score}. Eu posso te ajudar a melhorar!",
        "NOTIFICATION_RETRY_ATTEMPT": "Tentativa {attempt} para {user_id}, aguardando {wait_time}s",
        "NOTIFICATION_RETRY_SUCCESS": "✅ Notificação enviada na tentativa {attempt} para {user_id}",
        "NOTIFICATION_RETRY_FAILED": "❌ Todas as {max_retries} tentativas falharam para {user_id}",
        "NOTIFICATION_QUEUE_ADDED": "📥 Usuário {user_id} adicionado à fila",
        "NOTIFICATION_QUEUE_PROCESSING": "🚀 Iniciando processamento da fila",
        "NOTIFICATION_QUEUE_DONE": "✅ Fila processada: {success}/{processed} enviadas",

        # ---------- Score Worker ----------
        "SCORE_WORKER_START": "🔄 Iniciando worker de score diário...",
        "SCORE_WORKER_NO_USERS": "ℹ️ Nenhum usuário encontrado para processar",
        "SCORE_WORKER_USERS": "📊 Encontrados {total} usuários para processar",
        "SCORE_WORKER_BATCH": "📦 Processando lote {current}/{total}",
        "SCORE_WORKER_DONE": "✅ Worker de score concluído! {success}/{total} usuários processados em {duration}s",
        "SCORE_WORKER_LOGGED": "📊 Execução registrada no banco",
        "SCORE_WORKER_LOG_ERROR": "⚠️ Não foi possível registrar log do worker: {error}",
        "SCORE_WORKER_USER_SUCCESS": "✅ Score calculado para {email}: {score}",
        "SCORE_WORKER_USER_ERROR": "❌ Erro ao calcular score para {email}: {error}",
        "SCORE_WORKER_FATAL": "❌ Falha fatal no worker de score: {error}",
        "SCORE_WORKER_DB_NONE": "❌ Falha na conexão com o banco de dados",
        "SCORE_WORKER_INCREMENTAL": "🔄 Processamento incremental (última execução: {last_run})",
        "SCORE_WORKER_ACTIVE_USERS": "📊 {count} usuários com atividade recente",
        "SCORE_WORKER_NO_ACTIVE_USERS": "ℹ️ Nenhum usuário com atividade recente",
        "SCORE_WORKER_TRIGGERED": "🚀 Worker de score iniciado manualmente",
        "WORKER_SCORE_STARTED": "🚀 Worker de score acionado manualmente por {user_id}",
        "WORKER_SCORE_DONE": "✅ Worker de score finalizado com status: {status}",
        "WORKER_IMPORT_ERROR": "❌ Erro ao importar worker de score: {error}",

        # ---------- Score Queue ----------
        "SCORE_QUEUE_ADDED": "📥 Usuário {user_id} adicionado à fila de score",
        "SCORE_QUEUE_ERROR": "⚠️ Erro ao adicionar à fila de score: {error}",
        "SCORE_QUEUE_PROCESSING": "🚀 Iniciando processamento da fila de score...",
        "SCORE_QUEUE_PROCESS_ERROR": "❌ Erro ao processar fila de score: {error}",
        "SCORE_QUEUE_DONE": "✅ Fila de score processada: {success}/{processed} com sucesso",
        "SCORE_QUEUE_WORKER_START": "🔄 Iniciando worker de fila de score (loop infinito)...",
        "SCORE_QUEUE_WORKER_ERROR": "❌ Erro no worker de fila de score: {error}",

        # ---------- Migrations ----------
        "MIGRATIONS_START": "🔄 Iniciando migrações de dados...",
        "MIGRATIONS_DONE": "✅ Migrações concluídas! {executed} executadas, {skipped} ignoradas",
        "MIGRATIONS_SKIPPED": "ℹ️ Migração {name} já executada, ignorando...",
        "MIGRATIONS_EXECUTING": "🔄 Executando migração {name}...",
        "MIGRATIONS_NO_USERS": "ℹ️ Nenhum usuário para migrar",
        "MIGRATIONS_USERS_UPDATED": "✅ {total} usuários atualizados",
        "MIGRATIONS_EXECUTED": "✅ Migração {name} concluída",
        "MIGRATIONS_ERROR": "❌ Erro na migração {name}: {error}",
        "MIGRATIONS_DB_NONE": "❌ db não pode ser None",
        "MIGRATIONS_BATCH": "📦 Processados {processed} usuários...",

        # ---------- Categories ----------
        "CATEGORY_ALIMENTACAO": "Alimentação",
        "CATEGORY_TRANSPORTE": "Transporte",
        "CATEGORY_MORADIA": "Moradia",
        "CATEGORY_LAZER": "Lazer",
        "CATEGORY_SAUDE": "Saúde",
        "CATEGORY_EDUCACAO": "Educação",
        "CATEGORY_INVESTIMENTOS": "Investimentos",
        "CATEGORY_VESTUARIO": "Vestuário",
        "CATEGORY_BELEZA": "Beleza",
        "CATEGORY_ELETRONICOS": "Eletrônicos",
        "CATEGORY_CASA": "Casa",
        "CATEGORY_CARRO": "Carro",
        "CATEGORY_ECONOMIA": "Economia",
        "CATEGORY_VIAGEM": "Viagem",
        "CATEGORY_RENDA_FIXA": "Renda Fixa",
        "CATEGORY_ACOES": "Ações",
        "CATEGORY_FIIS": "FIIs",
        "CATEGORY_CRIPTO": "Cripto",
        "CATEGORY_OUTROS": "Outros",
        "CATEGORY_INVESTIMENTO": "Investimento",
        
        # ---------- 🆕 Categories Personalizadas ----------
        "CATEGORY_ALREADY_EXISTS": "Já existe uma categoria com este nome para o usuário.",
        "CATEGORY_NOT_FOUND": "Categoria não encontrada.",
        "CATEGORY_DELETED": "Categoria removida com sucesso.",
        "CATEGORY_INVALID_TYPE": "Tipo de categoria inválido. Use: expense, income, goal, investment ou bill.",
        "CATEGORY_NAME_REQUIRED": "O nome da categoria é obrigatório.",
        "CATEGORY_INVALID_COLOR": "Cor inválida. Use formato hexadecimal (#RRGGBB ou #RGB).",
    },

    # ============================================================
    # INGLÊS (en)
    # ============================================================
    "en": {
        # ---------- Success ----------
        "SUCCESS_CREATED": "Successfully created",
        "SUCCESS_UPDATED": "Successfully updated",
        "SUCCESS_DELETED": "Successfully deleted",
        
        # ---------- Common Errors ----------
        "ERROR_NOT_FOUND": "Not found",
        "ERROR_UNAUTHORIZED": "Unauthorized",
        "ERROR_FORBIDDEN": "Access denied",
        "ERROR_SERVER": "Internal server error",
        "ERROR_VALIDATION": "Invalid data",
        "ERROR_CONFLICT": "Conflict - resource already exists",
        "ERROR_NO_DATA_TO_UPDATE": "No data to update",
        "ERROR_INVALID_DATE_RANGE": "Start date cannot be greater than end date",
        "ERROR_PAGINATION_FAILED": "Pagination error: {error}",
        "ERROR_INVALID_ID": "Invalid {field_name}",
        "ERROR_DATE_FUTURE": "cannot be a future date",
        
        # ---------- Authentication ----------
        "AUTH_INVALID_CREDENTIALS": "Invalid email or password",
        "AUTH_EMAIL_ALREADY_EXISTS": "Email already registered",
        "AUTH_WEAK_PASSWORD": "Password is too weak",
        "AUTH_INVALID_TOKEN": "Invalid or expired token",
        "AUTH_TOKEN_REFRESHED": "Token refreshed successfully",
        "AUTH_TOKEN_REVOKED": "Token revoked",
        "AUTH_USER_NOT_FOUND": "User not found",
        "AUTH_INVALID_REFRESH_TOKEN": "Invalid refresh token",
        "AUTH_TOKEN_EXPIRED": "Token expired",
        
        # ---------- Achievements ----------
        "ACHIEVEMENT_NOT_FOUND": "Achievement not found",
        "ACHIEVEMENT_CREATED": "Achievement created successfully",
        "ACHIEVEMENT_UPDATED": "Achievement updated successfully",
        "ACHIEVEMENT_DELETED": "Achievement deleted successfully",
        "ACHIEVEMENT_ALREADY_EXISTS": "This achievement has already been recorded",
        "ACHIEVEMENT_SYNC_NONE": "No new achievements to sync",
        "ACHIEVEMENT_SYNC_ONE": "1 achievement synced successfully",
        "ACHIEVEMENT_SYNC_MULTIPLE": "{count} achievements synced successfully",
        "ACHIEVEMENT_SYNC_BATCH_TOO_LARGE": "Maximum number of achievements per sync is {MAX}. Please send in smaller batches.",
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "Invalid achievement type",
        "ERROR_INVALID_MONTH": "Month must be between 1 and 12",
        "ERROR_INVALID_YEAR": "Year must be between 1900 and 2100",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "Description cannot be empty",
        
        # ---------- Bills ----------
        "BILL_NOT_FOUND": "Bill not found",
        "BILL_NO_DATA_TO_UPDATE": "No data to update",
        "BILL_CREATED": "Bill created successfully",
        "BILL_UPDATED": "Bill updated successfully",
        "BILL_DELETED": "Bill deleted successfully",
        "BILL_ALREADY_PAID": "Bill is already paid",
        "BILL_PAYMENT_FAILED": "Failed to process payment",
        "ERROR_MAX_INSTALLMENTS_EXCEEDED": "Maximum number of installments is {MAX}",
        "ERROR_INVALID_INSTALLMENTS": "Invalid number of installments",
        "ERROR_TOTAL_LESS_THAN_PAID": "Total installments cannot be less than already paid",
        "ERROR_AMOUNT_INVALID": "Invalid amount. Must be greater than zero",
        "ERROR_START_DATE_PAST": "Start date cannot be in the past",
        "ERROR_INVALID_DUE_DAY": "Invalid due day for the month",
        "ERROR_CREATE_BILL_FAILED": "Internal error creating bill",
        
        # ---------- Bill Installments ----------
        "INSTALLMENT_NOT_FOUND": "Installment not found",
        "INSTALLMENT_ALREADY_PAID": "This installment is already paid",
        "INSTALLMENT_NOT_PAID": "This installment is not paid",
        "INSTALLMENT_PAID_SUCCESS": "Installment paid successfully",
        "INSTALLMENTS_ALL_PAID": "All installments have been paid successfully",
        "INSTALLMENTS_ALREADY_PAID": "All installments were already paid",
        "INSTALLMENT_NOT_YET_DUE": "This installment is not yet due",
        "INSTALLMENT_UNPAY_SUCCESS": "Payment successfully undone",
        "INSTALLMENT_UNPAY_WINDOW_EXPIRED": "Cannot unpay payments older than 30 days",
        "INSTALLMENT_UNPAY_SUCCESS_BUT_BILL_PAID": "Payment undone successfully, but the main bill remains as paid. Please check consistency.",
        
        # ---------- Credit Cards ----------
        "ERROR_CARD_NOT_FOUND": "Card not found",
        "ERROR_CARD_HAS_PURCHASES": "Card has associated purchases. Please remove purchases first.",
        "SUCCESS_CARD_DELETED": "Card deleted successfully",
        "ERROR_CANNOT_REDUCE_LIMIT": "Cannot reduce limit below already used amount (R$ {value:.2f})",
        "SUCCESS_LIMITS_RECALCULATED": "Limits recalculated successfully.",
        "CARD_LIMIT_EXCEEDED": "Card limit exceeded",
        "CARD_INVALID_CLOSING_DAY": "Invalid closing day",
        "CARD_INVALID_DUE_DAY": "Invalid due day",
        "CARD_CREATED": "Card created successfully",
        "CARD_UPDATED": "Card updated successfully",
        
        # ---------- Credit Card Purchases ----------
        "ERROR_PURCHASE_NOT_FOUND": "Purchase not found",
        "ERROR_INSUFFICIENT_LIMIT": "Insufficient limit. Available: R$ {available:.2f}, Required: R$ {required:.2f}",
        "ERROR_CANNOT_EDIT_PAID_INSTALLMENTS": "Cannot edit purchase with paid installments",
        "SUCCESS_PURCHASE_DELETED": "Purchase and installments deleted successfully",
        "SUCCESS_INSTALLMENT_PAID": "Installment marked as paid and commitment reduced",
        "SUCCESS_INSTALLMENT_UNPAY": "Payment successfully undone",
        "ERROR_FIRST_DUE_DATE_PAST": "First due date cannot be in the past",
        "ERROR_INVALID_INTEREST_RATE": "Invalid interest rate. Must be between 0% and 100%",
        
        # ---------- Goals ----------
        "ERROR_GOAL_NOT_FOUND": "Goal not found",
        "SUCCESS_GOAL_DELETED": "Goal deleted successfully",
        "GOAL_CREATED": "Goal created successfully",
        "GOAL_UPDATED": "Goal updated successfully",
        "GOAL_COMPLETED": "Goal completed! Congratulations!",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "Current value cannot exceed target value",
        
        # ---------- IA ----------
        "ERROR_USER_NOT_FOUND": "User not found.",
        "ERROR_TERMS_NOT_ACCEPTED": "To use the assistant, you need to accept the Terms of Use. Go to Settings > Consent.",
        "ERROR_IA_REQUEST_FAILED": "Unable to process your request. Please try again later.",
        "SUCCESS_FEEDBACK_RECEIVED": "Feedback received successfully!",
        "ERROR_AUDIT_NOT_FOUND": "Interaction not found.",
        "IA_TIMEOUT": "AI took too long to respond",
        "ERROR_RESEARCH_CONSENT_REQUIRED": "To send feedback, you need to accept the research consent. Go to Settings > Consent.",
        
        # ---------- IA Service ----------
        "IA_ERROR_GENERIC": "Sorry, an error occurred while processing your question. Please try again later.",
        "IA_ERROR_TIMEOUT": "The response is taking longer than expected. Please try again in a moment.",
        "IA_OUT_OF_SCOPE": "Sorry, I can only help with questions about personal finances. Can I help with savings, investments or financial planning?",
        "IA_CACHE_HIT": "Using cached response",
        
        # ---------- Score ----------
        "SCORE_CALCULATED": "Score calculated successfully",
        "SCORE_UPDATED": "Score updated successfully",
        "SCORE_CACHE_HIT": "Score retrieved from cache",
        "SCORE_CACHE_MISS": "Score not found in cache, calculating...",
        "SCORE_CACHE_EXPIRED": "Cache expired, recalculating...",
        "SCORE_CACHE_SAVED": "Score saved to cache",
        "SCORE_CACHE_INVALIDATED": "Score cache invalidated",
        "SCORE_CACHE_ERROR": "Error accessing score cache",
        "SCORE_VARIATION_LIMITED": "Variation limited to ±5 points",
        "SCORE_NO_USER": "User not found",
        "SCORE_GOALS_ERROR": "Error fetching goals",
        "SCORE_CALCULATION_STARTED": "Starting score calculation",
        
        # ---------- Score Ranges ----------
        "SCORE_RANGE_0_20": "0-20",
        "SCORE_RANGE_20_40": "20-40",
        "SCORE_RANGE_40_60": "40-60",
        "SCORE_RANGE_60_80": "60-80",
        "SCORE_RANGE_80_100": "80-100",
        
        # ---------- Expense Ranges ----------
        "EXPENSE_RANGE_0_100": "0-100",
        "EXPENSE_RANGE_100_500": "100-500",
        "EXPENSE_RANGE_500_1000": "500-1000",
        "EXPENSE_RANGE_1000_5000": "1000-5000",
        "EXPENSE_RANGE_5000_PLUS": "5000+",
        
        # ---------- Email ----------
        "EMAIL_RESET_SUBJECT": "Password Reset - Velorium",
        "EMAIL_DELETE_SUBJECT": "Delete Confirmation - Velorium",
        "EMAIL_TEST_SUBJECT": "Test Email - Velorium",
        
        # ---------- Audit ----------
        "AUDIT_COLLECTION_NONE": "Collection cannot be None",
        "AUDIT_DOC_ID_EMPTY": "doc_id cannot be empty",
        "AUDIT_DOC_ID_INVALID": "Invalid doc_id",
        "AUDIT_USER_ID_EMPTY": "user_id cannot be empty",
        "AUDIT_USER_ID_INVALID": "Invalid user_id",
        "AUDIT_DB_NONE": "db cannot be None",
        "AUDIT_ERROR_SAVING": "Error saving audit",
        
        # ---------- Transactions ----------
        "ERROR_TRANSACTION_NOT_FOUND": "Transaction not found.",
        "ERROR_CREATE_TRANSACTION_FAILED": "Internal error creating transaction.",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "Cannot delete expense with paid installments.",
        "SUCCESS_TRANSACTION_DELETED": "Transaction deleted successfully.",
        "SUCCESS_BULK_CATEGORIZED": "{count} transactions recategorized successfully.",
        "SUCCESS_BALANCE_RECALCULATED": "Balance recalculated successfully.",
        "ERROR_BULK_LIMIT_EXCEEDED": "Limit of 100 transactions per request exceeded.",
        "ERROR_INVALID_CATEGORY": "Invalid category. Use: {categories}",
        
        # ---------- Notifications ----------
        "SUCCESS_TOKEN_REGISTERED": "Token registered successfully",
        "SUCCESS_NOTIFICATIONS_ENABLED": "Notifications enabled",
        "SUCCESS_NOTIFICATIONS_DISABLED": "Notifications disabled",
        "SUCCESS_TEST_NOTIFICATION_SENT": "Test notification sent",
        "ERROR_TEST_NOTIFICATION_FAILED": "Failed to send test notification",
        "ERROR_NO_PUSH_TOKEN": "No push token registered",
        "NOTIFICATION_DAILY_INSIGHT_TITLE": "💡 Veloria - Daily Insight",
        "NOTIFICATION_DAILY_REMINDER_TITLE": "💜 Veloria - Daily Update",
        "NOTIFICATION_SENT": "Notification sent successfully",
        "NOTIFICATION_FAILED": "Failed to send notification",
        
        # ---------- Rate Limiting ----------
        "RATE_LIMIT_EXCEEDED": "Too many requests. Please try again later",
        
        # ---------- Profile ----------
        "ERROR_PROFILE_NOT_FOUND": "Profile not found for user {user_id}",
        "ERROR_PROFILE_COLLECTION": "Error creating/checking profiles collection: {error}",
        "ERROR_PROFILE_CREATE_FAILED": "Error creating profile for user {user_id}",
        "ERROR_PROFILE_UPDATE_FAILED": "Error updating profile for user {user_id}",
        "PROFILE_CACHE_HIT": "Profile cache hit for {user_id}",
        "PROFILE_CACHE_MISS": "Profile cache miss for {user_id}",
        "PROFILE_CACHE_SET": "Profile cached for {user_id}",
        "PROFILE_CACHE_INVALIDATED": "Profile cache invalidated for {user_id}",
        "SUCCESS_PROFILE_UPDATED": "Profile updated successfully",
        "ERROR_INVALID_PROFILE_DATA": "Invalid profile data",
        
        # ---------- Investments ----------
        "ERROR_INVESTMENT_NOT_FOUND": "Investment not found",
        "ERROR_SOLD_VALUE_REQUIRED": "Sold value is required when marking as sold",
        "ERROR_INVESTMENT_ALREADY_SOLD": "Investment has already been sold",
        "ERROR_CANNOT_UPDATE_SOLD_INVESTMENT": "Cannot update price of sold investment",
        "ERROR_QUANTITY_NOT_DEFINED": "Investment without quantity defined",
        "SUCCESS_INVESTMENT_DELETED": "Investment removed successfully",
        "INVESTMENT_CREATED": "Investment created successfully",
        "INVESTMENT_UPDATED": "Investment updated successfully",
        
        # ---------- User ----------
        "ERROR_INVALID_CURRENT_PASSWORD": "Current password is incorrect",
        "SUCCESS_PASSWORD_CHANGED": "Password changed successfully",
        "ERROR_INVALID_LANGUAGE": "Invalid language",
        "ERROR_INVALID_CURRENCY": "Invalid currency",
        "SUCCESS_PREFERENCES_UPDATED": "Preferences updated successfully",
        "ERROR_CANNOT_UNACCEPT_TERMS": "Terms of Use cannot be unchecked after being accepted",
        "SUCCESS_CONSENT_UPDATED": "Consent updated successfully",
        "SUCCESS_DATA_EXPORTED": "Data exported successfully",
        "SUCCESS_ACCOUNT_DELETED": "Your account and all associated data have been permanently removed",
        "USER_UPDATED": "User updated successfully",
        "USER_DELETED": "User deleted successfully",
        
        # ---------- Cache ----------
        "BALANCE_CACHE_HIT": "Balance retrieved from cache",
        "BALANCE_CACHE_SAVED": "Balance saved to cache",
        "BALANCE_CACHE_INVALIDATED": "Balance cache invalidated",
        "BALANCE_CACHE_ERROR": "Error accessing balance cache",
        "BALANCE_CALCULATION_ERROR": "Error calculating balance",
        "REDIS_CONNECTION_ERROR": "Redis connection error",
        "DB_NONE": "db cannot be None",
        "USER_ID_EMPTY": "user_id cannot be empty",
        
        # ---------- Currency ----------
        "CURRENCY_TO_CENTS": "Conversion to_cents",
        "CURRENCY_FROM_CENTS": "Conversion from_cents",
        "CURRENCY_NEGATIVE_VALUE": "Value cannot be negative",
        
        # ---------- Dates ----------
        "ERROR_DATE_PAST": "Date cannot be in the past",
        "ERROR_DATE_FUTURE": "Date cannot be in the future",
        "ERROR_INVALID_DUE_DAY": "Invalid due day",
        "ERROR_START_DATE_PAST": "Start date cannot be in the past",
        
        # ---------- Installments ----------
        "ERROR_INSTALLMENTS_PARTS_ZERO": "Number of installments must be greater than zero",
        "ERROR_INSTALLMENTS_TOTAL_ZERO": "Total value must be greater than zero",
        "ERROR_INSTALLMENTS_INTEREST_NEGATIVE": "Interest rate cannot be negative",
        "ERROR_INSTALLMENTS_INTEREST_HIGH": "Interest rate cannot be greater than 100%",
        
        # ---------- Notifications ----------
        "NOTIFICATION_EXPO_ERROR": "Expo error",
        "NOTIFICATION_SEND_ERROR": "Error sending notification",
        "NOTIFICATION_TIMEOUT": "Timeout sending notification",
        "NOTIFICATION_INVALID_TOKEN": "Invalid token",
        "NOTIFICATION_EMPTY_TOKEN": "Empty token",
        "NOTIFICATION_EMPTY_TITLE": "Empty title",
        "NOTIFICATION_EMPTY_BODY": "Empty body",
        "NOTIFICATION_EMPTY_TOKEN_LIST": "Empty token list",
        "NOTIFICATION_NO_VALID_TOKENS": "No valid tokens found",
        "NOTIFICATION_BULK_ERROR": "Error sending bulk notifications",
        "NOTIFICATION_EXPO_URL_MISSING": "Expo API URL not configured",
        "NOTIFICATION_NO_TICKET": "No ticket received for token",
        
        # ---------- Scheduler ----------
        "SCHEDULER_WORKER_SCORE_LOADED": "✅ Score worker loaded successfully",
        "SCHEDULER_WORKER_SCORE_NOT_AVAILABLE": "⚠️ Score worker not available: {error}",
        "SCHEDULER_WORKER_SCORE_ERROR": "❌ Error loading score worker: {error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_LOADED": "✅ Notifications worker loaded successfully",
        "SCHEDULER_WORKER_NOTIFICATIONS_NOT_AVAILABLE": "⚠️ Notifications worker not available: {error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_ERROR": "❌ Error loading notifications worker: {error}",
        "SCHEDULER_ALREADY_INITIALIZED": "⚠️ Scheduler already initialized",
        "SCHEDULER_DEV_MODE": "ℹ️ Development environment detected. Workers will NOT be scheduled.",
        "SCHEDULER_NO_WORKERS": "❌ No workers available. Scheduler will not start.",
        "SCHEDULER_SCORE_SCHEDULED": "⏰ Score worker scheduled for 03:00",
        "SCHEDULER_SCORE_NOT_SCHEDULED": "⚠️ Score worker NOT scheduled (not available)",
        "SCHEDULER_NOTIFICATIONS_SCHEDULED": "⏰ Notifications worker scheduled for 09:00",
        "SCHEDULER_NOTIFICATIONS_NOT_SCHEDULED": "⚠️ Notifications worker NOT scheduled (not available)",
        "SCHEDULER_STARTED": "✅ Scheduler started successfully!",
        "SCHEDULER_NO_JOBS": "⚠️ No workers scheduled. Scheduler not started.",
        "SCHEDULER_SHUTDOWN": "🛑 Scheduler shutdown",
        "SCHEDULER_SHUTDOWN_ERROR": "❌ Error shutting down scheduler: {error}",

        # ---------- Score Cache ----------
        "SCORE_CACHE_REDIS_CONNECTED": "✅ Redis connected successfully for score cache",
        "SCORE_CACHE_REDIS_NOT_CONFIGURED": "ℹ️ Redis not configured - using MongoDB as cache",
        "SCORE_CACHE_REDIS_NOT_INSTALLED": "ℹ️ Redis not installed - using MongoDB as cache",
        "SCORE_CACHE_REDIS_ERROR": "❌ Error connecting to Redis: {error}",
        "SCORE_CACHE_USER_ID_INVALID": "❌ Invalid user_id: {user_id}",
        "SCORE_CACHE_REDIS_HIT": "✅ Score retrieved from Redis for user {user_id}",
        "SCORE_CACHE_REDIS_MISS": "ℹ️ Score not found in Redis for {user_id}",
        "SCORE_CACHE_REDIS_GET_ERROR": "⚠️ Error fetching score from Redis for {user_id}: {error}",
        "SCORE_CACHE_REDIS_SET": "💾 Score stored in Redis for {user_id} (TTL: {ttl}s)",
        "SCORE_CACHE_REDIS_SET_ERROR": "⚠️ Error storing score in Redis for {user_id}: {error}",
        "SCORE_CACHE_REDIS_INVALIDATED": "🗑️ Redis cache invalidated for user {user_id}",
        "SCORE_CACHE_REDIS_INVALIDATE_ERROR": "⚠️ Error invalidating Redis cache for {user_id}: {error}",
        "SCORE_CACHE_REDIS_BATCH_INVALIDATED": "🗑️ Cache invalidated for {count} users ({errors} errors)",
        "SCORE_CACHE_MONGODB_HIT": "✅ Score retrieved from MongoDB for user {user_id}",
        "SCORE_CACHE_MONGODB_MISS": "ℹ️ Score not found in MongoDB for {user_id}",
        "SCORE_CACHE_MONGODB_GET_ERROR": "⚠️ Error fetching score from MongoDB for {user_id}: {error}",
        "SCORE_CACHE_MONGODB_SET": "💾 Score stored in MongoDB for {user_id}",
        "SCORE_CACHE_MONGODB_SET_ERROR": "⚠️ Error storing score in MongoDB for {user_id}: {error}",
        "SCORE_CACHE_FINAL_HIT": "✅ Final score retrieved from cache for {user_id}",
        "SCORE_CACHE_FINAL_HIT_MONGODB": "✅ Final score retrieved from MongoDB for {user_id}",
        "SCORE_CACHE_MISS_RECALCULATING": "🔄 Cache miss for user {user_id} - recalculating score...",
        "SCORE_CACHE_RECALCULATED": "✅ Score recalculated for user {user_id}",
        "SCORE_CACHE_DB_NONE": "❌ db cannot be None for user {user_id}",

        # ---------- User Tokens ----------
        "USER_TOKENS_USER_ID_INVALID": "❌ Invalid user_id: {user_id}",
        "USER_TOKENS_TOKEN_INVALID": "❌ Invalid token: {token}",
        "USER_TOKENS_DB_NONE": "❌ db cannot be None",
        "USER_TOKENS_GENERATING": "🔄 Generating deletion token for user {user_id}",
        "USER_TOKENS_GENERATED": "✅ Token generated for user {user_id} (expires in {expiry_hours} hours)",
        "USER_TOKENS_GENERATE_ERROR": "❌ Error generating token for user {user_id}: {error}",
        "USER_TOKENS_VERIFYING": "🔍 Verifying token {token}",
        "USER_TOKENS_INVALID": "⚠️ Invalid or expired token: {token}",
        "USER_TOKENS_VERIFIED": "✅ Token verified for user {user_id}",
        "USER_TOKENS_VERIFY_ERROR": "❌ Error verifying token: {error}",
        "USER_TOKENS_MARKING_USED": "📝 Marking token as used: {token}",
        "USER_TOKENS_MARKED_USED": "✅ Token marked as used: {token}",
        "USER_TOKENS_NOT_FOUND": "⚠️ Token not found: {token}",
        "USER_TOKENS_MARK_ERROR": "❌ Error marking token as used: {error}",
        "USER_TOKENS_DELETED_EXPIRED": "🗑️ {count} expired tokens removed",
        "USER_TOKENS_DELETE_EXPIRED_ERROR": "❌ Error removing expired tokens: {error}",
        "USER_TOKENS_RATE_LIMIT": "⛔ Token generation limit exceeded for user {user_id}. Please wait 1 hour.",

        # ---------- Validators Extras ----------
        "VALIDATION_INSTALLMENTS_NONE": "Installments not informed",
        "VALIDATION_INSTALLMENTS_ZERO": "Invalid installments: {installments}",
        "VALIDATION_INSTALLMENTS_MAX": "Maximum installments is {max}. Received: {installments}",
        "VALIDATION_INSTALLMENTS_OK": "✅ Valid installments: {installments}",
        "VALIDATION_INSTALLMENTS_TYPE": "Installments must be an integer. Received: {type}",
        "VALIDATION_AMOUNT_NONE": "Amount not informed",
        "VALIDATION_AMOUNT_ZERO": "Invalid amount: {amount}. Must be greater than zero",
        "VALIDATION_AMOUNT_OK": "✅ Valid amount: {amount}",
        "VALIDATION_AMOUNT_TYPE": "Amount must be an integer. Received: {type}",
        "VALIDATION_INTEREST_RATE_NONE": "Interest rate not informed",
        "VALIDATION_INTEREST_RATE_INVALID": "Invalid interest rate: {rate}%. Must be between 0% and 100%",
        "VALIDATION_INTEREST_RATE_OK": "✅ Valid interest rate: {rate}%",
        "VALIDATION_INTEREST_RATE_TYPE": "Interest rate must be a number. Received: {type}",
        "VALIDATION_QUANTITY_NONE": "Quantity not informed",
        "VALIDATION_QUANTITY_ZERO": "Invalid quantity: {quantity}. Must be greater than zero",
        "VALIDATION_QUANTITY_OK": "✅ Valid quantity: {quantity}",
        "VALIDATION_QUANTITY_TYPE": "Quantity must be a number. Received: {type}",
        "VALIDATION_PRICE_NONE": "Price not informed",
        "VALIDATION_PRICE_ZERO": "Invalid price: {price}. Must be greater than zero",
        "VALIDATION_PRICE_OK": "✅ Valid price: {price}",
        "VALIDATION_PRICE_TYPE": "Price must be a number. Received: {type}",
        "VALIDATION_PASSWORD_NONE": "Password not informed",
        "VALIDATION_PASSWORD_LENGTH": "Password must be at least 8 characters",
        "VALIDATION_PASSWORD_CRITERIA": "Password must contain at least 3 of the following: uppercase, lowercase, number, special character",
        "VALIDATION_PASSWORD_OK": "✅ Strong password",
        "VALIDATION_PASSWORD_TYPE": "Password must be a string. Received: {type}",

        # ---------- Notifications Worker ----------
        "NOTIFICATION_TOKEN_FOUND": "✅ Token found for user {user_id}",
        "NOTIFICATION_TOKEN_NOT_FOUND": "ℹ️ No token found for user {user_id}",
        "NOTIFICATION_TOKEN_ERROR": "❌ Error fetching token for user {user_id}: {error}",
        "NOTIFICATION_USER_DATA": "📊 User {user_id} data: score={score}",
        "NOTIFICATION_USER_DATA_ERROR": "❌ Error fetching user data for {user_id}: {error}",
        "NOTIFICATION_IA_ERROR": "❌ Error generating AI message: {error}",
        "NOTIFICATION_NO_TOKEN": "ℹ️ User {user_id} has no notification token",
        "NOTIFICATION_DAILY_TITLE": "🌅 Good morning! Your daily dose of finances",
        "NOTIFICATION_SENT_SUCCESS": "✅ Notification sent to user {user_id} - Score: {score}",
        "NOTIFICATION_SENT_FAILED": "❌ Failed to send notification to user {user_id}",
        "NOTIFICATION_SEND_ERROR": "❌ Error sending notification to user {user_id}: {error}",
        "NOTIFICATION_WORKER_START": "🚀 Starting proactive notifications worker...",
        "NOTIFICATION_WORKER_USERS": "📊 Found {total} users with active notifications",
        "NOTIFICATION_WORKER_USER_ERROR": "❌ Error processing user {user_id}: {error}",
        "NOTIFICATION_WORKER_DONE": "✅ Worker completed! {success}/{total} sent in {duration}s",
        "NOTIFICATION_WORKER_FATAL": "❌ Fatal error in notifications worker: {error}",
        "NOTIFICATION_FALLBACK_HIGH": "🏆 Excellent! Your score is {score}. Keep it up!",
        "NOTIFICATION_FALLBACK_MEDIUM": "📈 Good job! Your score is {score}. Small adjustments will get you there!",
        "NOTIFICATION_FALLBACK_LOW": "💪 You're on the right track! Score {score}. Focus on reducing expenses.",
        "NOTIFICATION_FALLBACK_VERY_LOW": "🌟 Let's get started? Your score is {score}. I can help you improve!",
        "NOTIFICATION_RETRY_ATTEMPT": "Attempt {attempt} for {user_id}, waiting {wait_time}s",
        "NOTIFICATION_RETRY_SUCCESS": "✅ Notification sent on attempt {attempt} for {user_id}",
        "NOTIFICATION_RETRY_FAILED": "❌ All {max_retries} attempts failed for {user_id}",
        "NOTIFICATION_QUEUE_ADDED": "📥 User {user_id} added to queue",
        "NOTIFICATION_QUEUE_PROCESSING": "🚀 Starting queue processing",
        "NOTIFICATION_QUEUE_DONE": "✅ Queue processed: {success}/{processed} sent",

        # ---------- Score Worker ----------
        "SCORE_WORKER_START": "🔄 Starting daily score worker...",
        "SCORE_WORKER_NO_USERS": "ℹ️ No users found to process",
        "SCORE_WORKER_USERS": "📊 Found {total} users to process",
        "SCORE_WORKER_BATCH": "📦 Processing batch {current}/{total}",
        "SCORE_WORKER_DONE": "✅ Score worker completed! {success}/{total} users processed in {duration}s",
        "SCORE_WORKER_LOGGED": "📊 Execution logged to database",
        "SCORE_WORKER_LOG_ERROR": "⚠️ Could not log worker execution: {error}",
        "SCORE_WORKER_USER_SUCCESS": "✅ Score calculated for {email}: {score}",
        "SCORE_WORKER_USER_ERROR": "❌ Error calculating score for {email}: {error}",
        "SCORE_WORKER_FATAL": "❌ Fatal error in score worker: {error}",
        "SCORE_WORKER_DB_NONE": "❌ Database connection failed",
        "SCORE_WORKER_INCREMENTAL": "🔄 Incremental processing (last run: {last_run})",
        "SCORE_WORKER_ACTIVE_USERS": "📊 {count} users with recent activity",
        "SCORE_WORKER_NO_ACTIVE_USERS": "ℹ️ No users with recent activity",
        "SCORE_WORKER_TRIGGERED": "🚀 Score worker manually triggered",
        "WORKER_SCORE_STARTED": "🚀 Score worker manually triggered by {user_id}",
        "WORKER_SCORE_DONE": "✅ Score worker finished with status: {status}",
        "WORKER_IMPORT_ERROR": "❌ Error importing score worker: {error}",

        # ---------- Score Queue ----------
        "SCORE_QUEUE_ADDED": "📥 User {user_id} added to score queue",
        "SCORE_QUEUE_ERROR": "⚠️ Error adding to score queue: {error}",
        "SCORE_QUEUE_PROCESSING": "🚀 Starting score queue processing...",
        "SCORE_QUEUE_PROCESS_ERROR": "❌ Error processing score queue: {error}",
        "SCORE_QUEUE_DONE": "✅ Score queue processed: {success}/{processed} successfully",
        "SCORE_QUEUE_WORKER_START": "🔄 Starting score queue worker (infinite loop)...",
        "SCORE_QUEUE_WORKER_ERROR": "❌ Error in score queue worker: {error}",

        # ---------- Migrations ----------
        "MIGRATIONS_START": "🔄 Starting data migrations...",
        "MIGRATIONS_DONE": "✅ Migrations completed! {executed} executed, {skipped} skipped",
        "MIGRATIONS_SKIPPED": "ℹ️ Migration {name} already executed, skipping...",
        "MIGRATIONS_EXECUTING": "🔄 Executing migration {name}...",
        "MIGRATIONS_NO_USERS": "ℹ️ No users to migrate",
        "MIGRATIONS_USERS_UPDATED": "✅ {total} users updated",
        "MIGRATIONS_EXECUTED": "✅ Migration {name} completed",
        "MIGRATIONS_ERROR": "❌ Error in migration {name}: {error}",
        "MIGRATIONS_DB_NONE": "❌ db cannot be None",
        "MIGRATIONS_BATCH": "📦 Processed {processed} users...",

        # ---------- Categories ----------
        "CATEGORY_ALIMENTACAO": "Food",
        "CATEGORY_TRANSPORTE": "Transport",
        "CATEGORY_MORADIA": "Housing",
        "CATEGORY_LAZER": "Leisure",
        "CATEGORY_SAUDE": "Health",
        "CATEGORY_EDUCACAO": "Education",
        "CATEGORY_INVESTIMENTOS": "Investments",
        "CATEGORY_VESTUARIO": "Clothing",
        "CATEGORY_BELEZA": "Beauty",
        "CATEGORY_ELETRONICOS": "Electronics",
        "CATEGORY_CASA": "Home",
        "CATEGORY_CARRO": "Car",
        "CATEGORY_ECONOMIA": "Savings",
        "CATEGORY_VIAGEM": "Travel",
        "CATEGORY_RENDA_FIXA": "Fixed Income",
        "CATEGORY_ACOES": "Stocks",
        "CATEGORY_FIIS": "REITs",
        "CATEGORY_CRIPTO": "Crypto",
        "CATEGORY_OUTROS": "Others",
        "CATEGORY_INVESTIMENTO": "Investment",
        
        # ---------- 🆕 Custom Categories ----------
        "CATEGORY_ALREADY_EXISTS": "A category with this name already exists for the user.",
        "CATEGORY_NOT_FOUND": "Category not found.",
        "CATEGORY_DELETED": "Category removed successfully.",
        "CATEGORY_INVALID_TYPE": "Invalid category type. Use: expense, income, goal, investment or bill.",
        "CATEGORY_NAME_REQUIRED": "Category name is required.",
        "CATEGORY_INVALID_COLOR": "Invalid color. Use hexadecimal format (#RRGGBB or #RGB).",
    },

    # ============================================================
    # ESPANHOL (es)
    # ============================================================
    "es": {
        # ---------- Éxito ----------
        "SUCCESS_CREATED": "Creado con éxito",
        "SUCCESS_UPDATED": "Actualizado con éxito",
        "SUCCESS_DELETED": "Eliminado con éxito",
        
        # ---------- Errores Comunes ----------
        "ERROR_NOT_FOUND": "No encontrado",
        "ERROR_UNAUTHORIZED": "No autorizado",
        "ERROR_FORBIDDEN": "Acceso denegado",
        "ERROR_SERVER": "Error interno del servidor",
        "ERROR_VALIDATION": "Datos inválidos",
        "ERROR_CONFLICT": "Conflicto - el recurso ya existe",
        "ERROR_NO_DATA_TO_UPDATE": "No hay datos para actualizar",
        "ERROR_INVALID_DATE_RANGE": "La fecha inicial no puede ser mayor que la fecha final",
        "ERROR_PAGINATION_FAILED": "Error de paginación: {error}",
        "ERROR_INVALID_ID": "{field_name} inválido",
        "ERROR_DATE_FUTURE": "no puede ser una fecha futura",
        
        # ---------- Autenticación ----------
        "AUTH_INVALID_CREDENTIALS": "Correo o contraseña inválidos",
        "AUTH_EMAIL_ALREADY_EXISTS": "El correo ya está registrado",
        "AUTH_WEAK_PASSWORD": "La contraseña es demasiado débil",
        "AUTH_INVALID_TOKEN": "Token inválido o expirado",
        "AUTH_TOKEN_REFRESHED": "Token actualizado con éxito",
        "AUTH_TOKEN_REVOKED": "Token revocado",
        "AUTH_USER_NOT_FOUND": "Usuario no encontrado",
        "AUTH_INVALID_REFRESH_TOKEN": "Refresh token inválido",
        "AUTH_TOKEN_EXPIRED": "Token expirado",
        
        # ---------- Logros ----------
        "ACHIEVEMENT_NOT_FOUND": "Logro no encontrado",
        "ACHIEVEMENT_CREATED": "Logro creado con éxito",
        "ACHIEVEMENT_UPDATED": "Logro actualizado con éxito",
        "ACHIEVEMENT_DELETED": "Logro eliminado con éxito",
        "ACHIEVEMENT_ALREADY_EXISTS": "Este logro ya ha sido registrado",
        "ACHIEVEMENT_SYNC_NONE": "No hay nuevos logros para sincronizar",
        "ACHIEVEMENT_SYNC_ONE": "1 logro sincronizado con éxito",
        "ACHIEVEMENT_SYNC_MULTIPLE": "{count} logros sincronizados con éxito",
        "ACHIEVEMENT_SYNC_BATCH_TOO_LARGE": "El número máximo de logros por sincronización es {MAX}. Envíe en lotes más pequeños.",
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "Tipo de logro inválido",
        "ERROR_INVALID_MONTH": "El mes debe estar entre 1 y 12",
        "ERROR_INVALID_YEAR": "El año debe estar entre 1900 y 2100",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "La descripción no puede estar vacía",
        
        # ---------- Cuentas ----------
        "BILL_NOT_FOUND": "Cuenta no encontrada",
        "BILL_NO_DATA_TO_UPDATE": "No hay datos para actualizar",
        "BILL_CREATED": "Cuenta creada con éxito",
        "BILL_UPDATED": "Cuenta actualizada con éxito",
        "BILL_DELETED": "Cuenta eliminada con éxito",
        "BILL_ALREADY_PAID": "La cuenta ya está pagada",
        "BILL_PAYMENT_FAILED": "Error al procesar el pago",
        "ERROR_MAX_INSTALLMENTS_EXCEEDED": "El número máximo de cuotas es {MAX}",
        "ERROR_INVALID_INSTALLMENTS": "Número de cuotas inválido",
        "ERROR_TOTAL_LESS_THAN_PAID": "El total de cuotas no puede ser menor que lo ya pagado",
        "ERROR_AMOUNT_INVALID": "Valor inválido. Debe ser mayor que cero",
        "ERROR_START_DATE_PAST": "La fecha de inicio no puede ser en el pasado",
        "ERROR_INVALID_DUE_DAY": "Día de vencimiento inválido para el mes",
        "ERROR_CREATE_BILL_FAILED": "Error interno al crear la cuenta",
        
        # ---------- Cuotas ----------
        "INSTALLMENT_NOT_FOUND": "Cuota no encontrada",
        "INSTALLMENT_ALREADY_PAID": "Esta cuota ya está pagada",
        "INSTALLMENT_NOT_PAID": "Esta cuota no está pagada",
        "INSTALLMENT_PAID_SUCCESS": "Cuota pagada con éxito",
        "INSTALLMENTS_ALL_PAID": "Todas las cuotas han sido pagadas con éxito",
        "INSTALLMENTS_ALREADY_PAID": "Todas las cuotas ya estaban pagadas",
        "INSTALLMENT_NOT_YET_DUE": "Esta cuota aún no vence",
        "INSTALLMENT_UNPAY_SUCCESS": "Pago desmarcado con éxito",
        "INSTALLMENT_UNPAY_WINDOW_EXPIRED": "No se pueden desmarcar pagos con más de 30 días",
        "INSTALLMENT_UNPAY_SUCCESS_BUT_BILL_PAID": "Pago desmarcado con éxito, pero la cuenta principal permanece como pagada. Verifique la consistencia.",
        
        # ---------- Tarjetas ----------
        "ERROR_CARD_NOT_FOUND": "Tarjeta no encontrada",
        "ERROR_CARD_HAS_PURCHASES": "La tarjeta tiene compras asociadas. Elimine las compras primero.",
        "SUCCESS_CARD_DELETED": "Tarjeta eliminada con éxito",
        "ERROR_CANNOT_REDUCE_LIMIT": "No se puede reducir el límite por debajo del valor ya utilizado (R$ {value:.2f})",
        "SUCCESS_LIMITS_RECALCULATED": "Límites recalculados con éxito.",
        "CARD_LIMIT_EXCEEDED": "Límite de tarjeta excedido",
        "CARD_INVALID_CLOSING_DAY": "Día de cierre inválido",
        "CARD_INVALID_DUE_DAY": "Día de vencimiento inválido",
        "CARD_CREATED": "Tarjeta creada con éxito",
        "CARD_UPDATED": "Tarjeta actualizada con éxito",
        
        # ---------- Compras ----------
        "ERROR_PURCHASE_NOT_FOUND": "Compra no encontrada",
        "ERROR_INSUFFICIENT_LIMIT": "Límite insuficiente. Disponible: R$ {available:.2f}, Necesario: R$ {required:.2f}",
        "ERROR_CANNOT_EDIT_PAID_INSTALLMENTS": "No se puede editar una compra con cuotas ya pagadas",
        "SUCCESS_PURCHASE_DELETED": "Compra y cuotas eliminadas con éxito",
        "SUCCESS_INSTALLMENT_PAID": "Cuota marcada como pagada y compromiso reducido",
        "SUCCESS_INSTALLMENT_UNPAY": "Pago desmarcado con éxito",
        "ERROR_FIRST_DUE_DATE_PAST": "La fecha de la primera cuota no puede ser en el pasado",
        "ERROR_INVALID_INTEREST_RATE": "Tasa de interés inválida. Debe ser entre 0% y 100%",
        
        # ---------- Metas ----------
        "ERROR_GOAL_NOT_FOUND": "Meta no encontrada",
        "SUCCESS_GOAL_DELETED": "Meta eliminada con éxito",
        "GOAL_CREATED": "Meta creada con éxito",
        "GOAL_UPDATED": "Meta actualizada con éxito",
        "GOAL_COMPLETED": "Meta completada! Felicitaciones",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "El valor actual no puede exceder el valor objetivo",
        
        # ---------- IA ----------
        "ERROR_USER_NOT_FOUND": "Usuario no encontrado.",
        "ERROR_TERMS_NOT_ACCEPTED": "Para usar el asistente, debe aceptar los Términos de Uso. Vaya a Configuración > Consentimiento.",
        "ERROR_IA_REQUEST_FAILED": "No se pudo procesar su solicitud. Intente más tarde.",
        "SUCCESS_FEEDBACK_RECEIVED": "¡Comentarios recibidos con éxito!",
        "ERROR_AUDIT_NOT_FOUND": "Interacción no encontrada.",
        "IA_TIMEOUT": "La IA tardó demasiado en responder",
        "ERROR_RESEARCH_CONSENT_REQUIRED": "Para enviar comentarios, debe aceptar el consentimiento de investigación. Vaya a Configuración > Consentimiento.",
        
        # ---------- IA Service ----------
        "IA_ERROR_GENERIC": "Lo sentimos, ocurrió un error al procesar tu pregunta. Por favor, intenta de nuevo más tarde.",
        "IA_ERROR_TIMEOUT": "La respuesta está tardando más de lo esperado. Intenta de nuevo en unos instantes.",
        "IA_OUT_OF_SCOPE": "Lo siento, solo puedo ayudar con preguntas sobre finanzas personales. ¿Puedo ayudar con ahorros, inversiones o planificación financiera?",
        "IA_CACHE_HIT": "Usando respuesta en caché",
        
        # ---------- Puntuación ----------
        "SCORE_CALCULATED": "Puntuación calculada con éxito",
        "SCORE_UPDATED": "Puntuación actualizada con éxito",
        "SCORE_CACHE_HIT": "Puntuación obtenida de caché",
        "SCORE_CACHE_MISS": "Puntuación no encontrada en caché, calculando...",
        "SCORE_CACHE_EXPIRED": "Caché expirado, recalculando...",
        "SCORE_CACHE_SAVED": "Puntuación guardada en caché",
        "SCORE_CACHE_INVALIDATED": "Caché de puntuación invalidado",
        "SCORE_CACHE_ERROR": "Error al acceder al caché de puntuación",
        "SCORE_VARIATION_LIMITED": "Variación limitada a ±5 puntos",
        "SCORE_NO_USER": "Usuario no encontrado",
        "SCORE_GOALS_ERROR": "Error al buscar metas",
        "SCORE_CALCULATION_STARTED": "Iniciando cálculo de puntuación",
        
        # ---------- Score Ranges ----------
        "SCORE_RANGE_0_20": "0-20",
        "SCORE_RANGE_20_40": "20-40",
        "SCORE_RANGE_40_60": "40-60",
        "SCORE_RANGE_60_80": "60-80",
        "SCORE_RANGE_80_100": "80-100",
        
        # ---------- Expense Ranges ----------
        "EXPENSE_RANGE_0_100": "0-100",
        "EXPENSE_RANGE_100_500": "100-500",
        "EXPENSE_RANGE_500_1000": "500-1000",
        "EXPENSE_RANGE_1000_5000": "1000-5000",
        "EXPENSE_RANGE_5000_PLUS": "5000+",
        
        # ---------- Email ----------
        "EMAIL_RESET_SUBJECT": "Restablecimiento de Contraseña - Velorium",
        "EMAIL_DELETE_SUBJECT": "Confirmación de Eliminación - Velorium",
        "EMAIL_TEST_SUBJECT": "Correo de Prueba - Velorium",
        
        # ---------- Audit ----------
        "AUDIT_COLLECTION_NONE": "La colección no puede ser None",
        "AUDIT_DOC_ID_EMPTY": "doc_id no puede estar vacío",
        "AUDIT_DOC_ID_INVALID": "doc_id inválido",
        "AUDIT_USER_ID_EMPTY": "user_id no puede estar vacío",
        "AUDIT_USER_ID_INVALID": "user_id inválido",
        "AUDIT_DB_NONE": "db no puede ser None",
        "AUDIT_ERROR_SAVING": "Error al guardar auditoría",
        
        # ---------- Transacciones ----------
        "ERROR_TRANSACTION_NOT_FOUND": "Transacción no encontrada.",
        "ERROR_CREATE_TRANSACTION_FAILED": "Error interno al crear la transacción.",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "No se puede eliminar un gasto con cuotas pagadas.",
        "SUCCESS_TRANSACTION_DELETED": "Transacción eliminada con éxito.",
        "SUCCESS_BULK_CATEGORIZED": "{count} transacciones recategorizadas con éxito.",
        "SUCCESS_BALANCE_RECALCULATED": "Saldo recalculado con éxito.",
        "ERROR_BULK_LIMIT_EXCEEDED": "Límite de 100 transacciones por solicitud excedido.",
        "ERROR_INVALID_CATEGORY": "Categoría inválida. Use: {categories}",
        
        # ---------- Notificaciones ----------
        "SUCCESS_TOKEN_REGISTERED": "Token registrado con éxito",
        "SUCCESS_NOTIFICATIONS_ENABLED": "Notificaciones activadas",
        "SUCCESS_NOTIFICATIONS_DISABLED": "Notificaciones desactivadas",
        "SUCCESS_TEST_NOTIFICATION_SENT": "Notificación de prueba enviada",
        "ERROR_TEST_NOTIFICATION_FAILED": "Error al enviar la notificación de prueba",
        "ERROR_NO_PUSH_TOKEN": "Ningún token de push registrado",
        "NOTIFICATION_DAILY_INSIGHT_TITLE": "💡 Veloria - Perspectiva del Día",
        "NOTIFICATION_DAILY_REMINDER_TITLE": "💜 Veloria - Actualización Diaria",
        "NOTIFICATION_SENT": "Notificación enviada con éxito",
        "NOTIFICATION_FAILED": "Error al enviar la notificación",
        
        # ---------- Rate Limiting ----------
        "RATE_LIMIT_EXCEEDED": "Demasiadas solicitudes. Intente más tarde",
        
        # ---------- Perfil ----------
        "ERROR_PROFILE_NOT_FOUND": "Perfil no encontrado para el usuario {user_id}",
        "ERROR_PROFILE_COLLECTION": "Error al crear/verificar la colección de perfiles: {error}",
        "ERROR_PROFILE_CREATE_FAILED": "Error al crear perfil para el usuario {user_id}",
        "ERROR_PROFILE_UPDATE_FAILED": "Error al actualizar perfil del usuario {user_id}",
        "PROFILE_CACHE_HIT": "Perfil obtenido de caché para {user_id}",
        "PROFILE_CACHE_MISS": "Perfil no encontrado en caché para {user_id}",
        "PROFILE_CACHE_SET": "Perfil almacenado en caché para {user_id}",
        "PROFILE_CACHE_INVALIDATED": "Caché de perfil invalidado para {user_id}",
        "SUCCESS_PROFILE_UPDATED": "Perfil actualizado con éxito",
        "ERROR_INVALID_PROFILE_DATA": "Datos de perfil inválidos",
        
        # ---------- Inversiones ----------
        "ERROR_INVESTMENT_NOT_FOUND": "Inversión no encontrada",
        "ERROR_SOLD_VALUE_REQUIRED": "El valor de venta es obligatorio al marcar como vendido",
        "ERROR_INVESTMENT_ALREADY_SOLD": "La inversión ya ha sido vendida",
        "ERROR_CANNOT_UPDATE_SOLD_INVESTMENT": "No se puede actualizar el precio de una inversión vendida",
        "ERROR_QUANTITY_NOT_DEFINED": "Inversión sin cantidad definida",
        "SUCCESS_INVESTMENT_DELETED": "Inversión eliminada con éxito",
        "INVESTMENT_CREATED": "Inversión creada con éxito",
        "INVESTMENT_UPDATED": "Inversión actualizada con éxito",
        
        # ---------- Usuario ----------
        "ERROR_INVALID_CURRENT_PASSWORD": "Contraseña actual incorrecta",
        "SUCCESS_PASSWORD_CHANGED": "Contraseña cambiada con éxito",
        "ERROR_INVALID_LANGUAGE": "Idioma inválido",
        "ERROR_INVALID_CURRENCY": "Moneda inválida",
        "SUCCESS_PREFERENCES_UPDATED": "Preferencias actualizadas con éxito",
        "ERROR_CANNOT_UNACCEPT_TERMS": "Los Términos de Uso no se pueden desmarcar después de ser aceptados",
        "SUCCESS_CONSENT_UPDATED": "Consentimiento actualizado con éxito",
        "SUCCESS_DATA_EXPORTED": "Datos exportados con éxito",
        "SUCCESS_ACCOUNT_DELETED": "Su cuenta y todos los datos asociados han sido eliminados permanentemente",
        "USER_UPDATED": "Usuario actualizado con éxito",
        "USER_DELETED": "Usuario eliminado con éxito",
        
        # ---------- Cache ----------
        "BALANCE_CACHE_HIT": "Saldo obtenido de caché",
        "BALANCE_CACHE_SAVED": "Saldo guardado en caché",
        "BALANCE_CACHE_INVALIDATED": "Caché de saldo invalidado",
        "BALANCE_CACHE_ERROR": "Error al acceder al caché de saldo",
        "BALANCE_CALCULATION_ERROR": "Error al calcular saldo",
        "REDIS_CONNECTION_ERROR": "Error de conexión Redis",
        "DB_NONE": "db no puede ser None",
        "USER_ID_EMPTY": "user_id no puede estar vacío",
        
        # ---------- Currency ----------
        "CURRENCY_TO_CENTS": "Conversión to_cents",
        "CURRENCY_FROM_CENTS": "Conversión from_cents",
        "CURRENCY_NEGATIVE_VALUE": "El valor no puede ser negativo",
        
        # ---------- Dates ----------
        "ERROR_DATE_PAST": "La fecha no puede ser en el pasado",
        "ERROR_DATE_FUTURE": "La fecha no puede ser en el futuro",
        "ERROR_INVALID_DUE_DAY": "Día de vencimiento inválido",
        "ERROR_START_DATE_PAST": "La fecha de inicio no puede ser en el pasado",
        
        # ---------- Installments ----------
        "ERROR_INSTALLMENTS_PARTS_ZERO": "El número de cuotas debe ser mayor que cero",
        "ERROR_INSTALLMENTS_TOTAL_ZERO": "El valor total debe ser mayor que cero",
        "ERROR_INSTALLMENTS_INTEREST_NEGATIVE": "La tasa de interés no puede ser negativa",
        "ERROR_INSTALLMENTS_INTEREST_HIGH": "La tasa de interés no puede ser mayor que 100%",
        
        # ---------- Notifications ----------
        "NOTIFICATION_EXPO_ERROR": "Error en Expo",
        "NOTIFICATION_SEND_ERROR": "Error al enviar notificación",
        "NOTIFICATION_TIMEOUT": "Timeout al enviar notificación",
        "NOTIFICATION_INVALID_TOKEN": "Token inválido",
        "NOTIFICATION_EMPTY_TOKEN": "Token vacío",
        "NOTIFICATION_EMPTY_TITLE": "Título vacío",
        "NOTIFICATION_EMPTY_BODY": "Cuerpo vacío",
        "NOTIFICATION_EMPTY_TOKEN_LIST": "Lista de tokens vacía",
        "NOTIFICATION_NO_VALID_TOKENS": "No se encontraron tokens válidos",
        "NOTIFICATION_BULK_ERROR": "Error al enviar notificaciones en lote",
        "NOTIFICATION_EXPO_URL_MISSING": "URL de API Expo no configurada",
        "NOTIFICATION_NO_TICKET": "No se recibió ticket para el token",
        
        # ---------- Scheduler ----------
        "SCHEDULER_WORKER_SCORE_LOADED": "✅ Worker de score cargado con éxito",
        "SCHEDULER_WORKER_SCORE_NOT_AVAILABLE": "⚠️ Worker de score no disponible: {error}",
        "SCHEDULER_WORKER_SCORE_ERROR": "❌ Error al cargar worker de score: {error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_LOADED": "✅ Worker de notificaciones cargado con éxito",
        "SCHEDULER_WORKER_NOTIFICATIONS_NOT_AVAILABLE": "⚠️ Worker de notificaciones no disponible: {error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_ERROR": "❌ Error al cargar worker de notificaciones: {error}",
        "SCHEDULER_ALREADY_INITIALIZED": "⚠️ El scheduler ya fue inicializado",
        "SCHEDULER_DEV_MODE": "ℹ️ Entorno de desarrollo detectado. Los workers NO serán programados.",
        "SCHEDULER_NO_WORKERS": "❌ Ningún worker disponible. El scheduler no se iniciará.",
        "SCHEDULER_SCORE_SCHEDULED": "⏰ Worker de score programado para las 03:00",
        "SCHEDULER_SCORE_NOT_SCHEDULED": "⚠️ Worker de score NO programado (no disponible)",
        "SCHEDULER_NOTIFICATIONS_SCHEDULED": "⏰ Worker de notificaciones programado para las 09:00",
        "SCHEDULER_NOTIFICATIONS_NOT_SCHEDULED": "⚠️ Worker de notificaciones NO programado (no disponible)",
        "SCHEDULER_STARTED": "✅ Scheduler iniciado con éxito!",
        "SCHEDULER_NO_JOBS": "⚠️ Ningún worker programado. El scheduler no se inició.",
        "SCHEDULER_SHUTDOWN": "🛑 Scheduler apagado",
        "SCHEDULER_SHUTDOWN_ERROR": "❌ Error al apagar scheduler: {error}",

        # ---------- Score Cache ----------
        "SCORE_CACHE_REDIS_CONNECTED": "✅ Redis conectado con éxito para caché de score",
        "SCORE_CACHE_REDIS_NOT_CONFIGURED": "ℹ️ Redis no configurado - usando MongoDB como caché",
        "SCORE_CACHE_REDIS_NOT_INSTALLED": "ℹ️ Redis no instalado - usando MongoDB como caché",
        "SCORE_CACHE_REDIS_ERROR": "❌ Error al conectar Redis: {error}",
        "SCORE_CACHE_USER_ID_INVALID": "❌ user_id inválido: {user_id}",
        "SCORE_CACHE_REDIS_HIT": "✅ Score obtenido de Redis para usuario {user_id}",
        "SCORE_CACHE_REDIS_MISS": "ℹ️ Score no encontrado en Redis para {user_id}",
        "SCORE_CACHE_REDIS_GET_ERROR": "⚠️ Error al obtener score de Redis para {user_id}: {error}",
        "SCORE_CACHE_REDIS_SET": "💾 Score almacenado en Redis para {user_id} (TTL: {ttl}s)",
        "SCORE_CACHE_REDIS_SET_ERROR": "⚠️ Error al almacenar score en Redis para {user_id}: {error}",
        "SCORE_CACHE_REDIS_INVALIDATED": "🗑️ Caché Redis invalidado para usuario {user_id}",
        "SCORE_CACHE_REDIS_INVALIDATE_ERROR": "⚠️ Error al invalidar caché Redis para {user_id}: {error}",
        "SCORE_CACHE_REDIS_BATCH_INVALIDATED": "🗑️ Caché invalidado para {count} usuarios ({errors} errores)",
        "SCORE_CACHE_MONGODB_HIT": "✅ Score obtenido de MongoDB para usuario {user_id}",
        "SCORE_CACHE_MONGODB_MISS": "ℹ️ Score no encontrado en MongoDB para {user_id}",
        "SCORE_CACHE_MONGODB_GET_ERROR": "⚠️ Error al obtener score de MongoDB para {user_id}: {error}",
        "SCORE_CACHE_MONGODB_SET": "💾 Score almacenado en MongoDB para {user_id}",
        "SCORE_CACHE_MONGODB_SET_ERROR": "⚠️ Error al almacenar score en MongoDB para {user_id}: {error}",
        "SCORE_CACHE_FINAL_HIT": "✅ Score final obtenido de caché para {user_id}",
        "SCORE_CACHE_FINAL_HIT_MONGODB": "✅ Score final obtenido de MongoDB para {user_id}",
        "SCORE_CACHE_MISS_RECALCULATING": "🔄 Cache miss para usuario {user_id} - recalculando score...",
        "SCORE_CACHE_RECALCULATED": "✅ Score recalculado para usuario {user_id}",
        "SCORE_CACHE_DB_NONE": "❌ db no puede ser None para el usuario {user_id}",

        # ---------- User Tokens ----------
        "USER_TOKENS_USER_ID_INVALID": "❌ user_id inválido: {user_id}",
        "USER_TOKENS_TOKEN_INVALID": "❌ token inválido: {token}",
        "USER_TOKENS_DB_NONE": "❌ db no puede ser None",
        "USER_TOKENS_GENERATING": "🔄 Generando token de eliminación para usuario {user_id}",
        "USER_TOKENS_GENERATED": "✅ Token generado para usuario {user_id} (expira en {expiry_hours} horas)",
        "USER_TOKENS_GENERATE_ERROR": "❌ Error al generar token para usuario {user_id}: {error}",
        "USER_TOKENS_VERIFYING": "🔍 Verificando token {token}",
        "USER_TOKENS_INVALID": "⚠️ Token inválido o expirado: {token}",
        "USER_TOKENS_VERIFIED": "✅ Token verificado para usuario {user_id}",
        "USER_TOKENS_VERIFY_ERROR": "❌ Error al verificar token: {error}",
        "USER_TOKENS_MARKING_USED": "📝 Marcando token como usado: {token}",
        "USER_TOKENS_MARKED_USED": "✅ Token marcado como usado: {token}",
        "USER_TOKENS_NOT_FOUND": "⚠️ Token no encontrado: {token}",
        "USER_TOKENS_MARK_ERROR": "❌ Error al marcar token como usado: {error}",
        "USER_TOKENS_DELETED_EXPIRED": "🗑️ {count} tokens expirados eliminados",
        "USER_TOKENS_DELETE_EXPIRED_ERROR": "❌ Error al eliminar tokens expirados: {error}",
        "USER_TOKENS_RATE_LIMIT": "⛔ Límite de generación de tokens excedido para usuario {user_id}. Espere 1 hora.",

        # ---------- Validators Extras ----------
        "VALIDATION_INSTALLMENTS_NONE": "Número de cuotas no informado",
        "VALIDATION_INSTALLMENTS_ZERO": "Número de cuotas inválido: {installments}",
        "VALIDATION_INSTALLMENTS_MAX": "El número máximo de cuotas es {max}. Recibido: {installments}",
        "VALIDATION_INSTALLMENTS_OK": "✅ Cuotas válidas: {installments}",
        "VALIDATION_INSTALLMENTS_TYPE": "El número de cuotas debe ser un número entero. Recibido: {type}",
        "VALIDATION_AMOUNT_NONE": "Valor no informado",
        "VALIDATION_AMOUNT_ZERO": "Valor inválido: {amount}. Debe ser mayor que cero",
        "VALIDATION_AMOUNT_OK": "✅ Valor válido: {amount}",
        "VALIDATION_AMOUNT_TYPE": "El valor debe ser un número entero. Recibido: {type}",
        "VALIDATION_INTEREST_RATE_NONE": "Tasa de interés no informada",
        "VALIDATION_INTEREST_RATE_INVALID": "Tasa de interés inválida: {rate}%. Debe ser entre 0% y 100%",
        "VALIDATION_INTEREST_RATE_OK": "✅ Tasa de interés válida: {rate}%",
        "VALIDATION_INTEREST_RATE_TYPE": "La tasa de interés debe ser un número. Recibido: {type}",
        "VALIDATION_QUANTITY_NONE": "Cantidad no informada",
        "VALIDATION_QUANTITY_ZERO": "Cantidad inválida: {quantity}. Debe ser mayor que cero",
        "VALIDATION_QUANTITY_OK": "✅ Cantidad válida: {quantity}",
        "VALIDATION_QUANTITY_TYPE": "La cantidad debe ser un número. Recibido: {type}",
        "VALIDATION_PRICE_NONE": "Precio no informado",
        "VALIDATION_PRICE_ZERO": "Precio inválido: {price}. Debe ser mayor que cero",
        "VALIDATION_PRICE_OK": "✅ Precio válido: {price}",
        "VALIDATION_PRICE_TYPE": "El precio debe ser un número. Recibido: {type}",
        "VALIDATION_PASSWORD_NONE": "Contraseña no informada",
        "VALIDATION_PASSWORD_LENGTH": "La contraseña debe tener al menos 8 caracteres",
        "VALIDATION_PASSWORD_CRITERIA": "La contraseña debe contener al menos 3 de los siguientes: mayúscula, minúscula, número, carácter especial",
        "VALIDATION_PASSWORD_OK": "✅ Contraseña fuerte",
        "VALIDATION_PASSWORD_TYPE": "La contraseña debe ser una cadena. Recibido: {type}",

        # ---------- Notifications Worker ----------
        "NOTIFICATION_TOKEN_FOUND": "✅ Token encontrado para usuario {user_id}",
        "NOTIFICATION_TOKEN_NOT_FOUND": "ℹ️ Ningún token encontrado para usuario {user_id}",
        "NOTIFICATION_TOKEN_ERROR": "❌ Error al buscar token para usuario {user_id}: {error}",
        "NOTIFICATION_USER_DATA": "📊 Datos del usuario {user_id}: score={score}",
        "NOTIFICATION_USER_DATA_ERROR": "❌ Error al buscar datos del usuario {user_id}: {error}",
        "NOTIFICATION_IA_ERROR": "❌ Error al generar mensaje IA: {error}",
        "NOTIFICATION_NO_TOKEN": "ℹ️ Usuario {user_id} no tiene token de notificación",
        "NOTIFICATION_DAILY_TITLE": "🌅 ¡Buenos días! Tu dosis diaria de finanzas",
        "NOTIFICATION_SENT_SUCCESS": "✅ Notificación enviada a usuario {user_id} - Score: {score}",
        "NOTIFICATION_SENT_FAILED": "❌ Fallo al enviar notificación a usuario {user_id}",
        "NOTIFICATION_SEND_ERROR": "❌ Error al enviar notificación a usuario {user_id}: {error}",
        "NOTIFICATION_WORKER_START": "🚀 Iniciando worker de notificaciones proactivas...",
        "NOTIFICATION_WORKER_USERS": "📊 Encontrados {total} usuarios con notificaciones activas",
        "NOTIFICATION_WORKER_USER_ERROR": "❌ Error al procesar usuario {user_id}: {error}",
        "NOTIFICATION_WORKER_DONE": "✅ Worker completado! {success}/{total} enviadas en {duration}s",
        "NOTIFICATION_WORKER_FATAL": "❌ Error fatal en worker de notificaciones: {error}",
        "NOTIFICATION_FALLBACK_HIGH": "🏆 Excelente! Tu score es {score}. ¡Sigue así!",
        "NOTIFICATION_FALLBACK_MEDIUM": "📈 Buen trabajo! Tu score es {score}. ¡Con pequeños ajustes llegarás!",
        "NOTIFICATION_FALLBACK_LOW": "💪 Vas por buen camino! Score {score}. Enfócate en reducir gastos.",
        "NOTIFICATION_FALLBACK_VERY_LOW": "🌟 ¿Empezamos? Tu score es {score}. ¡Puedo ayudarte a mejorar!",
        "NOTIFICATION_RETRY_ATTEMPT": "Intento {attempt} para {user_id}, esperando {wait_time}s",
        "NOTIFICATION_RETRY_SUCCESS": "✅ Notificación enviada en intento {attempt} para {user_id}",
        "NOTIFICATION_RETRY_FAILED": "❌ Todos los {max_retries} intentos fallaron para {user_id}",
        "NOTIFICATION_QUEUE_ADDED": "📥 Usuario {user_id} añadido a la cola",
        "NOTIFICATION_QUEUE_PROCESSING": "🚀 Iniciando procesamiento de cola",
        "NOTIFICATION_QUEUE_DONE": "✅ Cola procesada: {success}/{processed} enviadas",

        # ---------- Score Worker ----------
        "SCORE_WORKER_START": "🔄 Iniciando worker de score diario...",
        "SCORE_WORKER_NO_USERS": "ℹ️ Ningún usuario encontrado para procesar",
        "SCORE_WORKER_USERS": "📊 Encontrados {total} usuarios para procesar",
        "SCORE_WORKER_BATCH": "📦 Procesando lote {current}/{total}",
        "SCORE_WORKER_DONE": "✅ Worker de score completado! {success}/{total} usuarios procesados en {duration}s",
        "SCORE_WORKER_LOGGED": "📊 Ejecución registrada en base de datos",
        "SCORE_WORKER_LOG_ERROR": "⚠️ No se pudo registrar log del worker: {error}",
        "SCORE_WORKER_USER_SUCCESS": "✅ Score calculado para {email}: {score}",
        "SCORE_WORKER_USER_ERROR": "❌ Error al calcular score para {email}: {error}",
        "SCORE_WORKER_FATAL": "❌ Error fatal en worker de score: {error}",
        "SCORE_WORKER_DB_NONE": "❌ Fallo en la conexión con la base de datos",
        "SCORE_WORKER_INCREMENTAL": "🔄 Procesamiento incremental (última ejecución: {last_run})",
        "SCORE_WORKER_ACTIVE_USERS": "📊 {count} usuarios con actividad reciente",
        "SCORE_WORKER_NO_ACTIVE_USERS": "ℹ️ Ningún usuario con actividad reciente",
        "SCORE_WORKER_TRIGGERED": "🚀 Worker de score iniciado manualmente",
        "WORKER_SCORE_STARTED": "🚀 Worker de score activado manualmente por {user_id}",
        "WORKER_SCORE_DONE": "✅ Worker de score finalizado con estado: {status}",
        "WORKER_IMPORT_ERROR": "❌ Error al importar worker de score: {error}",

        # ---------- Score Queue ----------
        "SCORE_QUEUE_ADDED": "📥 Usuario {user_id} añadido a la cola de score",
        "SCORE_QUEUE_ERROR": "⚠️ Error al añadir a la cola de score: {error}",
        "SCORE_QUEUE_PROCESSING": "🚀 Iniciando procesamiento de cola de score...",
        "SCORE_QUEUE_PROCESS_ERROR": "❌ Error al procesar cola de score: {error}",
        "SCORE_QUEUE_DONE": "✅ Cola de score procesada: {success}/{processed} con éxito",
        "SCORE_QUEUE_WORKER_START": "🔄 Iniciando worker de cola de score (bucle infinito)...",
        "SCORE_QUEUE_WORKER_ERROR": "❌ Error en worker de cola de score: {error}",

        # ---------- Migrations ----------
        "MIGRATIONS_START": "🔄 Iniciando migraciones de datos...",
        "MIGRATIONS_DONE": "✅ Migraciones completadas! {executed} ejecutadas, {skipped} omitidas",
        "MIGRATIONS_SKIPPED": "ℹ️ Migración {name} ya ejecutada, omitiendo...",
        "MIGRATIONS_EXECUTING": "🔄 Ejecutando migración {name}...",
        "MIGRATIONS_NO_USERS": "ℹ️ Ningún usuario para migrar",
        "MIGRATIONS_USERS_UPDATED": "✅ {total} usuarios actualizados",
        "MIGRATIONS_EXECUTED": "✅ Migración {name} completada",
        "MIGRATIONS_ERROR": "❌ Error en migración {name}: {error}",
        "MIGRATIONS_DB_NONE": "❌ db no puede ser None",
        "MIGRATIONS_BATCH": "📦 Procesados {processed} usuarios...",

        # ---------- Categories ----------
        "CATEGORY_ALIMENTACAO": "Alimentación",
        "CATEGORY_TRANSPORTE": "Transporte",
        "CATEGORY_MORADIA": "Vivienda",
        "CATEGORY_LAZER": "Ocio",
        "CATEGORY_SAUDE": "Salud",
        "CATEGORY_EDUCACAO": "Educación",
        "CATEGORY_INVESTIMENTOS": "Inversiones",
        "CATEGORY_VESTUARIO": "Vestimenta",
        "CATEGORY_BELEZA": "Belleza",
        "CATEGORY_ELETRONICOS": "Electrónicos",
        "CATEGORY_CASA": "Hogar",
        "CATEGORY_CARRO": "Coche",
        "CATEGORY_ECONOMIA": "Ahorro",
        "CATEGORY_VIAGEM": "Viaje",
        "CATEGORY_RENDA_FIXA": "Renta Fija",
        "CATEGORY_ACOES": "Acciones",
        "CATEGORY_FIIS": "FIIs",
        "CATEGORY_CRIPTO": "Cripto",
        "CATEGORY_OUTROS": "Otros",
        "CATEGORY_INVESTIMENTO": "Inversión",
        
        # ---------- 🆕 Categorías Personalizadas ----------
        "CATEGORY_ALREADY_EXISTS": "Ya existe una categoría con este nombre para el usuario.",
        "CATEGORY_NOT_FOUND": "Categoría no encontrada.",
        "CATEGORY_DELETED": "Categoría eliminada con éxito.",
        "CATEGORY_INVALID_TYPE": "Tipo de categoría inválido. Use: expense, income, goal, investment o bill.",
        "CATEGORY_NAME_REQUIRED": "El nombre de la categoría es obligatorio.",
        "CATEGORY_INVALID_COLOR": "Color inválido. Use formato hexadecimal (#RRGGBB o #RGB).",
    },

    # ============================================================
    # CHINÊS SIMPLIFICADO (zh)
    # ============================================================
    "zh": {
        # ---------- 成功 ----------
        "SUCCESS_CREATED": "创建成功",
        "SUCCESS_UPDATED": "更新成功",
        "SUCCESS_DELETED": "删除成功",
        
        # ---------- 常见错误 ----------
        "ERROR_NOT_FOUND": "未找到",
        "ERROR_UNAUTHORIZED": "未授权",
        "ERROR_FORBIDDEN": "访问被拒绝",
        "ERROR_SERVER": "服务器内部错误",
        "ERROR_VALIDATION": "数据无效",
        "ERROR_CONFLICT": "冲突 - 资源已存在",
        "ERROR_NO_DATA_TO_UPDATE": "没有数据可更新",
        "ERROR_INVALID_DATE_RANGE": "开始日期不能大于结束日期",
        "ERROR_PAGINATION_FAILED": "分页错误：{error}",
        "ERROR_INVALID_ID": "{field_name} 无效",
        "ERROR_DATE_FUTURE": "不能是未来日期",
        
        # ---------- 认证 ----------
        "AUTH_INVALID_CREDENTIALS": "邮箱或密码无效",
        "AUTH_EMAIL_ALREADY_EXISTS": "邮箱已注册",
        "AUTH_WEAK_PASSWORD": "密码太弱",
        "AUTH_INVALID_TOKEN": "令牌无效或已过期",
        "AUTH_TOKEN_REFRESHED": "令牌更新成功",
        "AUTH_TOKEN_REVOKED": "令牌已撤销",
        "AUTH_USER_NOT_FOUND": "未找到用户",
        "AUTH_INVALID_REFRESH_TOKEN": "刷新令牌无效",
        "AUTH_TOKEN_EXPIRED": "令牌已过期",
        
        # ---------- 成就 ----------
        "ACHIEVEMENT_NOT_FOUND": "未找到成就",
        "ACHIEVEMENT_CREATED": "成就创建成功",
        "ACHIEVEMENT_UPDATED": "成就更新成功",
        "ACHIEVEMENT_DELETED": "成就删除成功",
        "ACHIEVEMENT_ALREADY_EXISTS": "此成就已记录",
        "ACHIEVEMENT_SYNC_NONE": "没有新成就需要同步",
        "ACHIEVEMENT_SYNC_ONE": "1个成就同步成功",
        "ACHIEVEMENT_SYNC_MULTIPLE": "{count}个成就同步成功",
        "ACHIEVEMENT_SYNC_BATCH_TOO_LARGE": "每次同步的最大成就数为{MAX}。请分批发送。",
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "无效的成就类型",
        "ERROR_INVALID_MONTH": "月份必须在1到12之间",
        "ERROR_INVALID_YEAR": "年份必须在1900到2100之间",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "描述不能为空",
        
        # ---------- 账单 ----------
        "BILL_NOT_FOUND": "未找到账单",
        "BILL_NO_DATA_TO_UPDATE": "没有数据可更新",
        "BILL_CREATED": "账单创建成功",
        "BILL_UPDATED": "账单更新成功",
        "BILL_DELETED": "账单删除成功",
        "BILL_ALREADY_PAID": "账单已支付",
        "BILL_PAYMENT_FAILED": "处理支付失败",
        "ERROR_MAX_INSTALLMENTS_EXCEEDED": "最大分期数为{MAX}",
        "ERROR_INVALID_INSTALLMENTS": "无效的分期数",
        "ERROR_TOTAL_LESS_THAN_PAID": "总分期数不能少于已支付数",
        "ERROR_AMOUNT_INVALID": "金额无效。必须大于零",
        "ERROR_START_DATE_PAST": "开始日期不能是过去日期",
        "ERROR_INVALID_DUE_DAY": "该月份无效的到期日",
        "ERROR_CREATE_BILL_FAILED": "创建账单时内部错误",
        
        # ---------- 分期 ----------
        "INSTALLMENT_NOT_FOUND": "未找到分期",
        "INSTALLMENT_ALREADY_PAID": "此分期已支付",
        "INSTALLMENT_NOT_PAID": "此分期未支付",
        "INSTALLMENT_PAID_SUCCESS": "分期支付成功",
        "INSTALLMENTS_ALL_PAID": "所有分期已成功支付",
        "INSTALLMENTS_ALREADY_PAID": "所有分期已支付",
        "INSTALLMENT_NOT_YET_DUE": "此分期尚未到期",
        "INSTALLMENT_UNPAY_SUCCESS": "支付已成功撤销",
        "INSTALLMENT_UNPAY_WINDOW_EXPIRED": "无法撤销超过30天的付款",
        "INSTALLMENT_UNPAY_SUCCESS_BUT_BILL_PAID": "支付撤销成功，但主账单仍显示为已支付。请检查一致性。",
        
        # ---------- 信用卡 ----------
        "ERROR_CARD_NOT_FOUND": "未找到卡片",
        "ERROR_CARD_HAS_PURCHASES": "卡片有关联的购买记录。请先删除购买记录。",
        "SUCCESS_CARD_DELETED": "卡片删除成功",
        "ERROR_CANNOT_REDUCE_LIMIT": "无法将限额降低到已使用金额（R$ {value:.2f}）以下",
        "SUCCESS_LIMITS_RECALCULATED": "限额重新计算成功。",
        "CARD_LIMIT_EXCEEDED": "超出卡片限额",
        "CARD_INVALID_CLOSING_DAY": "无效的账单日",
        "CARD_INVALID_DUE_DAY": "无效的还款日",
        "CARD_CREATED": "卡片创建成功",
        "CARD_UPDATED": "卡片更新成功",
        
        # ---------- 购买 ----------
        "ERROR_PURCHASE_NOT_FOUND": "未找到购买记录",
        "ERROR_INSUFFICIENT_LIMIT": "额度不足。可用：R$ {available:.2f}，需要：R$ {required:.2f}",
        "ERROR_CANNOT_EDIT_PAID_INSTALLMENTS": "无法编辑已有已付分期的购买",
        "SUCCESS_PURCHASE_DELETED": "购买和分期已成功删除",
        "SUCCESS_INSTALLMENT_PAID": "分期已标记为已付并减少承诺金额",
        "SUCCESS_INSTALLMENT_UNPAY": "付款已成功撤销",
        "ERROR_FIRST_DUE_DATE_PAST": "首期到期日不能是过去日期",
        "ERROR_INVALID_INTEREST_RATE": "利率无效。必须在0%到100%之间",
        
        # ---------- 目标 ----------
        "ERROR_GOAL_NOT_FOUND": "未找到目标",
        "SUCCESS_GOAL_DELETED": "目标删除成功",
        "GOAL_CREATED": "目标创建成功",
        "GOAL_UPDATED": "目标更新成功",
        "GOAL_COMPLETED": "目标完成！恭喜！",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "当前值不能超过目标值",
        
        # ---------- IA ----------
        "ERROR_USER_NOT_FOUND": "未找到用户。",
        "ERROR_TERMS_NOT_ACCEPTED": "要使用助手，您需要接受使用条款。前往设置 > 同意。",
        "ERROR_IA_REQUEST_FAILED": "无法处理您的请求。请稍后再试。",
        "SUCCESS_FEEDBACK_RECEIVED": "反馈接收成功！",
        "ERROR_AUDIT_NOT_FOUND": "未找到交互记录。",
        "IA_TIMEOUT": "AI响应超时",
        "ERROR_RESEARCH_CONSENT_REQUIRED": "要发送反馈，您需要接受研究同意。前往设置 > 同意。",
        
        # ---------- IA Service ----------
        "IA_ERROR_GENERIC": "抱歉，处理您的问题时出错。请稍后再试。",
        "IA_ERROR_TIMEOUT": "响应时间超过预期。请稍后再试。",
        "IA_OUT_OF_SCOPE": "抱歉，我只能帮助回答有关个人财务的问题。我可以帮助储蓄、投资或财务规划吗？",
        "IA_CACHE_HIT": "使用缓存响应",
        
        # ---------- 评分 ----------
        "SCORE_CALCULATED": "评分计算成功",
        "SCORE_UPDATED": "评分更新成功",
        "SCORE_CACHE_HIT": "从缓存获取评分",
        "SCORE_CACHE_MISS": "缓存中未找到评分，正在计算...",
        "SCORE_CACHE_EXPIRED": "缓存已过期，正在重新计算...",
        "SCORE_CACHE_SAVED": "评分已保存到缓存",
        "SCORE_CACHE_INVALIDATED": "评分缓存已失效",
        "SCORE_CACHE_ERROR": "访问评分缓存时出错",
        "SCORE_VARIATION_LIMITED": "变化限制在±5分以内",
        "SCORE_NO_USER": "未找到用户",
        "SCORE_GOALS_ERROR": "获取目标时出错",
        "SCORE_CALCULATION_STARTED": "开始计算评分",
        
        # ---------- Score Ranges ----------
        "SCORE_RANGE_0_20": "0-20",
        "SCORE_RANGE_20_40": "20-40",
        "SCORE_RANGE_40_60": "40-60",
        "SCORE_RANGE_60_80": "60-80",
        "SCORE_RANGE_80_100": "80-100",
        
        # ---------- Expense Ranges ----------
        "EXPENSE_RANGE_0_100": "0-100",
        "EXPENSE_RANGE_100_500": "100-500",
        "EXPENSE_RANGE_500_1000": "500-1000",
        "EXPENSE_RANGE_1000_5000": "1000-5000",
        "EXPENSE_RANGE_5000_PLUS": "5000+",
        
        # ---------- Email ----------
        "EMAIL_RESET_SUBJECT": "重置密码 - Velorium",
        "EMAIL_DELETE_SUBJECT": "确认删除账户 - Velorium",
        "EMAIL_TEST_SUBJECT": "测试邮件 - Velorium",
        
        # ---------- Audit ----------
        "AUDIT_COLLECTION_NONE": "集合不能为 None",
        "AUDIT_DOC_ID_EMPTY": "doc_id 不能为空",
        "AUDIT_DOC_ID_INVALID": "doc_id 无效",
        "AUDIT_USER_ID_EMPTY": "user_id 不能为空",
        "AUDIT_USER_ID_INVALID": "user_id 无效",
        "AUDIT_DB_NONE": "db 不能为 None",
        "AUDIT_ERROR_SAVING": "保存审计日志时出错",
        
        # ---------- 交易 ----------
        "ERROR_TRANSACTION_NOT_FOUND": "未找到交易。",
        "ERROR_CREATE_TRANSACTION_FAILED": "创建交易时内部错误。",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "无法删除已有已付分期的支出。",
        "SUCCESS_TRANSACTION_DELETED": "交易删除成功。",
        "SUCCESS_BULK_CATEGORIZED": "{count}笔交易重新分类成功。",
        "SUCCESS_BALANCE_RECALCULATED": "余额重新计算成功。",
        "ERROR_BULK_LIMIT_EXCEEDED": "超出每请求100笔交易的限制。",
        "ERROR_INVALID_CATEGORY": "无效的分类。使用：{categories}",
        
        # ---------- 通知 ----------
        "SUCCESS_TOKEN_REGISTERED": "令牌注册成功",
        "SUCCESS_NOTIFICATIONS_ENABLED": "通知已启用",
        "SUCCESS_NOTIFICATIONS_DISABLED": "通知已禁用",
        "SUCCESS_TEST_NOTIFICATION_SENT": "测试通知已发送",
        "ERROR_TEST_NOTIFICATION_FAILED": "发送测试通知失败",
        "ERROR_NO_PUSH_TOKEN": "未注册推送令牌",
        "NOTIFICATION_DAILY_INSIGHT_TITLE": "💡 Veloria - 每日洞察",
        "NOTIFICATION_DAILY_REMINDER_TITLE": "💜 Veloria - 每日更新",
        "NOTIFICATION_SENT": "通知发送成功",
        "NOTIFICATION_FAILED": "发送通知失败",
        
        # ---------- 限流 ----------
        "RATE_LIMIT_EXCEEDED": "请求过多，请稍后再试",
        
        # ---------- 个人资料 ----------
        "ERROR_PROFILE_NOT_FOUND": "未找到用户 {user_id} 的个人资料",
        "ERROR_PROFILE_COLLECTION": "创建/检查个人资料集合时出错：{error}",
        "ERROR_PROFILE_CREATE_FAILED": "为用户 {user_id} 创建个人资料时出错",
        "ERROR_PROFILE_UPDATE_FAILED": "更新用户 {user_id} 的个人资料时出错",
        "PROFILE_CACHE_HIT": "命中 {user_id} 的个人资料缓存",
        "PROFILE_CACHE_MISS": "未命中 {user_id} 的个人资料缓存",
        "PROFILE_CACHE_SET": "已缓存 {user_id} 的个人资料",
        "PROFILE_CACHE_INVALIDATED": "已失效 {user_id} 的个人资料缓存",
        "SUCCESS_PROFILE_UPDATED": "个人资料更新成功",
        "ERROR_INVALID_PROFILE_DATA": "个人资料数据无效",
        
        # ---------- 投资 ----------
        "ERROR_INVESTMENT_NOT_FOUND": "未找到投资",
        "ERROR_SOLD_VALUE_REQUIRED": "标记为已售时需要出售价值",
        "ERROR_INVESTMENT_ALREADY_SOLD": "投资已售出",
        "ERROR_CANNOT_UPDATE_SOLD_INVESTMENT": "无法更新已售投资的价格",
        "ERROR_QUANTITY_NOT_DEFINED": "未定义数量的投资",
        "SUCCESS_INVESTMENT_DELETED": "投资删除成功",
        "INVESTMENT_CREATED": "投资创建成功",
        "INVESTMENT_UPDATED": "投资更新成功",
        
        # ---------- 用户 ----------
        "ERROR_INVALID_CURRENT_PASSWORD": "当前密码不正确",
        "SUCCESS_PASSWORD_CHANGED": "密码更改成功",
        "ERROR_INVALID_LANGUAGE": "无效的语言",
        "ERROR_INVALID_CURRENCY": "无效的货币",
        "SUCCESS_PREFERENCES_UPDATED": "偏好设置更新成功",
        "ERROR_CANNOT_UNACCEPT_TERMS": "接受后无法取消使用条款",
        "SUCCESS_CONSENT_UPDATED": "同意更新成功",
        "SUCCESS_DATA_EXPORTED": "数据导出成功",
        "SUCCESS_ACCOUNT_DELETED": "您的帐户和所有相关数据已被永久删除",
        "USER_UPDATED": "用户更新成功",
        "USER_DELETED": "用户删除成功",
        
        # ---------- Cache ----------
        "BALANCE_CACHE_HIT": "从缓存获取余额",
        "BALANCE_CACHE_SAVED": "余额已保存到缓存",
        "BALANCE_CACHE_INVALIDATED": "余额缓存已失效",
        "BALANCE_CACHE_ERROR": "访问余额缓存时出错",
        "BALANCE_CALCULATION_ERROR": "计算余额时出错",
        "REDIS_CONNECTION_ERROR": "Redis连接错误",
        "DB_NONE": "db 不能为 None",
        "USER_ID_EMPTY": "user_id 不能为空",
        
        # ---------- Currency ----------
        "CURRENCY_TO_CENTS": "转换为分",
        "CURRENCY_FROM_CENTS": "从分转换",
        "CURRENCY_NEGATIVE_VALUE": "值不能为负数",
        
        # ---------- Dates ----------
        "ERROR_DATE_PAST": "日期不能是过去",
        "ERROR_DATE_FUTURE": "日期不能是未来",
        "ERROR_INVALID_DUE_DAY": "无效的到期日",
        "ERROR_START_DATE_PAST": "开始日期不能是过去",
        
        # ---------- Installments ----------
        "ERROR_INSTALLMENTS_PARTS_ZERO": "分期数必须大于零",
        "ERROR_INSTALLMENTS_TOTAL_ZERO": "总金额必须大于零",
        "ERROR_INSTALLMENTS_INTEREST_NEGATIVE": "利率不能为负数",
        "ERROR_INSTALLMENTS_INTEREST_HIGH": "利率不能大于100%",
        
        # ---------- Notifications ----------
        "NOTIFICATION_EXPO_ERROR": "Expo错误",
        "NOTIFICATION_SEND_ERROR": "发送通知错误",
        "NOTIFICATION_TIMEOUT": "发送通知超时",
        "NOTIFICATION_INVALID_TOKEN": "无效令牌",
        "NOTIFICATION_EMPTY_TOKEN": "空令牌",
        "NOTIFICATION_EMPTY_TITLE": "空标题",
        "NOTIFICATION_EMPTY_BODY": "空内容",
        "NOTIFICATION_EMPTY_TOKEN_LIST": "空令牌列表",
        "NOTIFICATION_NO_VALID_TOKENS": "未找到有效令牌",
        "NOTIFICATION_BULK_ERROR": "批量发送通知错误",
        "NOTIFICATION_EXPO_URL_MISSING": "未配置Expo API URL",
        "NOTIFICATION_NO_TICKET": "未收到令牌的票证",
        
        # ---------- Scheduler ----------
        "SCHEDULER_WORKER_SCORE_LOADED": "✅ 评分工作器加载成功",
        "SCHEDULER_WORKER_SCORE_NOT_AVAILABLE": "⚠️ 评分工作器不可用：{error}",
        "SCHEDULER_WORKER_SCORE_ERROR": "❌ 加载评分工作器出错：{error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_LOADED": "✅ 通知工作器加载成功",
        "SCHEDULER_WORKER_NOTIFICATIONS_NOT_AVAILABLE": "⚠️ 通知工作器不可用：{error}",
        "SCHEDULER_WORKER_NOTIFICATIONS_ERROR": "❌ 加载通知工作器出错：{error}",
        "SCHEDULER_ALREADY_INITIALIZED": "⚠️ 调度器已初始化",
        "SCHEDULER_DEV_MODE": "ℹ️ 检测到开发环境。工作器将不会调度。",
        "SCHEDULER_NO_WORKERS": "❌ 没有可用的工作器。调度器不会启动。",
        "SCHEDULER_SCORE_SCHEDULED": "⏰ 评分工作器安排在 03:00",
        "SCHEDULER_SCORE_NOT_SCHEDULED": "⚠️ 评分工作器未安排（不可用）",
        "SCHEDULER_NOTIFICATIONS_SCHEDULED": "⏰ 通知工作器安排在 09:00",
        "SCHEDULER_NOTIFICATIONS_NOT_SCHEDULED": "⚠️ 通知工作器未安排（不可用）",
        "SCHEDULER_STARTED": "✅ 调度器启动成功！",
        "SCHEDULER_NO_JOBS": "⚠️ 没有安排工作器。调度器未启动。",
        "SCHEDULER_SHUTDOWN": "🛑 调度器已关闭",
        "SCHEDULER_SHUTDOWN_ERROR": "❌ 关闭调度器出错：{error}",

        # ---------- Score Cache ----------
        "SCORE_CACHE_REDIS_CONNECTED": "✅ Redis 成功连接到评分缓存",
        "SCORE_CACHE_REDIS_NOT_CONFIGURED": "ℹ️ Redis 未配置 - 使用 MongoDB 作为缓存",
        "SCORE_CACHE_REDIS_NOT_INSTALLED": "ℹ️ Redis 未安装 - 使用 MongoDB 作为缓存",
        "SCORE_CACHE_REDIS_ERROR": "❌ 连接 Redis 出错：{error}",
        "SCORE_CACHE_USER_ID_INVALID": "❌ user_id 无效：{user_id}",
        "SCORE_CACHE_REDIS_HIT": "✅ 从 Redis 获取用户 {user_id} 的评分",
        "SCORE_CACHE_REDIS_MISS": "ℹ️ 在 Redis 中未找到 {user_id} 的评分",
        "SCORE_CACHE_REDIS_GET_ERROR": "⚠️ 从 Redis 获取 {user_id} 的评分出错：{error}",
        "SCORE_CACHE_REDIS_SET": "💾 评分已存储在 Redis 中 {user_id}（TTL：{ttl}s）",
        "SCORE_CACHE_REDIS_SET_ERROR": "⚠️ 存储评分到 Redis 出错 {user_id}：{error}",
        "SCORE_CACHE_REDIS_INVALIDATED": "🗑️ 用户 {user_id} 的 Redis 缓存已失效",
        "SCORE_CACHE_REDIS_INVALIDATE_ERROR": "⚠️ 使 {user_id} 的 Redis 缓存失效出错：{error}",
        "SCORE_CACHE_REDIS_BATCH_INVALIDATED": "🗑️ 已使 {count} 个用户的缓存失效（{errors} 个错误）",
        "SCORE_CACHE_MONGODB_HIT": "✅ 从 MongoDB 获取用户 {user_id} 的评分",
        "SCORE_CACHE_MONGODB_MISS": "ℹ️ 在 MongoDB 中未找到 {user_id} 的评分",
        "SCORE_CACHE_MONGODB_GET_ERROR": "⚠️ 从 MongoDB 获取 {user_id} 的评分出错：{error}",
        "SCORE_CACHE_MONGODB_SET": "💾 评分已存储在 MongoDB 中 {user_id}",
        "SCORE_CACHE_MONGODB_SET_ERROR": "⚠️ 存储评分到 MongoDB 出错 {user_id}：{error}",
        "SCORE_CACHE_FINAL_HIT": "✅ 从缓存获取用户 {user_id} 的最终评分",
        "SCORE_CACHE_FINAL_HIT_MONGODB": "✅ 从 MongoDB 获取用户 {user_id} 的最终评分",
        "SCORE_CACHE_MISS_RECALCULATING": "🔄 用户 {user_id} 的缓存未命中 - 重新计算评分...",
        "SCORE_CACHE_RECALCULATED": "✅ 用户 {user_id} 的评分已重新计算",
        "SCORE_CACHE_DB_NONE": "❌ 用户 {user_id} 的 db 不能为 None",

        # ---------- User Tokens ----------
        "USER_TOKENS_USER_ID_INVALID": "❌ user_id 无效：{user_id}",
        "USER_TOKENS_TOKEN_INVALID": "❌ token 无效：{token}",
        "USER_TOKENS_DB_NONE": "❌ db 不能为 None",
        "USER_TOKENS_GENERATING": "🔄 为用户 {user_id} 生成删除令牌",
        "USER_TOKENS_GENERATED": "✅ 为用户 {user_id} 生成令牌（在 {expiry_hours} 小时后过期）",
        "USER_TOKENS_GENERATE_ERROR": "❌ 为用户 {user_id} 生成令牌出错：{error}",
        "USER_TOKENS_VERIFYING": "🔍 验证令牌 {token}",
        "USER_TOKENS_INVALID": "⚠️ 令牌无效或已过期：{token}",
        "USER_TOKENS_VERIFIED": "✅ 用户 {user_id} 的令牌已验证",
        "USER_TOKENS_VERIFY_ERROR": "❌ 验证令牌出错：{error}",
        "USER_TOKENS_MARKING_USED": "📝 标记令牌为已使用：{token}",
        "USER_TOKENS_MARKED_USED": "✅ 令牌已标记为已使用：{token}",
        "USER_TOKENS_NOT_FOUND": "⚠️ 未找到令牌：{token}",
        "USER_TOKENS_MARK_ERROR": "❌ 标记令牌为已使用时出错：{error}",
        "USER_TOKENS_DELETED_EXPIRED": "🗑️ 删除了 {count} 个过期令牌",
        "USER_TOKENS_DELETE_EXPIRED_ERROR": "❌ 删除过期令牌时出错：{error}",
        "USER_TOKENS_RATE_LIMIT": "⛔ 用户 {user_id} 超出令牌生成限制。请等待 1 小时。",

        # ---------- Validators Extras ----------
        "VALIDATION_INSTALLMENTS_NONE": "未提供分期数",
        "VALIDATION_INSTALLMENTS_ZERO": "分期数无效：{installments}",
        "VALIDATION_INSTALLMENTS_MAX": "最大分期数为{max}。收到：{installments}",
        "VALIDATION_INSTALLMENTS_OK": "✅ 分期数有效：{installments}",
        "VALIDATION_INSTALLMENTS_TYPE": "分期数必须是整数。收到：{type}",
        "VALIDATION_AMOUNT_NONE": "未提供金额",
        "VALIDATION_AMOUNT_ZERO": "金额无效：{amount}。必须大于零",
        "VALIDATION_AMOUNT_OK": "✅ 金额有效：{amount}",
        "VALIDATION_AMOUNT_TYPE": "金额必须是整数。收到：{type}",
        "VALIDATION_INTEREST_RATE_NONE": "未提供利率",
        "VALIDATION_INTEREST_RATE_INVALID": "利率无效：{rate}%。必须在0%到100%之间",
        "VALIDATION_INTEREST_RATE_OK": "✅ 利率有效：{rate}%",
        "VALIDATION_INTEREST_RATE_TYPE": "利率必须是数字。收到：{type}",
        "VALIDATION_QUANTITY_NONE": "未提供数量",
        "VALIDATION_QUANTITY_ZERO": "数量无效：{quantity}。必须大于零",
        "VALIDATION_QUANTITY_OK": "✅ 数量有效：{quantity}",
        "VALIDATION_QUANTITY_TYPE": "数量必须是数字。收到：{type}",
        "VALIDATION_PRICE_NONE": "未提供价格",
        "VALIDATION_PRICE_ZERO": "价格无效：{price}。必须大于零",
        "VALIDATION_PRICE_OK": "✅ 价格有效：{price}",
        "VALIDATION_PRICE_TYPE": "价格必须是数字。收到：{type}",
        "VALIDATION_PASSWORD_NONE": "未提供密码",
        "VALIDATION_PASSWORD_LENGTH": "密码必须至少8个字符",
        "VALIDATION_PASSWORD_CRITERIA": "密码必须包含以下至少3种：大写字母、小写字母、数字、特殊字符",
        "VALIDATION_PASSWORD_OK": "✅ 密码强度高",
        "VALIDATION_PASSWORD_TYPE": "密码必须是字符串。收到：{type}",

        # ---------- Notifications Worker ----------
        "NOTIFICATION_TOKEN_FOUND": "✅ 找到用户 {user_id} 的令牌",
        "NOTIFICATION_TOKEN_NOT_FOUND": "ℹ️ 未找到用户 {user_id} 的令牌",
        "NOTIFICATION_TOKEN_ERROR": "❌ 获取用户 {user_id} 的令牌时出错：{error}",
        "NOTIFICATION_USER_DATA": "📊 用户 {user_id} 的数据：score={score}",
        "NOTIFICATION_USER_DATA_ERROR": "❌ 获取用户 {user_id} 的数据时出错：{error}",
        "NOTIFICATION_IA_ERROR": "❌ 生成AI消息时出错：{error}",
        "NOTIFICATION_NO_TOKEN": "ℹ️ 用户 {user_id} 没有通知令牌",
        "NOTIFICATION_DAILY_TITLE": "🌅 早上好！您的每日财务资讯",
        "NOTIFICATION_SENT_SUCCESS": "✅ 通知已发送给用户 {user_id} - 评分：{score}",
        "NOTIFICATION_SENT_FAILED": "❌ 发送通知给用户 {user_id} 失败",
        "NOTIFICATION_SEND_ERROR": "❌ 发送通知给用户 {user_id} 时出错：{error}",
        "NOTIFICATION_WORKER_START": "🚀 启动主动通知工作器...",
        "NOTIFICATION_WORKER_USERS": "📊 找到 {total} 个有活动通知的用户",
        "NOTIFICATION_WORKER_USER_ERROR": "❌ 处理用户 {user_id} 时出错：{error}",
        "NOTIFICATION_WORKER_DONE": "✅ 工作器完成！在 {duration} 秒内发送了 {success}/{total} 条",
        "NOTIFICATION_WORKER_FATAL": "❌ 通知工作器发生致命错误：{error}",
        "NOTIFICATION_FALLBACK_HIGH": "🏆 太棒了！您的评分是 {score}。继续保持！",
        "NOTIFICATION_FALLBACK_MEDIUM": "📈 做得好！您的评分是 {score}。再做一些小调整就能达到目标！",
        "NOTIFICATION_FALLBACK_LOW": "💪 您走在正确的道路上！评分 {score}。专注于减少开支。",
        "NOTIFICATION_FALLBACK_VERY_LOW": "🌟 我们开始吧？您的评分是 {score}。我可以帮助您改善！",
        "NOTIFICATION_RETRY_ATTEMPT": "用户 {user_id} 的第 {attempt} 次尝试，等待 {wait_time} 秒",
        "NOTIFICATION_RETRY_SUCCESS": "✅ 用户 {user_id} 在第 {attempt} 次尝试时成功发送通知",
        "NOTIFICATION_RETRY_FAILED": "❌ 用户 {user_id} 的所有 {max_retries} 次尝试均失败",
        "NOTIFICATION_QUEUE_ADDED": "📥 用户 {user_id} 已添加到队列",
        "NOTIFICATION_QUEUE_PROCESSING": "🚀 开始处理队列",
        "NOTIFICATION_QUEUE_DONE": "✅ 队列处理完成：发送了 {success}/{processed} 条",

        # ---------- Score Worker ----------
        "SCORE_WORKER_START": "🔄 开始每日评分工作器...",
        "SCORE_WORKER_NO_USERS": "ℹ️ 没有找到需要处理的用户",
        "SCORE_WORKER_USERS": "📊 找到 {total} 个用户需要处理",
        "SCORE_WORKER_BATCH": "📦 处理批次 {current}/{total}",
        "SCORE_WORKER_DONE": "✅ 评分工作器完成！在 {duration} 秒内处理了 {success}/{total} 个用户",
        "SCORE_WORKER_LOGGED": "📊 执行已记录到数据库",
        "SCORE_WORKER_LOG_ERROR": "⚠️ 无法记录工作器执行情况：{error}",
        "SCORE_WORKER_USER_SUCCESS": "✅ 已为 {email} 计算评分：{score}",
        "SCORE_WORKER_USER_ERROR": "❌ 为 {email} 计算评分时出错：{error}",
        "SCORE_WORKER_FATAL": "❌ 评分工作器发生致命错误：{error}",
        "SCORE_WORKER_DB_NONE": "❌ 数据库连接失败",
        "SCORE_WORKER_INCREMENTAL": "🔄 增量处理（上次运行：{last_run}）",
        "SCORE_WORKER_ACTIVE_USERS": "📊 {count} 个有最近活动的用户",
        "SCORE_WORKER_NO_ACTIVE_USERS": "ℹ️ 没有有最近活动的用户",
        "SCORE_WORKER_TRIGGERED": "🚀 手动触发了评分工作器",
        "WORKER_SCORE_STARTED": "🚀 由 {user_id} 手动触发了评分工作器",
        "WORKER_SCORE_DONE": "✅ 评分工作器已完成，状态：{status}",
        "WORKER_IMPORT_ERROR": "❌ 导入评分工作器时出错：{error}",

        # ---------- Score Queue ----------
        "SCORE_QUEUE_ADDED": "📥 用户 {user_id} 已添加到评分队列",
        "SCORE_QUEUE_ERROR": "⚠️ 添加到评分队列时出错：{error}",
        "SCORE_QUEUE_PROCESSING": "🚀 开始处理评分队列...",
        "SCORE_QUEUE_PROCESS_ERROR": "❌ 处理评分队列时出错：{error}",
        "SCORE_QUEUE_DONE": "✅ 评分队列处理完成：成功处理了 {success}/{processed} 个",
        "SCORE_QUEUE_WORKER_START": "🔄 开始评分队列工作器（无限循环）...",
        "SCORE_QUEUE_WORKER_ERROR": "❌ 评分队列工作器出错：{error}",

        # ---------- Migrations ----------
        "MIGRATIONS_START": "🔄 开始数据迁移...",
        "MIGRATIONS_DONE": "✅ 迁移完成！执行了 {executed} 项，跳过了 {skipped} 项",
        "MIGRATIONS_SKIPPED": "ℹ️ 迁移 {name} 已执行，跳过...",
        "MIGRATIONS_EXECUTING": "🔄 正在执行迁移 {name}...",
        "MIGRATIONS_NO_USERS": "ℹ️ 没有需要迁移的用户",
        "MIGRATIONS_USERS_UPDATED": "✅ 已更新 {total} 个用户",
        "MIGRATIONS_EXECUTED": "✅ 迁移 {name} 已完成",
        "MIGRATIONS_ERROR": "❌ 迁移 {name} 出错：{error}",
        "MIGRATIONS_DB_NONE": "❌ db 不能为 None",
        "MIGRATIONS_BATCH": "📦 已处理 {processed} 个用户...",

        # ---------- Categories ----------
        "CATEGORY_ALIMENTACAO": "食品",
        "CATEGORY_TRANSPORTE": "交通",
        "CATEGORY_MORADIA": "住房",
        "CATEGORY_LAZER": "休闲",
        "CATEGORY_SAUDE": "健康",
        "CATEGORY_EDUCACAO": "教育",
        "CATEGORY_INVESTIMENTOS": "投资",
        "CATEGORY_VESTUARIO": "服装",
        "CATEGORY_BELEZA": "美容",
        "CATEGORY_ELETRONICOS": "电子产品",
        "CATEGORY_CASA": "家居",
        "CATEGORY_CARRO": "汽车",
        "CATEGORY_ECONOMIA": "储蓄",
        "CATEGORY_VIAGEM": "旅行",
        "CATEGORY_RENDA_FIXA": "固定收益",
        "CATEGORY_ACOES": "股票",
        "CATEGORY_FIIS": "REITs",
        "CATEGORY_CRIPTO": "加密货币",
        "CATEGORY_OUTROS": "其他",
        "CATEGORY_INVESTIMENTO": "投资",
        
        # ---------- 🆕 自定义类别 ----------
        "CATEGORY_ALREADY_EXISTS": "该用户已存在同名类别。",
        "CATEGORY_NOT_FOUND": "未找到类别。",
        "CATEGORY_DELETED": "类别已成功删除。",
        "CATEGORY_INVALID_TYPE": "无效的类别类型。请使用：expense、income、goal、investment 或 bill。",
        "CATEGORY_NAME_REQUIRED": "类别名称是必填项。",
        "CATEGORY_INVALID_COLOR": "无效颜色。请使用十六进制格式（#RRGGBB 或 #RGB）。",
    }
}


# ========== FUNÇÕES AUXILIARES ==========

def get_message(key: str, language: str = "pt") -> str:
    """
    Retorna a mensagem traduzida para o idioma solicitado.
    
    Args:
        key (str): Chave da mensagem (ex: "ACHIEVEMENT_NOT_FOUND")
        language (str): Código do idioma (pt, en, es, zh)
    
    Returns:
        str: Mensagem traduzida ou a própria chave se não encontrada
    """
    lang_dict = MESSAGES.get(language, MESSAGES.get("pt", {}))
    return lang_dict.get(key, key)


def get_language_from_request(request: Request) -> str:
    """
    Extrai o idioma do header Accept-Language da requisição.
    
    Args:
        request (Request): Objeto da requisição FastAPI
    
    Returns:
        str: Código do idioma (pt, en, es, zh) ou "pt" como fallback
    """
    accept_language = request.headers.get("Accept-Language", "pt")
    
    if accept_language:
        lang = accept_language.split(",")[0].split("-")[0].strip().lower()
    else:
        lang = "pt"
    
    if lang in ["pt", "en", "es", "zh"]:
        return lang
    
    return "pt"


def get_all_message_keys() -> list:
    """Retorna todas as chaves de mensagens disponíveis."""
    return list(MESSAGES.get("pt", {}).keys())


def get_supported_languages() -> list:
    """Retorna a lista de idiomas suportados."""
    return list(MESSAGES.keys())


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Mensagens organizadas por categoria
# ✅ Suporte a 4 idiomas: pt, en, es, zh
# ✅ Função get_message() com fallback para português
# ✅ Função get_language_from_request() para capturar idioma do header
# ✅ Função get_all_message_keys() para validação
# ✅ Função get_supported_languages() para listar idiomas
# ✅ Fallback seguro: se a chave não for encontrada, retorna a própria chave
# ✅ 🆕 Mensagens para categorias personalizadas adicionadas
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Adicionado chaves IA Service (04/07/2026)
#   - v3: Adicionado chaves SCORE_* (04/07/2026)
#   - v4: Adicionado chaves SCORE_RANGES, EXPENSE_RANGES, EMAIL, AUDIT (04/07/2026)
#   - v5: Adicionado chaves AUTH, BALANCE_CACHE, CURRENCY, DATES, INSTALLMENTS, NOTIFICATIONS (05/07/2026)
#   - v6: Adicionado chaves PROFILE_CACHE_*, ERROR_PROFILE_*, ERROR_PAGINATION_FAILED (06/07/2026)
#   - v7: Adicionado chaves SCHEDULER_*, SCORE_CACHE_*, USER_TOKENS_* (06/07/2026)
#   - v8: Adicionado chaves VALIDATION_* (Validators Extras) (06/07/2026)
#   - v9: Adicionado chaves ERROR_INVALID_ID, ERROR_DATE_FUTURE, NOTIFICATION_*, SCORE_*, MIGRATIONS_*, CATEGORY_* (06/07/2026)
#   - v10: Adicionado chaves CATEGORY_ALREADY_EXISTS, CATEGORY_NOT_FOUND, CATEGORY_DELETED, CATEGORY_INVALID_TYPE, CATEGORY_NAME_REQUIRED, CATEGORY_INVALID_COLOR (10/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO
# 📅 ÚLTIMA ATUALIZAÇÃO: 10/07/2026