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

        # ---------- Autenticação ----------
        "AUTH_INVALID_CREDENTIALS": "E-mail ou senha inválidos",
        "AUTH_EMAIL_ALREADY_EXISTS": "E-mail já cadastrado",
        "AUTH_WEAK_PASSWORD": "Senha muito fraca",
        "AUTH_INVALID_TOKEN": "Token inválido ou expirado",
        "AUTH_TOKEN_REFRESHED": "Token atualizado com sucesso",

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

        # ---------- Transações ----------
        "ERROR_TRANSACTION_NOT_FOUND": "Transação não encontrada",
        "ERROR_CREATE_TRANSACTION_FAILED": "Erro interno ao criar transação",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "Não é possível deletar despesa com parcelas pagas no cartão",
        "SUCCESS_TRANSACTION_DELETED": "Transação deletada com sucesso",
        "TRANSACTION_CREATED": "Transação criada com sucesso",
        "TRANSACTION_UPDATED": "Transação atualizada com sucesso",

        # ---------- Score ----------
        "ERROR_SCORE_CALCULATION_FAILED": "Erro ao calcular score financeiro. Tente novamente mais tarde",
        "ERROR_SCORE_HISTORY_FAILED": "Erro ao buscar histórico de score",
        "SCORE_CALCULATED": "Score calculado com sucesso",
        "SCORE_HISTORY_NOT_FOUND": "Histórico de score não encontrado",

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

        # ---------- Perfil ----------
        "ERROR_PROFILE_NOT_FOUND": "Perfil não encontrado",
        "SUCCESS_PROFILE_UPDATED": "Perfil atualizado com sucesso",
        "ERROR_INVALID_PROFILE_DATA": "Dados do perfil inválidos",

        # ---------- Investimentos ----------
        "ERROR_INVESTMENT_NOT_FOUND": "Investimento não encontrado",
        "ERROR_INVALID_CATEGORY": "Categoria inválida. Use: {categories}",
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

        # ---------- Authentication ----------
        "AUTH_INVALID_CREDENTIALS": "Invalid email or password",
        "AUTH_EMAIL_ALREADY_EXISTS": "Email already registered",
        "AUTH_WEAK_PASSWORD": "Password is too weak",
        "AUTH_INVALID_TOKEN": "Invalid or expired token",
        "AUTH_TOKEN_REFRESHED": "Token refreshed successfully",

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

        # ---------- Transactions ----------
        "ERROR_TRANSACTION_NOT_FOUND": "Transaction not found",
        "ERROR_CREATE_TRANSACTION_FAILED": "Internal error creating transaction",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "Cannot delete expense with paid installments",
        "SUCCESS_TRANSACTION_DELETED": "Transaction deleted successfully",
        "TRANSACTION_CREATED": "Transaction created successfully",
        "TRANSACTION_UPDATED": "Transaction updated successfully",

        # ---------- Score ----------
        "ERROR_SCORE_CALCULATION_FAILED": "Error calculating financial score. Please try again later",
        "ERROR_SCORE_HISTORY_FAILED": "Error fetching score history",
        "SCORE_CALCULATED": "Score calculated successfully",
        "SCORE_HISTORY_NOT_FOUND": "Score history not found",

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
        "ERROR_PROFILE_NOT_FOUND": "Profile not found",
        "SUCCESS_PROFILE_UPDATED": "Profile updated successfully",
        "ERROR_INVALID_PROFILE_DATA": "Invalid profile data",

        # ---------- Investments ----------
        "ERROR_INVESTMENT_NOT_FOUND": "Investment not found",
        "ERROR_INVALID_CATEGORY": "Invalid category. Use: {categories}",
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

        # ---------- Autenticación ----------
        "AUTH_INVALID_CREDENTIALS": "Correo o contraseña inválidos",
        "AUTH_EMAIL_ALREADY_EXISTS": "El correo ya está registrado",
        "AUTH_WEAK_PASSWORD": "La contraseña es demasiado débil",
        "AUTH_INVALID_TOKEN": "Token inválido o expirado",
        "AUTH_TOKEN_REFRESHED": "Token actualizado con éxito",

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

        # ---------- Transacciones ----------
        "ERROR_TRANSACTION_NOT_FOUND": "Transacción no encontrada",
        "ERROR_CREATE_TRANSACTION_FAILED": "Error interno al crear la transacción",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "No se puede eliminar un gasto con cuotas pagadas",
        "SUCCESS_TRANSACTION_DELETED": "Transacción eliminada con éxito",
        "TRANSACTION_CREATED": "Transacción creada con éxito",
        "TRANSACTION_UPDATED": "Transacción actualizada con éxito",

        # ---------- Puntuación ----------
        "ERROR_SCORE_CALCULATION_FAILED": "Error al calcular la puntuación financiera. Intente más tarde",
        "ERROR_SCORE_HISTORY_FAILED": "Error al obtener el historial de puntuación",
        "SCORE_CALCULATED": "Puntuación calculada con éxito",
        "SCORE_HISTORY_NOT_FOUND": "Historial de puntuación no encontrado",

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
        "ERROR_PROFILE_NOT_FOUND": "Perfil no encontrado",
        "SUCCESS_PROFILE_UPDATED": "Perfil actualizado con éxito",
        "ERROR_INVALID_PROFILE_DATA": "Datos de perfil inválidos",

        # ---------- Inversiones ----------
        "ERROR_INVESTMENT_NOT_FOUND": "Inversión no encontrada",
        "ERROR_INVALID_CATEGORY": "Categoría inválida. Use: {categories}",
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

        # ---------- 认证 ----------
        "AUTH_INVALID_CREDENTIALS": "邮箱或密码无效",
        "AUTH_EMAIL_ALREADY_EXISTS": "邮箱已注册",
        "AUTH_WEAK_PASSWORD": "密码太弱",
        "AUTH_INVALID_TOKEN": "令牌无效或已过期",
        "AUTH_TOKEN_REFRESHED": "令牌更新成功",

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

        # ---------- 交易 ----------
        "ERROR_TRANSACTION_NOT_FOUND": "未找到交易",
        "ERROR_CREATE_TRANSACTION_FAILED": "创建交易时内部错误",
        "ERROR_CANNOT_DELETE_PAID_INSTALLMENTS": "无法删除已有已付分期的支出",
        "SUCCESS_TRANSACTION_DELETED": "交易删除成功",
        "TRANSACTION_CREATED": "交易创建成功",
        "TRANSACTION_UPDATED": "交易更新成功",

        # ---------- 评分 ----------
        "ERROR_SCORE_CALCULATION_FAILED": "计算财务评分时出错。请稍后再试",
        "ERROR_SCORE_HISTORY_FAILED": "获取评分历史时出错",
        "SCORE_CALCULATED": "评分计算成功",
        "SCORE_HISTORY_NOT_FOUND": "未找到评分历史",

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
        "ERROR_PROFILE_NOT_FOUND": "未找到个人资料",
        "SUCCESS_PROFILE_UPDATED": "个人资料更新成功",
        "ERROR_INVALID_PROFILE_DATA": "个人资料数据无效",

        # ---------- 投资 ----------
        "ERROR_INVESTMENT_NOT_FOUND": "未找到投资",
        "ERROR_INVALID_CATEGORY": "无效的分类。使用：{categories}",
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

    Exemplo:
        >>> get_message("ACHIEVEMENT_NOT_FOUND", "pt")
        "Conquista não encontrada"

        >>> get_message("ACHIEVEMENT_NOT_FOUND", "en")
        "Achievement not found"
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
# ✅ TODAS as mensagens dos arquivos modificados estão incluídas:
#   - achievements.py ✅
#   - bills.py ✅
#   - bill_installments.py ✅
#   - credit_card_purchases.py ✅
#   - credit_cards.py ✅
#   - goals.py ✅
#   - ia.py ✅
#   - investments.py ✅ (preventivo)
#   - notifications.py ✅ (preventivo)
#   - profile.py ✅ (preventivo)
#   - score.py ✅ (preventivo)
#   - transactions.py ✅ (preventivo)
#   - user.py ✅ (preventivo)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO