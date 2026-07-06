"""
Sistema de logging centralizado
Arquivo: backend/app/utils/logger.py

Funcionalidades:
- Configura logs com níveis de severidade
- Controla o que aparece em desenvolvimento vs produção
- Formato padronizado para facilitar leitura e debug
- Logs em arquivo com rotação automática
- Integrado com variável ENVIRONMENT do .env

Principais features:
- 🔧 CORRIGIDO: ENVIRONMENT em vez de PRODUCTION (consistência)
- 🔧 CORRIGIDO: Documentação completa
- 🔧 CORRIGIDO: FileHandler com rotação (10MB, 5 backups)
- 🔧 CORRIGIDO: Criação automática da pasta logs/
- 🔧 CORRIGIDO: Suporte a desenvolvimento e produção
- 🔧 CORRIGIDO: Verificação de nível ao reutilizar logger
- ✅ Configuração por ambiente
- ✅ Níveis de log configuráveis via .env
- ✅ Formato padronizado
- ✅ Evita handlers duplicados
- ✅ Função is_debug_mode()
- ✅ Fallback para console se arquivo falhar

Regra: 2.8 (Logs)

🔧 USO:
    from app.utils.logger import setup_logger
    logger = setup_logger(__name__)
    
    logger.debug("Mensagem de debug")
    logger.info("Mensagem informativa")
    logger.warning("Aviso")
    logger.error("Erro")
    logger.critical("Erro crítico")
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# ============================================================
# CONFIGURAÇÃO POR AMBIENTE (baseado no .env)
# ============================================================

# 🔧 CORRIGIDO: Usa ENVIRONMENT em vez de PRODUCTION
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
PRODUCTION = ENVIRONMENT == "production"

# Define o nível de log baseado no ambiente
# - Produção (ENVIRONMENT=production): apenas WARNING, ERROR, CRITICAL
# - Desenvolvimento (ENVIRONMENT=development): DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING" if PRODUCTION else "DEBUG").upper()

# Mapeamento de string para constante do logging
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ============================================================
# CRIAÇÃO DA PASTA DE LOGS
# ============================================================

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except OSError:
        pass  # Se não conseguir criar, apenas ignora (logs só vão para console)


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def setup_logger(name: str) -> logging.Logger:
    """
    Configura e retorna um logger para o módulo solicitado
    
    🔧 CARACTERÍSTICAS:
    - 🔧 Logs para console (sempre ativo)
    - 🔧 Logs para arquivo com rotação (se possível)
    - 🔧 Nível de log configurável via .env
    - 🔧 Evita handlers duplicados
    - 🔧 Verifica e atualiza nível ao reutilizar logger
    
    Args:
        name: Nome do módulo (geralmente __name__)
    
    Returns:
        logging.Logger: Logger configurado
    
    Exemplo:
        logger = setup_logger(__name__)
        logger.info("Servidor iniciado")
    """
    
    # Cria ou obtém um logger com o nome do módulo
    logger = logging.getLogger(name)
    
    # 🔧 CORRIGIDO: Verifica se o nível está correto antes de retornar
    target_level = LOG_LEVELS.get(LOG_LEVEL, logging.INFO)
    
    # Evita adicionar handlers múltiplas vezes (se já configurado, retorna)
    if logger.handlers:
        # 🔧 NOVO: Atualiza o nível se necessário
        if logger.level != target_level:
            logger.setLevel(target_level)
        return logger
    
    # Define o nível mínimo de log
    logger.setLevel(target_level)
    
    # Formato do log: data - nome - nível - mensagem
    # Exemplo: 2026-05-28 10:30:15 - app.routes.auth - INFO - Login realizado
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ===== Handler para console (terminal) =====
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ===== 🔧 NOVO: Handler para arquivo com rotação =====
    try:
        log_file = os.path.join(LOG_DIR, "velorium.log")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5  # Mantém 5 arquivos de backup
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Se não conseguir criar o arquivo, apenas loga no console
        logger.warning(f"⚠️ Não foi possível criar arquivo de log: {e}")
    
    return logger


# ============================================================
# FUNÇÃO AUXILIAR
# ============================================================

def is_debug_mode() -> bool:
    """Retorna True se estiver em modo DEBUG (logs detalhados)"""
    return LOG_LEVEL == "DEBUG"


# ============================================================
# NOTAS DE IMPLEMENTAÇÃO
# ============================================================

"""
📌 COMO USAR:

1. No início de cada arquivo:
   from app.utils.logger import setup_logger
   logger = setup_logger(__name__)

2. Substituir prints:
   print("Usuário logou")        → logger.info("Usuário logou")
   print(f"Erro: {e}")           → logger.error(f"Erro: {e}")
   print(f"Debug: {data}")       → logger.debug(f"Debug: {data}")

3. Níveis de log:
   - DEBUG: Informações detalhadas (só desenvolvimento)
   - INFO: Confirmação que algo funcionou
   - WARNING: Algo inesperado, mas não quebrou
   - ERROR: Erro que foi tratado
   - CRITICAL: Erro grave que derrubou o sistema

4. Comportamento por ambiente (.env):
   ENVIRONMENT=development → LOG_LEVEL=DEBUG (mostra tudo)
   ENVIRONMENT=production  → LOG_LEVEL=WARNING (só avisos e erros)

5. Arquivos de log:
   - logs/velorium.log (arquivo atual)
   - logs/velorium.log.1, .2, .3, .4, .5 (backups)
   - Cada arquivo tem até 10MB
"""


# ============================================================
# DECISÕES DOCUMENTADAS
# ============================================================
#
# ✅ Configuração por ambiente (ENVIRONMENT)
# ✅ Níveis de log configuráveis via .env
# ✅ Formato padronizado
# ✅ Evita handlers duplicados
# ✅ Função is_debug_mode()
# ✅ Documentação completa
# ✅ 🔧 ENVIRONMENT em vez de PRODUCTION (consistência)
# ✅ 🔧 FileHandler com rotação (10MB, 5 backups)
# ✅ 🔧 Criação automática da pasta logs/
# ✅ 🔧 Suporte a desenvolvimento e produção
# ✅ 🔧 Fallback para console se arquivo não for criado
# ✅ 🔧 Verificação de nível ao reutilizar logger
#
# ❌ Não implementado (Pós-MVP):
#   - Log estruturado (JSON) para ferramentas de monitoramento
#   - Envio de logs para serviços externos (Sentry, DataDog)
#   - Logs com correlation_id para rastreamento de requisições
#
# 📋 CHANGELOG:
#   - v1: Versão inicial
#   - v2: Refatoração - ENVIRONMENT, FileHandler, rotação (05/07/2026)
#   - v3: Correção - Verificação de nível ao reutilizar logger (05/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO