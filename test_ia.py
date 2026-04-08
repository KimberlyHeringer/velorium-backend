import os
from app.services.ia_service import obter_resposta_ia

# Define a chave (se não estiver nas variáveis de ambiente)
os.environ["DEEPSEEK_API_KEY"] = "sua-chave-aqui"

resposta = obter_resposta_ia(
    prompt_context="Você é um assistente de mecânica automotiva.",
    pergunta_usuario="Qual a função do óleo do motor?"
)
print(resposta)