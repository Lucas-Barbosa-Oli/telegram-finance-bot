import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

async def parse_expense_text(text: str):
    if not MISTRAL_API_KEY:
        print("MISTRAL_API_KEY not set.")
        return None

    prompt = f"""
    Analise o seguinte texto sobre uma transação financeira e extraia os dados em formato JSON.
    Campos necessários:
    - amount (float): o valor da transação
    - type (string): 'income' para ganho/salário ou 'expense' para gasto/despesa
    - category (string): uma categoria simples (ex: Alimentação, Transporte, Lazer, Salário, etc.)
    - description (string): uma breve descrição do que foi

    Texto: "{text}"

    Responda APENAS o JSON.
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }

    payload = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(MISTRAL_URL, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']
            return json.loads(content)
        except Exception as e:
            print(f"Error parsing with AI: {e}")
            return None
