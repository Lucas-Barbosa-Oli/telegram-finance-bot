import asyncio
from utils.ai_parser import parse_expense_text
import os

async def main():
    # Mocking environment for testing purposes if key is missing
    if not os.environ.get("MISTRAL_API_KEY"):
        print("MISTRAL_API_KEY not set. Skipping real API call.")
        return

    test_text = "Gastei 50 reais em pizza ontem a noite"
    print(f"Testing with: {test_text}")
    result = await parse_expense_text(test_text)
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
