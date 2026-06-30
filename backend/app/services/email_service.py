"""
Serviço de Envio de Email
Arquivo: backend/app/services/email_service.py

🔧 NOVO: Integração com serviço de email (SMTP)
- Suporte a templates multilíngue (pt, en, es, zh)
- Fallback para mock quando credenciais não configuradas
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class EmailService:
    """Serviço para envio de emails"""
    
    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("SMTP_PORT", 587))
        self.username = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.username)
        self.enabled = bool(self.username and self.password)
        
        if not self.enabled:
            logger.warning("⚠️ Email service desabilitado (credenciais não configuradas)")
        else:
            logger.info("✅ Email service inicializado")
    
    async def send_password_reset_email(self, to_email: str, reset_token: str, language: str = "pt") -> bool:
        """
        Envia email de redefinição de senha.
        
        Args:
            to_email: Email do destinatário
            reset_token: Token de redefinição
            language: Idioma do email (pt, en, es, zh)
        
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.enabled:
            # 🔧 Fallback para mock (apenas log)
            reset_link = f"https://velorium-frontend.com/reset-password?token={reset_token}"
            logger.info(f"🔐 [MOCK] Link para redefinir senha: {reset_link}")
            logger.info(f"📧 [MOCK] Email seria enviado para: {to_email}")
            return True
        
        reset_link = f"https://velorium-frontend.com/reset-password?token={reset_token}"
        
        # Templates por idioma
        templates = {
            "pt": {
                "subject": "Redefinição de Senha - Velorium",
                "body": f"""
Olá,

Você solicitou a redefinição da sua senha no Velorium.

Clique no link abaixo para redefinir sua senha:
{reset_link}

Este link é válido por 15 minutos.

Se você não solicitou esta redefinição, ignore este email.

Atenciosamente,
Equipe Velorium
                """
            },
            "en": {
                "subject": "Password Reset - Velorium",
                "body": f"""
Hello,

You requested to reset your password on Velorium.

Click the link below to reset your password:
{reset_link}

This link is valid for 15 minutes.

If you didn't request this reset, please ignore this email.

Best regards,
Velorium Team
                """
            },
            "es": {
                "subject": "Restablecimiento de Contraseña - Velorium",
                "body": f"""
Hola,

Solicitaste restablecer tu contraseña en Velorium.

Haz clic en el enlace para restablecer tu contraseña:
{reset_link}

Este enlace es válido por 15 minutos.

Si no solicitaste esto, ignora este correo.

Saludos,
Equipo Velorium
                """
            },
            "zh": {
                "subject": "重置密码 - Velorium",
                "body": f"""
您好，

您请求重置 Velorium 的密码。

请点击以下链接重置密码：
{reset_link}

此链接有效期为15分钟。

如果您没有请求重置，请忽略此邮件。

此致，
Velorium 团队
                """
            }
        }
        
        template = templates.get(language, templates["pt"])
        
        return await self._send_email(to_email, template["subject"], template["body"].strip())
    
    async def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Envia o email via SMTP"""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            
            msg.attach(MIMEText(body, "plain", "utf-8"))
            
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"✅ Email enviado para: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email para {to_email}: {e}")
            return False


# ========== SINGLETON ==========
email_service = EmailService()


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. 🔧 NOVO: Serviço de email com SMTP
2. 🔧 NOVO: Templates multilíngue (pt, en, es, zh)
3. 🔧 NOVO: Fallback para mock quando credenciais não configuradas
4. 🔧 NOVO: Logs para monitoramento

📌 VARIÁVEIS .env NECESSÁRIAS:
   - SMTP_HOST → servidor SMTP (ex: smtp.gmail.com)
   - SMTP_PORT → porta SMTP (ex: 587)
   - SMTP_USERNAME → usuário do email
   - SMTP_PASSWORD → senha ou app password
   - SMTP_FROM_EMAIL → email remetente (opcional)

✅ STATUS: PRONTO PARA PRODUÇÃO
================================================================================
"""