"""
Serviço de Envio de Email
Arquivo: backend/app/services/email_service.py

Funcionalidades:
- Envio de emails transacionais (redefinição de senha, exclusão de conta, etc.)
- Suporte a templates em HTML e texto plano
- Múltiplos idiomas (pt, en, es, zh)
- Fallback para mock quando credenciais não configuradas
- Envio assíncrono com asyncio.to_thread()

Principais features:
- 🔧 CORRIGIDO: Async com asyncio.to_thread() (não bloqueia o event loop)
- 🔧 CORRIGIDO: Templates HTML com fallback para texto plano
- 🔧 CORRIGIDO: Integração com i18n (get_message)
- 🔧 CORRIGIDO: Validação de formato de email
- 🔧 CORRIGIDO: URLs configuráveis via .env (FRONTEND_URL)
- 🔧 CORRIGIDO: Timeout SMTP configurável via .env (SMTP_TIMEOUT)
- 🔧 CORRIGIDO: Fallback para subject em caso de chave i18n ausente
- 🔧 CORRIGIDO: Logs estruturados
- 🔧 CORRIGIDO: Fallback para mock quando credenciais não configuradas
"""

import os
import smtplib
import re
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict

from app.utils.logger import setup_logger
from app.utils.i18n import get_message

logger = setup_logger(__name__)


