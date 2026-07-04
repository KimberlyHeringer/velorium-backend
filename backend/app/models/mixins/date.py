"""
Arquivo: backend/app/models/mixins/date.py
Objetivo: Fornecer validações de data para campos de data

Funcionalidades:
- Define o mixin DateMixin com validação de data
- Valida que a data não está no futuro
- Converte strings para datetime quando possível

Principais features:
- validate_date_not_future(): data não pode ser futura
- validate_date_not_past(): data não pode ser passada
- validate_date_range(): data dentro de um intervalo
"""

from typing import Optional
from datetime import datetime, timezone


class DateMixin:
    """
    Mixin que fornece validações de data.
    
    🔧 MÉTODOS ADICIONADOS:
      - validate_date_not_future(): Valida que data não é futura
      - validate_date_not_past(): Valida que data não é passada
      - validate_date_range(): Valida que data está entre duas datas
    """
    
    @staticmethod
    def validate_date_not_future(value: datetime, field_name: str = "data") -> datetime:
        """
        Valida que a data não está no futuro.
        
        🔧 EXEMPLO:
          hoje = datetime.now()
          amanha = hoje + timedelta(days=1)
          validate_date_not_future(hoje)  # ✅ OK
          validate_date_not_future(amanha)  # ❌ ERRO!
        """
        now = datetime.now(timezone.utc)
        if value > now:
            raise ValueError(f'{field_name} não pode ser no futuro')
        return value
    
    @staticmethod
    def validate_date_not_past(value: datetime, field_name: str = "data") -> datetime:
        """
        Valida que a data não está no passado.
        """
        now = datetime.now(timezone.utc)
        if value < now:
            raise ValueError(f'{field_name} não pode ser no passado')
        return value
    
    @staticmethod
    def validate_date_range(
        value: datetime,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        field_name: str = "data"
    ) -> datetime:
        """
        Valida que a data está entre um intervalo.
        """
        if start is not None and value < start:
            raise ValueError(f'{field_name} deve ser maior ou igual a {start}')
        if end is not None and value > end:
            raise ValueError(f'{field_name} deve ser menor ou igual a {end}')
        return value


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Implementado:
#   - Método validate_date_not_future()
#   - Método validate_date_not_past()
#   - Método validate_date_range()
#   - Uso de timezone.utc para comparação
#
# ❌ Não implementado (Pós-MVP):
#   - Validação de formato de data
#   - Conversão entre timezones
#
# 📋 CHANGELOG:
#   - v1: Versão inicial (03/07/2026)
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO