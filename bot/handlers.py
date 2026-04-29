import sys
import os

# ---------------------------------------------------------------------------
# Make the mcp-hub package importable without installing it as a package.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-hub'))

from aiogram import Router
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from utils.ai_parser import parse_expense_text
from utils.reports import generate_expense_pie_chart
import datetime

# mcp-hub tool used by /extrato (Phase 2 migration)
from client import finance_client

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Olá! Eu sou seu assistente financeiro. \n"
        "Você pode me dizer algo como 'Gastei 50 reais em pizza' ou 'Recebi meu salário de 3000' "
        "e eu vou anotar para você!"
    )

@router.message(Command("resumo"))
async def cmd_summary(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    now = datetime.datetime.now()
    async with finance_client() as client:
        result = await client.call_tool(
            "get_monthly_summary",
            {"user_id": message.from_user.id, "month": now.month, "year": now.year}
        )

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao buscar resumo: {error.get('message', 'Erro desconhecido.')}")
        return

    data = result.get("data", {})
    transactions = data.get("transactions", [])

    if not transactions:
        await message.answer("Nenhuma transação encontrada para este mês.")
        return

    total_income = data.get("total_income", 0)
    total_expense = data.get("total_expense", 0)
    balance = data.get("balance", 0)

    text = f"📊 *Resumo de {now.strftime('%B/%Y')}*\n\n"
    text += f"💰 Ganhos: R$ {total_income:.2f}\n"
    text += f"💸 Gastos: R$ {total_expense:.2f}\n"
    text += f"⚖️ Saldo: R$ {balance:.2f}\n"

    await message.answer(text, parse_mode="Markdown")

@router.message(Command("grafico"))
async def cmd_chart(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    now = datetime.datetime.now()
    async with finance_client() as client:
        result = await client.call_tool(
            "get_monthly_summary",
            {"user_id": message.from_user.id, "month": now.month, "year": now.year}
        )

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao buscar dados do gráfico: {error.get('message', 'Erro desconhecido.')}")
        return

    data = result.get("data", {})
    summary = data.get("transactions", [])

    if not summary:
        await message.answer("Nenhuma transação encontrada para este mês.")
        return

    chart_buf = generate_expense_pie_chart(summary)

    if not chart_buf:
        await message.answer("Não há gastos registrados para gerar o gráfico.")
        return

    photo = BufferedInputFile(chart_buf.read(), filename="chart.png")
    await message.answer_photo(photo, caption=f"Distribuição de gastos em {now.strftime('%B/%Y')}")

@router.message(Command("extrato"))
async def cmd_statement(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    # Phase 2: delegate to mcp-hub tool via stdio transport
    async with finance_client() as client:
        result = await client.call_tool(
            "get_recent_transactions",
            {"user_id": message.from_user.id, "limit": 15}
        )

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(
            f"Erro ao buscar extrato: {error.get('message', 'Erro desconhecido.')}"
        )
        return

    transactions = result.get("data") or []

    if not transactions:
        await message.answer("Nenhuma transação encontrada para exibir no extrato.")
        return

    text = "🧾 *Extrato (últimos lançamentos)*\n\n"
    for item in transactions:
        trans_type = item.get("type", "")
        type_emoji = "💰" if trans_type == "income" else "💸"
        date_raw = item.get("created_at", "")
        date_str = date_raw.split("T")[0] if date_raw else "sem data"
        category = item.get("category", "sem categoria")
        amount = float(item.get("amount", 0))
        description = item.get("description", "") or "-"
        text += (
            f"{type_emoji} `{date_str}` | *{category}* | R$ {amount:.2f}\n"
            f"_{description}_\n\n"
        )

    await message.answer(text, parse_mode="Markdown")

@router.message()
async def process_text(message: Message):
    # Ignore commands
    if not message.text:
        return

    if message.text.startswith('/'):
        return

    wait_msg = await message.answer("Processando sua mensagem... 🤔")

    data = await parse_expense_text(message.text)

    if not data:
        await wait_msg.edit_text("Desculpe, não consegui entender os valores. Tente ser mais específico.")
        return

    try:
        if message.from_user is None:
            await wait_msg.edit_text("Não consegui identificar seu usuário no Telegram.")
            return

        async with finance_client() as client:
            result = await client.call_tool(
                "create_transaction",
                {
                    "user_id": message.from_user.id,
                    "amount": data['amount'],
                    "trans_type": data['type'],
                    "category": data['category'],
                    "description": data.get('description', '')
                }
            )

        if not result.get("ok"):
            error = result.get("error", {})
            await wait_msg.edit_text(f"Erro ao salvar no banco de dados: {error.get('message', 'Erro desconhecido.')}")
            return

        type_emoji = "💰" if data['type'] == 'income' else "💸"
        await wait_msg.edit_text(
            f"Registrado com sucesso! {type_emoji}\n\n"
            f"Valor: R$ {data['amount']:.2f}\n"
            f"Categoria: {data['category']}\n"
            f"Descrição: {data.get('description', '')}"
        )
    except Exception as e:
        await wait_msg.edit_text(f"Erro ao salvar no banco de dados: {e}")