class EmailService:
    """Serviço para envio de emails transacionais."""
    
    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("SMTP_PORT", 587))
        self.username = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.username)
        
        # 🔧 NOVO: URL do frontend configurável
        self.frontend_url = os.getenv("FRONTEND_URL", "https://velorium-frontend.com")
        
        # 🔧 NOVO: Timeout SMTP configurável
        self.smtp_timeout = int(os.getenv("SMTP_TIMEOUT", 30))
        
        self.enabled = bool(self.username and self.password)
        
        if not self.enabled:
            logger.warning("⚠️ Email service desabilitado (credenciais não configuradas)")
        else:
            logger.info(f"✅ Email service inicializado: {self.from_email} via {self.host}:{self.port}")
            logger.info(f"🔗 Frontend URL: {self.frontend_url}")
            logger.info(f"⏱️ SMTP Timeout: {self.smtp_timeout}s")
    
    # ========== VALIDAÇÃO ==========
    
    def _is_valid_email(self, email: str) -> bool:
        """
        Valida formato de email.
        
        Args:
            email: Endereço de email a ser validado
        
        Returns:
            bool: True se o formato for válido
        """
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    # ========== TEMPLATES ==========
    
    def _get_templates(self, language: str, reset_link: str) -> Dict[str, str]:
        """
        Retorna os templates de email no idioma solicitado.
        
        Args:
            language: Código do idioma (pt, en, es, zh)
            reset_link: Link para redefinição de senha
        
        Returns:
            Dict com subject, html e text
        """
        # 🔧 CORRIGIDO: Fallback para subject se chave i18n não existir
        subject = get_message("EMAIL_RESET_SUBJECT", language)
        if subject == "EMAIL_RESET_SUBJECT":
            subject = "Redefinição de Senha - Velorium"
        
        templates = {
            "pt": {
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #6C63FF; margin-top: 0;">🔐 Redefinição de Senha</h2>
                        <p>Olá,</p>
                        <p>Você solicitou a redefinição da sua senha no <strong>Velorium</strong>.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{reset_link}" style="background: #6C63FF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                Redefinir Senha
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">Este link é válido por 15 minutos.</p>
                        <p style="font-size: 14px; color: #666;">Se você não solicitou esta redefinição, ignore este email.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">Atenciosamente,<br>Equipe Velorium</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                🔐 REDEFINIÇÃO DE SENHA - VELORIUM
                
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
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #6C63FF; margin-top: 0;">🔐 Password Reset</h2>
                        <p>Hello,</p>
                        <p>You requested to reset your password on <strong>Velorium</strong>.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{reset_link}" style="background: #6C63FF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                Reset Password
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">This link is valid for 15 minutes.</p>
                        <p style="font-size: 14px; color: #666;">If you didn't request this reset, please ignore this email.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">Best regards,<br>Velorium Team</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                🔐 PASSWORD RESET - VELORIUM
                
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
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #6C63FF; margin-top: 0;">🔐 Restablecimiento de Contraseña</h2>
                        <p>Hola,</p>
                        <p>Solicitaste restablecer tu contraseña en <strong>Velorium</strong>.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{reset_link}" style="background: #6C63FF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                Restablecer Contraseña
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">Este enlace es válido por 15 minutos.</p>
                        <p style="font-size: 14px; color: #666;">Si no solicitaste esto, ignora este correo.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">Saludos,<br>Equipo Velorium</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                🔐 RESTABLECIMIENTO DE CONTRASEÑA - VELORIUM
                
                Hola,
                
                Solicítaste restablecer tu contraseña en Velorium.
                
                Haz clic en el enlace para restablecer tu contraseña:
                {reset_link}
                
                Este enlace es válido por 15 minutos.
                
                Si no solicitaste esto, ignora este correo.
                
                Saludos,
                Equipo Velorium
                """
            },
            "zh": {
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #6C63FF; margin-top: 0;">🔐 重置密码</h2>
                        <p>您好，</p>
                        <p>您请求重置您在 <strong>Velorium</strong> 的密码。</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{reset_link}" style="background: #6C63FF; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                重置密码
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">此链接有效期为15分钟。</p>
                        <p style="font-size: 14px; color: #666;">如果您没有请求重置，请忽略此邮件。</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">此致，<br>Velorium 团队</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                🔐 重置密码 - VELORIUM
                
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
        
        return templates.get(language, templates["pt"])
    
    # ========== ENVIO DE EMAIL ==========
    
    async def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        language: str = "pt"
    ) -> bool:
        """
        Envia email de redefinição de senha.
        
        Args:
            to_email: Email do destinatário
            reset_token: Token de redefinição
            language: Idioma do email (pt, en, es, zh)
        
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self._is_valid_email(to_email):
            logger.warning(f"⚠️ Email inválido: {to_email}")
            return False
        
        # 🔧 CORRIGIDO: Usar FRONTEND_URL do .env
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        if not self.enabled:
            logger.info(f"🔐 [MOCK] Link para redefinir senha: {reset_link}")
            logger.info(f"📧 [MOCK] Email seria enviado para: {to_email}")
            return True
        
        templates = self._get_templates(language, reset_link)
        
        return await self._send_email(
            to_email=to_email,
            subject=templates["subject"],
            html_body=templates["html"],
            text_body=templates["text"]
        )
    
    async def send_delete_confirmation_email(
        self,
        to_email: str,
        user_name: str,
        delete_token: str,
        language: str = "pt"
    ) -> bool:
        """
        Envia email de confirmação de exclusão de conta.
        
        Args:
            to_email: Email do destinatário
            user_name: Nome do usuário
            delete_token: Token de exclusão
            language: Idioma do email (pt, en, es, zh)
        
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self._is_valid_email(to_email):
            logger.warning(f"⚠️ Email inválido: {to_email}")
            return False
        
        # 🔧 CORRIGIDO: Usar FRONTEND_URL do .env
        delete_link = f"{self.frontend_url}/delete-account?token={delete_token}"
        
        # 🔧 CORRIGIDO: Fallback para subject se chave i18n não existir
        subject = get_message("EMAIL_DELETE_SUBJECT", language)
        if subject == "EMAIL_DELETE_SUBJECT":
            subject = "Confirmação de Exclusão de Conta - Velorium"
        
        templates = {
            "pt": {
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #FF4444; margin-top: 0;">⚠️ Confirmação de Exclusão</h2>
                        <p>Olá, <strong>{user_name}</strong>,</p>
                        <p>Você solicitou a exclusão permanente da sua conta no <strong>Velorium</strong>.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{delete_link}" style="background: #FF4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                Confirmar Exclusão
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">Este link é válido por 24 horas.</p>
                        <p style="font-size: 14px; color: #666;">Se você não solicitou esta exclusão, ignore este email.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">Atenciosamente,<br>Equipe Velorium</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                ⚠️ CONFIRMAÇÃO DE EXCLUSÃO - VELORIUM
                
                Olá, {user_name},
                
                Você solicitou a exclusão permanente da sua conta no Velorium.
                
                Clique no link abaixo para confirmar a exclusão:
                {delete_link}
                
                Este link é válido por 24 horas.
                
                Se você não solicitou esta exclusão, ignore este email.
                
                Atenciosamente,
                Equipe Velorium
                """
            },
            "en": {
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #FF4444; margin-top: 0;">⚠️ Delete Confirmation</h2>
                        <p>Hello, <strong>{user_name}</strong>,</p>
                        <p>You requested to permanently delete your account on <strong>Velorium</strong>.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{delete_link}" style="background: #FF4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                Confirm Delete
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">This link is valid for 24 hours.</p>
                        <p style="font-size: 14px; color: #666;">If you didn't request this deletion, please ignore this email.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">Best regards,<br>Velorium Team</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                ⚠️ DELETE CONFIRMATION - VELORIUM
                
                Hello, {user_name},
                
                You requested to permanently delete your account on Velorium.
                
                Click the link below to confirm deletion:
                {delete_link}
                
                This link is valid for 24 hours.
                
                If you didn't request this deletion, please ignore this email.
                
                Best regards,
                Velorium Team
                """
            },
            "es": {
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #FF4444; margin-top: 0;">⚠️ Confirmación de Eliminación</h2>
                        <p>Hola, <strong>{user_name}</strong>,</p>
                        <p>Solicitaste eliminar permanentemente tu cuenta en <strong>Velorium</strong>.</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{delete_link}" style="background: #FF4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                Confirmar Eliminación
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">Este enlace es válido por 24 horas.</p>
                        <p style="font-size: 14px; color: #666;">Si no solicitaste esto, ignora este correo.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">Saludos,<br>Equipo Velorium</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                ⚠️ CONFIRMACIÓN DE ELIMINACIÓN - VELORIUM
                
                Hola, {user_name},
                
                Solicítaste eliminar permanentemente tu cuenta en Velorium.
                
                Haz clic en el enlace para confirmar la eliminación:
                {delete_link}
                
                Este enlace es válido por 24 horas.
                
                Si no solicitaste esto, ignora este correo.
                
                Saludos,
                Equipo Velorium
                """
            },
            "zh": {
                "subject": subject,
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #FF4444; margin-top: 0;">⚠️ 确认删除</h2>
                        <p>您好，<strong>{user_name}</strong>，</p>
                        <p>您请求永久删除您在 <strong>Velorium</strong> 的账户。</p>
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{delete_link}" style="background: #FF4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                                确认删除
                            </a>
                        </p>
                        <p style="font-size: 14px; color: #666;">此链接有效期为24小时。</p>
                        <p style="font-size: 14px; color: #666;">如果您没有请求删除，请忽略此邮件。</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999;">此致，<br>Velorium 团队</p>
                    </div>
                </body>
                </html>
                """,
                "text": f"""
                ⚠️ 确认删除 - VELORIUM
                
                您好，{user_name}，
                
                您请求永久删除您在 Velorium 的账户。
                
                请点击以下链接确认删除：
                {delete_link}
                
                此链接有效期为24小时。
                
                如果您没有请求删除，请忽略此邮件。
                
                此致，
                Velorium 团队
                """
            }
        }
        
        template = templates.get(language, templates["pt"])
        
        if not self.enabled:
            logger.info(f"🔐 [MOCK] Link para excluir conta: {delete_link}")
            logger.info(f"📧 [MOCK] Email seria enviado para: {to_email}")
            return True
        
        return await self._send_email(
            to_email=to_email,
            subject=template["subject"],
            html_body=template["html"],
            text_body=template["text"]
        )
    
    # ========== ENVIO (ASYNC) ==========
    
    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """
        Envia o email via SMTP em uma thread separada.
        🔧 CORRIGIDO: Usa asyncio.to_thread() para não bloquear o event loop.
        """
        return await asyncio.to_thread(
            self._send_email_sync,
            to_email,
            subject,
            html_body,
            text_body
        )
    
    def _send_email_sync(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """
        Versão síncrona do envio de email (roda em thread separada).
        🔧 CORRIGIDO: Timeout configurável via .env.
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            
            part_text = MIMEText(text_body, "plain", "utf-8")
            part_html = MIMEText(html_body, "html", "utf-8")
            
            msg.attach(part_text)
            msg.attach(part_html)
            
            # 🔧 CORRIGIDO: Timeout configurável
            with smtplib.SMTP(self.host, self.port, timeout=self.smtp_timeout) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"✅ Email enviado para: {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ Falha na autenticação SMTP: {e}")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"❌ Destinatário recusado: {e}")
            return False
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"❌ Conexão SMTP perdida: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ Erro SMTP: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email para {to_email}: {e}")
            return False


# ========== SINGLETON ==========
email_service = EmailService()


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Envio assíncrono com asyncio.to_thread()
#   - Templates HTML com fallback para texto plano
#   - Suporte a 4 idiomas (pt, en, es, zh)
#   - Integração com i18n (get_message)
#   - Validação de formato de email
#   - Fallback para mock quando credenciais não configuradas
#   - Logs estruturados
#   - Suporte a redefinição de senha e exclusão de conta
#   - 🔧 CORRIGIDO: FRONTEND_URL configurável via .env
#   - 🔧 CORRIGIDO: SMTP_TIMEOUT configurável via .env
#   - 🔧 CORRIGIDO: Fallback para subject em caso de chave i18n ausente
#   - 🔧 CORRIGIDO: Tratamento específico de erros SMTP
#
# ❌ Não implementado (Pós-MVP):
#   - Rate limiting por email
#   - Fila de emails (processamento assíncrono em background)
#   - Tracking de abertura de emails
#   - Templates em banco de dados
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Async com asyncio.to_thread, HTML templates, i18n, validação (04/07/2026)
#   - v3: FRONTEND_URL configurável, SMTP_TIMEOUT configurável, fallback i18n, tratamento de erros (04/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO