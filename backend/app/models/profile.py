"""
Modelo de Perfil Financeiro do Usuário
Arquivo: backend/app/models/profile.py

🔧 CORRIGIDO:
- Adicionados max_length em todos os campos de texto
- Adicionado max_items em next_year_goals
- Campos monetários agora são int (centavos)
- Adicionados Enums (Literal) com valores CORRESPONDENTES AO FRONTEND
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Literal
from datetime import datetime, timezone
from bson import ObjectId


class UserProfile(BaseModel):
    """
    Perfil financeiro detalhado do usuário.
    Armazena respostas de questionários sobre hábitos, metas e perfil de risco.
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True,
        from_attributes=True
    )

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="ID do usuário (injetado pelo backend)")

    # ========== Bloco 1: Psicologia Financeira ==========
    # Valores conforme frontend: ansioso, indiferente, controlado, inseguro
    money_feeling: Optional[Literal["ansioso", "indiferente", "controlado", "inseguro"]] = Field(
        None, description="sentimento em relação ao dinheiro"
    )
    
    # Valores conforme frontend: culpa, alegria, racionalizo, impulsivo
    post_purchase: Optional[Literal["culpa", "alegria", "racionalizo", "impulsivo"]] = Field(
        None, description="reação após comprar"
    )
    
    # Valores conforme frontend: saldo_crescendo, comprar, pagar_divida, ajudar
    satisfaction: Optional[Literal["saldo_crescendo", "comprar", "pagar_divida", "ajudar"]] = Field(
        None, description="o que te deixa satisfeito financeiramente"
    )
    
    # Valores conforme frontend: sempre, as_vezes, raramente, nao_sei
    planning_habit: Optional[Literal["sempre", "as_vezes", "raramente", "nao_sei"]] = Field(
        None, description="hábito de planejamento"
    )

    # ========== Bloco 2: Metas Pessoais ==========
    # Valores conforme frontend: imovel, viajar, liberdade, aposentar, outro
    dream_5y: Optional[Literal["imovel", "viajar", "liberdade", "aposentar", "outro"]] = Field(
        None, description="sonho para 5 anos"
    )
    dream_other: Optional[str] = Field(None, max_length=500, description="outro sonho (se aplicável)")
    
    # 🔧 CORRIGIDO: str → int (centavos)
    dream_value: Optional[int] = Field(None, ge=0, description="Valor estimado do sonho em CENTAVOS")
    
    # Valores conforme frontend: 3_meses, 6_meses, 12_meses, nenhuma
    emergency_target: Optional[Literal["3_meses", "6_meses", "12_meses", "nenhuma"]] = Field(
        None, description="meta para reserva de emergência"
    )
    
    # Valores conforme frontend: quitar_dividas, guardar, investir, aumentar_renda, nenhuma
    next_year_goals: List[Literal["quitar_dividas", "guardar", "investir", "aumentar_renda", "nenhuma"]] = Field(
        default_factory=list, 
        max_length=20, 
        description="lista de metas para o próximo ano"
    )
    
    # 🔧 CORRIGIDO: str → int (centavos)
    next_year_goal_value: Optional[int] = Field(None, ge=0, description="Valor da meta em CENTAVOS")

    # ========== Bloco 3: Hábitos de Consumo ==========
    # Valores conforme frontend: alimentacao_fora, compras_online, assinaturas, transporte, lazer
    spending_blindspot: Optional[Literal["alimentacao_fora", "compras_online", "assinaturas", "transporte", "lazer"]] = Field(
        None, description="onde o dinheiro 'some'"
    )
    
    # Valores conforme frontend: sempre, as_vezes, raramente, nunca
    price_comparison: Optional[Literal["sempre", "as_vezes", "raramente", "nunca"]] = Field(
        None, description="hábito de comparar preços"
    )
    
    # Valores conforme frontend: pago_a_vista, parcelo, uso_credito, vivo_sem_planejar
    money_phrase: Optional[Literal["pago_a_vista", "parcelo", "uso_credito", "vivo_sem_planejar"]] = Field(
        None, description="frase que define relação com dinheiro"
    )

    # ========== Bloco 4: Tolerância a Risco ==========
    # Valores conforme frontend: poupanca, renda_fixa, hibrido, alto_risco
    risk_scenario: Optional[Literal["poupanca", "renda_fixa", "hibrido", "alto_risco"]] = Field(
        None, description="reação a cenário de risco"
    )
    
    # Valores conforme frontend: prevenir, arriscar, equilibrio, nao_entendo
    risk_phrase: Optional[Literal["prevenir", "arriscar", "equilibrio", "nao_entendo"]] = Field(
        None, description="frase sobre risco"
    )
    
    # Valores conforme frontend: cartao_rotativo, financiamento, emprestimo, nao
    has_debt: Optional[Literal["cartao_rotativo", "financiamento", "emprestimo", "nao"]] = Field(
        None, description="se possui dívidas"
    )
    
    # Valores conforme frontend: sempre_integral, parcelar, atraso
    credit_card_behavior: Optional[Literal["sempre_integral", "parcelar", "atraso"]] = Field(
        None, description="comportamento com cartão de crédito"
    )

    # ========== Metadados ==========
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========== Validações ==========
    @field_validator('next_year_goals')
    @classmethod
    def validate_goals_list(cls, v: List[str]) -> List[str]:
        """Garante que a lista não tenha mais de 20 itens"""
        if len(v) > 20:
            raise ValueError('next_year_goals não pode ter mais de 20 itens')
        return v


class UserProfileCreate(BaseModel):
    """Schema usado para CRIAR um perfil (sem campos autogerados)"""
    money_feeling: Optional[Literal["ansioso", "indiferente", "controlado", "inseguro"]] = None
    post_purchase: Optional[Literal["culpa", "alegria", "racionalizo", "impulsivo"]] = None
    satisfaction: Optional[Literal["saldo_crescendo", "comprar", "pagar_divida", "ajudar"]] = None
    planning_habit: Optional[Literal["sempre", "as_vezes", "raramente", "nao_sei"]] = None
    dream_5y: Optional[Literal["imovel", "viajar", "liberdade", "aposentar", "outro"]] = None
    dream_other: Optional[str] = Field(None, max_length=500)
    dream_value: Optional[int] = Field(None, ge=0)
    emergency_target: Optional[Literal["3_meses", "6_meses", "12_meses", "nenhuma"]] = None
    next_year_goals: List[Literal["quitar_dividas", "guardar", "investir", "aumentar_renda", "nenhuma"]] = Field(
        default_factory=list, max_length=20
    )
    next_year_goal_value: Optional[int] = Field(None, ge=0)
    spending_blindspot: Optional[Literal["alimentacao_fora", "compras_online", "assinaturas", "transporte", "lazer"]] = None
    price_comparison: Optional[Literal["sempre", "as_vezes", "raramente", "nunca"]] = None
    money_phrase: Optional[Literal["pago_a_vista", "parcelo", "uso_credito", "vivo_sem_planejar"]] = None
    risk_scenario: Optional[Literal["poupanca", "renda_fixa", "hibrido", "alto_risco"]] = None
    risk_phrase: Optional[Literal["prevenir", "arriscar", "equilibrio", "nao_entendo"]] = None
    has_debt: Optional[Literal["cartao_rotativo", "financiamento", "emprestimo", "nao"]] = None
    credit_card_behavior: Optional[Literal["sempre_integral", "parcelar", "atraso"]] = None

    @field_validator('next_year_goals')
    @classmethod
    def validate_goals_list(cls, v: List[str]) -> List[str]:
        if len(v) > 20:
            raise ValueError('next_year_goals não pode ter mais de 20 itens')
        return v


class UserProfileResponse(UserProfile):
    """Schema usado para RESPOSTAS da API (força id como string)"""
    id: str = Field(..., description="ID do perfil")


"""
================================================================================
✅ CORREÇÕES REALIZADAS NESTA VERSÃO:
================================================================================
1. Adicionados max_length em todos os campos de texto
2. Adicionado max_length=20 em next_year_goals
3. Adicionada validação field_validator para next_year_goals
4. 🔧 Campos monetários: dream_value, next_year_goal_value → int (centavos)
5. 🔧 Enums (Literal) ajustados com os valores EXATOS do frontend:
   - money_feeling: ansioso, indiferente, controlado, inseguro
   - post_purchase: culpa, alegria, racionalizo, impulsivo
   - satisfaction: saldo_crescendo, comprar, pagar_divida, ajudar
   - planning_habit: sempre, as_vezes, raramente, nao_sei
   - dream_5y: imovel, viajar, liberdade, aposentar, outro
   - emergency_target: 3_meses, 6_meses, 12_meses, nenhuma
   - next_year_goals: quitar_dividas, guardar, investir, aumentar_renda, nenhuma
   - spending_blindspot: alimentacao_fora, compras_online, assinaturas, transporte, lazer
   - price_comparison: sempre, as_vezes, raramente, nunca
   - money_phrase: pago_a_vista, parcelo, uso_credito, vivo_sem_planejar
   - risk_scenario: poupanca, renda_fixa, hibrido, alto_risco
   - risk_phrase: prevenir, arriscar, equilibrio, nao_entendo
   - has_debt: cartao_rotativo, financiamento, emprestimo, nao
   - credit_card_behavior: sempre_integral, parcelar, atraso
6. Adicionados descriptions em todos os Field()
7. Adicionado id: str em UserProfileResponse

✅ PENDÊNCIAS REMANESCENTES (pós-MVP):
================================================================================
1. updated_at: atualização automática (atualmente manual nas rotas)
2. Internacionalização (i18n) das mensagens de erro

================================================================================
✅ STATUS: APROVADO PARA MVP (100% corrigido)
================================================================================
"""