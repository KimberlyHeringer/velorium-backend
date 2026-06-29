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
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "Tipo de conquista inválido",
        "ERROR_INVALID_MONTH": "Mês deve ser entre 1 e 12",
        "ERROR_INVALID_YEAR": "Ano deve ser entre 1900 e 2100",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "Descrição não pode estar vazia",
        "ERROR_ACHIEVEMENT_ALREADY_EXISTS": "Conquista já existe para este usuário",
        
        # ---------- Contas a pagar (Bills) ----------
        "BILL_NOT_FOUND": "Conta não encontrada",
        "BILL_NO_DATA_TO_UPDATE": "Nenhum dado para atualizar",
        "BILL_CREATED": "Conta criada com sucesso",
        "BILL_UPDATED": "Conta atualizada com sucesso",
        "BILL_DELETED": "Conta removida com sucesso",
        "BILL_ALREADY_PAID": "Conta já está paga",
        "BILL_PAYMENT_FAILED": "Erro ao processar pagamento",
        
        # ---------- Parcelas (Bill Installments) ----------
        "INSTALLMENT_NOT_FOUND": "Parcela não encontrada",
        "INSTALLMENT_ALREADY_PAID": "Parcela já está paga",
        "INSTALLMENT_PAID_SUCCESS": "Parcela paga com sucesso",
        "INSTALLMENTS_ALL_PAID": "Todas as parcelas foram pagas",
        
        # ---------- Cartões de Crédito ----------
        "CARD_NOT_FOUND": "Cartão não encontrado",
        "CARD_LIMIT_EXCEEDED": "Limite do cartão excedido",
        "CARD_INVALID_CLOSING_DAY": "Dia de fechamento inválido",
        "CARD_INVALID_DUE_DAY": "Dia de vencimento inválido",
        "CARD_CREATED": "Cartão criado com sucesso",
        "CARD_UPDATED": "Cartão atualizado com sucesso",
        "CARD_DELETED": "Cartão removido com sucesso",
        
        # ---------- Compras Parceladas ----------
        "PURCHASE_NOT_FOUND": "Compra não encontrada",
        "PURCHASE_CREATED": "Compra criada com sucesso",
        "PURCHASE_UPDATED": "Compra atualizada com sucesso",
        "PURCHASE_DELETED": "Compra removida com sucesso",
        
        # ---------- Metas (Goals) ----------
        "GOAL_NOT_FOUND": "Meta não encontrada",
        "GOAL_CREATED": "Meta criada com sucesso",
        "GOAL_UPDATED": "Meta atualizada com sucesso",
        "GOAL_DELETED": "Meta removida com sucesso",
        "GOAL_COMPLETED": "Meta concluída! Parabéns!",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "Valor atual não pode ser maior que o valor alvo",
        
        # ---------- Transações ----------
        "TRANSACTION_NOT_FOUND": "Transação não encontrada",
        "TRANSACTION_CREATED": "Transação criada com sucesso",
        "TRANSACTION_UPDATED": "Transação atualizada com sucesso",
        "TRANSACTION_DELETED": "Transação removida com sucesso",
        
        # ---------- Score ----------
        "SCORE_CALCULATED": "Score calculado com sucesso",
        "SCORE_HISTORY_NOT_FOUND": "Histórico de score não encontrado",
        
        # ---------- IA ----------
        "IA_ERROR": "Erro ao processar solicitação da IA",
        "IA_TIMEOUT": "IA demorou muito para responder",
        
        # ---------- Notificações ----------
        "NOTIFICATION_SENT": "Notificação enviada com sucesso",
        "NOTIFICATION_FAILED": "Falha ao enviar notificação",
        
        # ---------- Rate Limiting ----------
        "RATE_LIMIT_EXCEEDED": "Muitas requisições. Tente novamente mais tarde",
        
        # ---------- Perfil ----------
        "PROFILE_NOT_FOUND": "Perfil não encontrado",
        "PROFILE_UPDATED": "Perfil atualizado com sucesso",
        "ERROR_INVALID_PROFILE_DATA": "Dados do perfil inválidos",
        
        # ---------- Investimentos ----------
        "INVESTMENT_NOT_FOUND": "Investimento não encontrado",
        "INVESTMENT_CREATED": "Investimento criado com sucesso",
        "INVESTMENT_UPDATED": "Investimento atualizado com sucesso",
        "INVESTMENT_DELETED": "Investimento removido com sucesso",
        
        # ---------- Usuário ----------
        "USER_NOT_FOUND": "Usuário não encontrado",
        "USER_UPDATED": "Usuário atualizado com sucesso",
        "USER_DELETED": "Usuário removido com sucesso",
        
        # ---------- Conflito ----------
        "ERROR_CONFLICT": "Conflito - recurso já existe",
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
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "Invalid achievement type",
        "ERROR_INVALID_MONTH": "Month must be between 1 and 12",
        "ERROR_INVALID_YEAR": "Year must be between 1900 and 2100",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "Description cannot be empty",
        "ERROR_ACHIEVEMENT_ALREADY_EXISTS": "Achievement already exists for this user",
        
        # ---------- Bills ----------
        "BILL_NOT_FOUND": "Bill not found",
        "BILL_NO_DATA_TO_UPDATE": "No data to update",
        "BILL_CREATED": "Bill created successfully",
        "BILL_UPDATED": "Bill updated successfully",
        "BILL_DELETED": "Bill deleted successfully",
        "BILL_ALREADY_PAID": "Bill is already paid",
        "BILL_PAYMENT_FAILED": "Failed to process payment",
        
        # ---------- Installments ----------
        "INSTALLMENT_NOT_FOUND": "Installment not found",
        "INSTALLMENT_ALREADY_PAID": "Installment is already paid",
        "INSTALLMENT_PAID_SUCCESS": "Installment paid successfully",
        "INSTALLMENTS_ALL_PAID": "All installments have been paid",
        
        # ---------- Credit Cards ----------
        "CARD_NOT_FOUND": "Card not found",
        "CARD_LIMIT_EXCEEDED": "Card limit exceeded",
        "CARD_INVALID_CLOSING_DAY": "Invalid closing day",
        "CARD_INVALID_DUE_DAY": "Invalid due day",
        "CARD_CREATED": "Card created successfully",
        "CARD_UPDATED": "Card updated successfully",
        "CARD_DELETED": "Card deleted successfully",
        
        # ---------- Purchases ----------
        "PURCHASE_NOT_FOUND": "Purchase not found",
        "PURCHASE_CREATED": "Purchase created successfully",
        "PURCHASE_UPDATED": "Purchase updated successfully",
        "PURCHASE_DELETED": "Purchase deleted successfully",
        
        # ---------- Goals ----------
        "GOAL_NOT_FOUND": "Goal not found",
        "GOAL_CREATED": "Goal created successfully",
        "GOAL_UPDATED": "Goal updated successfully",
        "GOAL_DELETED": "Goal deleted successfully",
        "GOAL_COMPLETED": "Goal completed! Congratulations!",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "Current value cannot exceed target value",
        
        # ---------- Transactions ----------
        "TRANSACTION_NOT_FOUND": "Transaction not found",
        "TRANSACTION_CREATED": "Transaction created successfully",
        "TRANSACTION_UPDATED": "Transaction updated successfully",
        "TRANSACTION_DELETED": "Transaction deleted successfully",
        
        # ---------- Score ----------
        "SCORE_CALCULATED": "Score calculated successfully",
        "SCORE_HISTORY_NOT_FOUND": "Score history not found",
        
        # ---------- AI ----------
        "IA_ERROR": "Error processing AI request",
        "IA_TIMEOUT": "AI took too long to respond",
        
        # ---------- Notifications ----------
        "NOTIFICATION_SENT": "Notification sent successfully",
        "NOTIFICATION_FAILED": "Failed to send notification",
        
        # ---------- Rate Limiting ----------
        "RATE_LIMIT_EXCEEDED": "Too many requests. Please try again later",
        
        # ---------- Profile ----------
        "PROFILE_NOT_FOUND": "Profile not found",
        "PROFILE_UPDATED": "Profile updated successfully",
        "ERROR_INVALID_PROFILE_DATA": "Invalid profile data",
        
        # ---------- Investments ----------
        "INVESTMENT_NOT_FOUND": "Investment not found",
        "INVESTMENT_CREATED": "Investment created successfully",
        "INVESTMENT_UPDATED": "Investment updated successfully",
        "INVESTMENT_DELETED": "Investment deleted successfully",
        
        # ---------- User ----------
        "USER_NOT_FOUND": "User not found",
        "USER_UPDATED": "User updated successfully",
        "USER_DELETED": "User deleted successfully",
        
        # ---------- Conflict ----------
        "ERROR_CONFLICT": "Conflict - resource already exists",
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
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "Tipo de logro inválido",
        "ERROR_INVALID_MONTH": "El mes debe estar entre 1 y 12",
        "ERROR_INVALID_YEAR": "El año debe estar entre 1900 y 2100",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "La descripción no puede estar vacía",
        "ERROR_ACHIEVEMENT_ALREADY_EXISTS": "El logro ya existe para este usuario",
        
        # ---------- Cuentas ----------
        "BILL_NOT_FOUND": "Cuenta no encontrada",
        "BILL_NO_DATA_TO_UPDATE": "No hay datos para actualizar",
        "BILL_CREATED": "Cuenta creada con éxito",
        "BILL_UPDATED": "Cuenta actualizada con éxito",
        "BILL_DELETED": "Cuenta eliminada con éxito",
        "BILL_ALREADY_PAID": "La cuenta ya está pagada",
        "BILL_PAYMENT_FAILED": "Error al procesar el pago",
        
        # ---------- Cuotas ----------
        "INSTALLMENT_NOT_FOUND": "Cuota no encontrada",
        "INSTALLMENT_ALREADY_PAID": "La cuota ya está pagada",
        "INSTALLMENT_PAID_SUCCESS": "Cuota pagada con éxito",
        "INSTALLMENTS_ALL_PAID": "Todas las cuotas han sido pagadas",
        
        # ---------- Tarjetas ----------
        "CARD_NOT_FOUND": "Tarjeta no encontrada",
        "CARD_LIMIT_EXCEEDED": "Límite de tarjeta excedido",
        "CARD_INVALID_CLOSING_DAY": "Día de cierre inválido",
        "CARD_INVALID_DUE_DAY": "Día de vencimiento inválido",
        "CARD_CREATED": "Tarjeta creada con éxito",
        "CARD_UPDATED": "Tarjeta actualizada con éxito",
        "CARD_DELETED": "Tarjeta eliminada con éxito",
        
        # ---------- Compras ----------
        "PURCHASE_NOT_FOUND": "Compra no encontrada",
        "PURCHASE_CREATED": "Compra creada con éxito",
        "PURCHASE_UPDATED": "Compra actualizada con éxito",
        "PURCHASE_DELETED": "Compra eliminada con éxito",
        
        # ---------- Metas ----------
        "GOAL_NOT_FOUND": "Meta no encontrada",
        "GOAL_CREATED": "Meta creada con éxito",
        "GOAL_UPDATED": "Meta actualizada con éxito",
        "GOAL_DELETED": "Meta eliminada con éxito",
        "GOAL_COMPLETED": "Meta completada! Felicitaciones",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "El valor actual no puede exceder el valor objetivo",
        
        # ---------- Transacciones ----------
        "TRANSACTION_NOT_FOUND": "Transacción no encontrada",
        "TRANSACTION_CREATED": "Transacción creada con éxito",
        "TRANSACTION_UPDATED": "Transacción actualizada con éxito",
        "TRANSACTION_DELETED": "Transacción eliminada con éxito",
        
        # ---------- Puntuación ----------
        "SCORE_CALCULATED": "Puntuación calculada con éxito",
        "SCORE_HISTORY_NOT_FOUND": "Historial de puntuación no encontrado",
        
        # ---------- IA ----------
        "IA_ERROR": "Error al procesar la solicitud de IA",
        "IA_TIMEOUT": "La IA tardó demasiado en responder",
        
        # ---------- Notificaciones ----------
        "NOTIFICATION_SENT": "Notificación enviada con éxito",
        "NOTIFICATION_FAILED": "Error al enviar la notificación",
        
        # ---------- Rate Limiting ----------
        "RATE_LIMIT_EXCEEDED": "Demasiadas solicitudes. Intente más tarde",
        
        # ---------- Perfil ----------
        "PROFILE_NOT_FOUND": "Perfil no encontrado",
        "PROFILE_UPDATED": "Perfil actualizado con éxito",
        "ERROR_INVALID_PROFILE_DATA": "Datos de perfil inválidos",
        
        # ---------- Inversiones ----------
        "INVESTMENT_NOT_FOUND": "Inversión no encontrada",
        "INVESTMENT_CREATED": "Inversión creada con éxito",
        "INVESTMENT_UPDATED": "Inversión actualizada con éxito",
        "INVESTMENT_DELETED": "Inversión eliminada con éxito",
        
        # ---------- Usuario ----------
        "USER_NOT_FOUND": "Usuario no encontrado",
        "USER_UPDATED": "Usuario actualizado con éxito",
        "USER_DELETED": "Usuario eliminado con éxito",
        
        # ---------- Conflicto ----------
        "ERROR_CONFLICT": "Conflicto - el recurso ya existe",
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
        "ERROR_INVALID_ACHIEVEMENT_TYPE": "无效的成就类型",
        "ERROR_INVALID_MONTH": "月份必须在1到12之间",
        "ERROR_INVALID_YEAR": "年份必须在1900到2100之间",
        "ERROR_ACHIEVEMENT_DESCRIPTION_EMPTY": "描述不能为空",
        "ERROR_ACHIEVEMENT_ALREADY_EXISTS": "该用户的成就已存在",
        
        # ---------- 账单 ----------
        "BILL_NOT_FOUND": "未找到账单",
        "BILL_NO_DATA_TO_UPDATE": "没有数据可更新",
        "BILL_CREATED": "账单创建成功",
        "BILL_UPDATED": "账单更新成功",
        "BILL_DELETED": "账单删除成功",
        "BILL_ALREADY_PAID": "账单已支付",
        "BILL_PAYMENT_FAILED": "处理支付失败",
        
        # ---------- 分期 ----------
        "INSTALLMENT_NOT_FOUND": "未找到分期",
        "INSTALLMENT_ALREADY_PAID": "分期已支付",
        "INSTALLMENT_PAID_SUCCESS": "分期支付成功",
        "INSTALLMENTS_ALL_PAID": "所有分期已支付",
        
        # ---------- 信用卡 ----------
        "CARD_NOT_FOUND": "未找到卡片",
        "CARD_LIMIT_EXCEEDED": "超出卡片限额",
        "CARD_INVALID_CLOSING_DAY": "无效的账单日",
        "CARD_INVALID_DUE_DAY": "无效的还款日",
        "CARD_CREATED": "卡片创建成功",
        "CARD_UPDATED": "卡片更新成功",
        "CARD_DELETED": "卡片删除成功",
        
        # ---------- 购买 ----------
        "PURCHASE_NOT_FOUND": "未找到购买记录",
        "PURCHASE_CREATED": "购买记录创建成功",
        "PURCHASE_UPDATED": "购买记录更新成功",
        "PURCHASE_DELETED": "购买记录删除成功",
        
        # ---------- 目标 ----------
        "GOAL_NOT_FOUND": "未找到目标",
        "GOAL_CREATED": "目标创建成功",
        "GOAL_UPDATED": "目标更新成功",
        "GOAL_DELETED": "目标删除成功",
        "GOAL_COMPLETED": "目标完成！恭喜！",
        "ERROR_GOAL_CURRENT_EXCEEDS_TARGET": "当前值不能超过目标值",
        
        # ---------- 交易 ----------
        "TRANSACTION_NOT_FOUND": "未找到交易",
        "TRANSACTION_CREATED": "交易创建成功",
        "TRANSACTION_UPDATED": "交易更新成功",
        "TRANSACTION_DELETED": "交易删除成功",
        
        # ---------- 评分 ----------
        "SCORE_CALCULATED": "评分计算成功",
        "SCORE_HISTORY_NOT_FOUND": "未找到评分历史",
        
        # ---------- AI ----------
        "IA_ERROR": "处理AI请求时出错",
        "IA_TIMEOUT": "AI响应超时",
        
        # ---------- 通知 ----------
        "NOTIFICATION_SENT": "通知发送成功",
        "NOTIFICATION_FAILED": "发送通知失败",
        
        # ---------- 限流 ----------
        "RATE_LIMIT_EXCEEDED": "请求过多，请稍后再试",
        
        # ---------- 个人资料 ----------
        "PROFILE_NOT_FOUND": "未找到个人资料",
        "PROFILE_UPDATED": "个人资料更新成功",
        "ERROR_INVALID_PROFILE_DATA": "个人资料数据无效",
        
        # ---------- 投资 ----------
        "INVESTMENT_NOT_FOUND": "未找到投资",
        "INVESTMENT_CREATED": "投资创建成功",
        "INVESTMENT_UPDATED": "投资更新成功",
        "INVESTMENT_DELETED": "投资删除成功",
        
        # ---------- 用户 ----------
        "USER_NOT_FOUND": "未找到用户",
        "USER_UPDATED": "用户更新成功",
        "USER_DELETED": "用户删除成功",
        
        # ---------- 冲突 ----------
        "ERROR_CONFLICT": "冲突 - 资源已存在",
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
    # Busca o dicionário do idioma, fallback para português
    lang_dict = MESSAGES.get(language, MESSAGES.get("pt", {}))
    
    # Retorna a mensagem ou a própria chave se não encontrada
    return lang_dict.get(key, key)


