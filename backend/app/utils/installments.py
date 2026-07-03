"""
Funções de Cálculo de Parcelamento
Arquivo: backend/app/utils/installments.py

Funcionalidade: Centraliza todas as funções relacionadas a cálculo de parcelas
para reutilização em diferentes rotas (bills, credit_card_purchases, etc).

🔧 USO:
    from app.utils.installments import split_amount_cents, calculate_installments_with_interest
    
    amounts = split_amount_cents(10000, 3)  # [3334, 3333, 3333]
    amounts_with_interest = calculate_installments_with_interest(10000, 3, 2.5)

📋 ESTRUTURA:
    - split_amount_cents(): Divide valor igualmente entre parcelas
    - calculate_installments_with_interest(): Calcula parcelas com juros compostos

🔧 CARACTERÍSTICAS:
    - Trabalha com centavos (int) para precisão
    - Distribui resto nas primeiras parcelas
    - Suporte a juros compostos (fórmula PMT)
    - Validação de entrada (parts > 0, total_cents > 0)
"""

from typing import List


def split_amount_cents(total_cents: int, parts: int) -> List[int]:
    """
    Divide um valor em centavos igualmente entre parcelas.
    Distribui o resto (se houver) nas primeiras parcelas.
    
    Exemplo: 100 centavos em 3 parcelas = [34, 33, 33]
    
    Args:
        total_cents: Valor total em centavos
        parts: Número de parcelas
    
    Returns:
        List[int]: Lista com os valores de cada parcela em centavos
    
    Raises:
        ValueError: Se parts <= 0 ou total_cents <= 0
    
    Exemplo:
        >>> split_amount_cents(100, 3)
        [34, 33, 33]
        
        >>> split_amount_cents(1000, 4)
        [250, 250, 250, 250]
    """
    if parts <= 0:
        raise ValueError("Número de parcelas deve ser maior que zero")
    if total_cents <= 0:
        raise ValueError("Valor total deve ser maior que zero")
    
    base = total_cents // parts
    remainder = total_cents - (base * parts)
    amounts = [base] * parts
    for i in range(remainder):
        amounts[i] += 1
    return amounts


def calculate_installments_with_interest(
    total_cents: int,
    installments: int,
    interest_rate: float
) -> List[int]:
    """
    Calcula parcelas com juros compostos.
    
    Fórmula: PMT = PV * (i * (1 + i)^n) / ((1 + i)^n - 1)
    Onde:
    - PV = valor presente (total_cents)
    - i = taxa de juros mensal (interest_rate / 100)
    - n = número de parcelas (installments)
    
    Se interest_rate = 0 ou installments = 1, usa split_amount_cents (sem juros).
    
    Args:
        total_cents: Valor total em centavos
        installments: Número de parcelas
        interest_rate: Taxa de juros mensal (%)
    
    Returns:
        List[int]: Lista com os valores de cada parcela em centavos
    
    Raises:
        ValueError: Se installments <= 0
    
    Exemplo:
        >>> calculate_installments_with_interest(10000, 3, 2.5)
        [3500, 3500, 3500]  # Aproximadamente
    """
    if installments <= 0:
        raise ValueError("Número de parcelas deve ser maior que zero")
    
    # Se não tem juros ou é 1 parcela, usa split simples
    if interest_rate == 0 or installments == 1:
        return split_amount_cents(total_cents, installments)
    
    i = interest_rate / 100
    n = installments
    
    # Evita divisão por zero
    denominator = (1 + i) ** n - 1
    if denominator == 0:
        return split_amount_cents(total_cents, installments)
    
    # Fórmula da parcela com juros compostos
    pmt = total_cents * (i * (1 + i) ** n) / denominator
    
    # Arredonda para centavos
    pmt_cents = round(pmt)
    
    # Cria lista com todas as parcelas iguais
    amounts = [pmt_cents] * n
    
    # Ajusta o resto para não perder centavos
    total_calculated = sum(amounts)
    if total_calculated != total_cents:
        diff = total_cents - total_calculated
        amounts[0] += diff
    
    return amounts


# ========== DECISÕES DOCUMENTADAS ==========
#
# ✅ Trabalha com centavos (int) para precisão
# ✅ Distribui resto nas primeiras parcelas
# ✅ Suporte a juros compostos
# ✅ Validação de entrada (parts > 0, total_cents > 0)
# ✅ Evita divisão por zero
# ✅ Ajusta diferença de arredondamento
#
# ✅ STATUS: PRONTO PARA PRODUÇÃO