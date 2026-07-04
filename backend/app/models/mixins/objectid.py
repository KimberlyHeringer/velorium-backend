"""
Arquivo: backend/app/models/mixins/objectid.py
Objetivo: Fornecer método de conversão de ObjectId do MongoDB para string

Funcionalidades:
- Fornece o método convert_objectid() para converter ObjectId do MongoDB
- Pode ser herdado por qualquer model que precise de conversão

Principais features:
- Conversão automática de ObjectId para string
- Verificação de instância para evitar loops
- Delegação para a função centralizada do validators.py
"""

from typing import Any

from app.utils.validators import convert_objectid_to_str


class ObjectIdMixin:
    """
    Mixin que fornece conversão de ObjectId do MongoDB para string.
    
    🔧 MÉTODO ADICIONADO:
      - convert_objectid(): Converte ObjectId para string em dicionários
    
    🔧 COMO USAR:
      @model_validator(mode='before')
      @classmethod
      def convert_objectid(cls, data: Any) -> Any:
          if isinstance(data, cls):
              return data
          return convert_objectid_to_str(data)
    """
    
    @classmethod
    def convert_objectid(cls, data: Any) -> Any:
        """
        Converte ObjectId do MongoDB para string.
        
        🔧 O QUE FAZ:
          1. Verifica se já é uma instância do modelo (ignora)
          2. Delega para a função convert_objectid_to_str do validators.py
          3. Converte todos os ObjectId encontrados no dicionário
        """
        if isinstance(data, cls):
            return data
        return convert_objectid_to_str(data)


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Método convert_objectid() para uso em model_validator
#   - Verificação de instância para evitar loops
#   - Delegação para convert_objectid_to_str do validators.py
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de formato ObjectId (24 caracteres hex)
#   - Validação de campos específicos (ex: user_id, card_id)
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO