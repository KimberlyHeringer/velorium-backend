import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# ========== FUNÇÃO MODIFICADA: ACEITA SYSTEM MESSAGE E USER MESSAGE SEPARADAS ==========
def obter_resposta_ia(system_message: str, user_message: str) -> str:
    try:
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            stream=False,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Erro ao chamar a API da Groq: {e}")
        return "Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente mais tarde."