def get_language_from_request(request: Request) -> str:
    """
    Extrai o idioma do header Accept-Language da requisição.
    
    Args:
        request (Request): Objeto da requisição FastAPI
    
    Returns:
        str: Código do idioma (pt, en, es, zh) ou "pt" como fallback
    
    Exemplo:
        Header: "Accept-Language: en-US,pt;q=0.9,es;q=0.8"
        Retorno: "en"
        
        Header: "Accept-Language: pt-BR,en;q=0.9"
        Retorno: "pt"
    """
    accept_language = request.headers.get("Accept-Language", "pt")
    
    # Pega o primeiro idioma e remove região (ex: en-US → en)
    if accept_language:
        lang = accept_language.split(",")[0].split("-")[0].strip().lower()
    else:
        lang = "pt"
    
    # Valida se é um idioma suportado
    if lang in ["pt", "en", "es", "zh"]:
        return lang
    
    # Fallback para português
    return "pt"


def get_all_message_keys() -> list:
    """
    Retorna todas as chaves de mensagens disponíveis.
    
    Returns:
        list: Lista de chaves de mensagens
    
    Exemplo:
        >>> get_all_message_keys()
        ['SUCCESS_CREATED', 'SUCCESS_UPDATED', ...]
    """
    return list(MESSAGES.get("pt", {}).keys())


def get_supported_languages() -> list:
    """
    Retorna a lista de idiomas suportados.
    
    Returns:
        list: Lista de códigos de idioma
        
    Exemplo:
        >>> get_supported_languages()
        ['pt', 'en', 'es', 'zh']
    """
    return list(MESSAGES.keys())


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Mensagens organizadas por categoria (Sucesso, Erros, Autenticação, etc.)
# ✅ Suporte a 4 idiomas: pt, en, es, zh
# ✅ Função get_message() com fallback para português
# ✅ Função get_language_from_request() para capturar idioma do header
# ✅ Função get_all_message_keys() para validação
# ✅ Função get_supported_languages() para listar idiomas
# ✅ Fallback seguro: se a chave não for encontrada, retorna a própria chave
#
# ⏳ PENDÊNCIAS PÓS-MVP:
# - Adicionar mais idiomas (ex: francês, alemão)
# - Suporte a pluralização
# - Suporte a variáveis nas mensagens (ex: "Usuário {name} criado")
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO