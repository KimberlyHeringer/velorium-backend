"""
Sistema de logging centralizado
Arquivo: backend/app/utils/logger.py

✅ Configura logs com níveis de severidade
✅ Controla o que aparece em desenvolvimento vs produção
✅ Formato padronizado para facilitar leitura e debug
✅ Integrado com variável PRODUCTION do .env

Regra: 2.8 (Logs)
"""

import logging
import os

# ============================================================
# CONFIGURAÇÃO POR AMBIENTE (baseado no .env)
# ============================================================

# Lê a variável PRODUCTION do .env (padrão: false)
PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"

# Define o nível de log baseado no ambiente
# - Produção (PRODUCTION=true): apenas WARNING, ERROR, CRITICAL
# - Desenvolvimento (PRODUCTION=false): DEBUG, INFO, WARNING, ERROR, CRITICAL
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
# FUNÇÃO PRINCIPAL
# ============================================================

def setup_logger(name: str) -> logging.Logger:
    """
    Configura e retorna um logger para o módulo solicitado
    
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
    
    # Evita adicionar handlers múltiplas vezes (se já configurado, retorna)
    if logger.handlers:
        return logger
    
    # Define o nível mínimo de log
    logger.setLevel(LOG_LEVELS.get(LOG_LEVEL, logging.INFO))
    
    # Formato do log: data - nome - nível - mensagem
    # Exemplo: 2026-05-28 10:30:15 - app.routes.auth - INFO - Login realizado
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para console (terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
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
   PRODUCTION=false → LOG_LEVEL=DEBUG (mostra tudo)
   PRODUCTION=true  → LOG_LEVEL=WARNING (só avisos e erros)
"""