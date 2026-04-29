import datetime
import html
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from utils.ai_parser import parse_expense_text
from utils.reports import generate_expense_pie_chart

# Make the mcp-hub package importable without installing it as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-hub"))

from client import finance_client


router = Router()

MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def format_currency(value: Any) -> str:
    formatted = f"R$ {float(value or 0):,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_signed_currency(value: Any, trans_type: str) -> str:
    sign = "+" if trans_type == "income" else "-"
    return f"{sign}{format_currency(value)}"


def month_label(month: int, year: int) -> str:
    return f"{MONTH_NAMES.get(month, str(month))}/{year}"


def type_label(trans_type: str) -> str:
    return "Ganho" if trans_type == "income" else "Gasto"


def type_emoji(trans_type: str) -> str:
    return "💰" if trans_type == "income" else "💸"


def category_totals(transactions: List[Dict[str, Any]], trans_type: str) -> Dict[str, float]:
    totals: Dict[str, float] = defaultdict(float)
    for item in transactions:
        if item.get("type") != trans_type:
            continue
        category = item.get("category") or "sem categoria"
        totals[str(category)] += float(item.get("amount") or 0)
    return dict(sorted(totals.items(), key=lambda entry: entry[1], reverse=True))


def format_category_lines(totals: Dict[str, float]) -> str:
    if not totals:
        return "<i>nenhum</i>"
    return "\n".join(
        f"• <b>{html.escape(category)}</b>: {format_currency(amount)}"
        for category, amount in totals.items()
    )


async def call_finance_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    async with finance_client() as client:
        return await client.call_tool(name, arguments)


async def get_monthly_summary(user_id: int, now: datetime.datetime) -> Dict[str, Any]:
    return await call_finance_tool(
        "get_monthly_summary",
        {"user_id": user_id, "month": now.month, "year": now.year},
    )


def help_text() -> str:
    return (
        "🤖 <b>Bot Financeiro</b>\n\n"
        "Você pode escrever naturalmente:\n"
        "<code>gastei 50 reais em mercado</code>\n"
        "<code>recebi meu salário de 3000</code>\n\n"
        "Ou usar os comandos:\n"
        "/resumo - totais do mês\n"
        "/extrato - últimos lançamentos\n"
        "/relatorio - categorias do mês\n"
        "/grafico - gráfico dos gastos\n"
        "/ajuda - ver esta mensagem"
    )


@router.message(Command("start", "ajuda"))
async def cmd_help(message: Message):
    await message.answer(help_text(), parse_mode="HTML")


@router.message(Command("resumo"))
async def cmd_summary(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    now = datetime.datetime.now()
    result = await get_monthly_summary(message.from_user.id, now)

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao buscar resumo: {error.get('message', 'Erro desconhecido.')}")
        return

    data = result.get("data", {})
    transactions = data.get("transactions", [])

    if not transactions:
        await message.answer("Ainda não encontrei lançamentos neste mês.")
        return

    text = (
        f"📊 <b>Resumo de {month_label(now.month, now.year)}</b>\n\n"
        f"💰 Ganhos: <b>{format_currency(data.get('total_income'))}</b>\n"
        f"💸 Gastos: <b>{format_currency(data.get('total_expense'))}</b>\n"
        f"⚖️ Saldo: <b>{format_currency(data.get('balance'))}</b>"
    )

    await message.answer(text, parse_mode="HTML")


@router.message(Command("relatorio"))
async def cmd_report(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    now = datetime.datetime.now()
    result = await get_monthly_summary(message.from_user.id, now)

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao gerar relatório: {error.get('message', 'Erro desconhecido.')}")
        return

    data = result.get("data", {})
    transactions = data.get("transactions", [])

    if not transactions:
        await message.answer("Ainda não encontrei lançamentos neste mês.")
        return

    expenses = category_totals(transactions, "expense")
    incomes = category_totals(transactions, "income")

    text = (
        f"📈 <b>Relatório de {month_label(now.month, now.year)}</b>\n\n"
        "💸 <b>Gastos por categoria</b>\n"
        f"{format_category_lines(expenses)}\n\n"
        "💰 <b>Ganhos por categoria</b>\n"
        f"{format_category_lines(incomes)}\n\n"
        f"⚖️ <b>Saldo do mês:</b> {format_currency(data.get('balance'))}"
    )

    await message.answer(text, parse_mode="HTML")


@router.message(Command("grafico"))
async def cmd_chart(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    now = datetime.datetime.now()
    result = await get_monthly_summary(message.from_user.id, now)

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao buscar dados do gráfico: {error.get('message', 'Erro desconhecido.')}")
        return

    data = result.get("data", {})
    transactions = data.get("transactions", [])

    if not transactions:
        await message.answer("Ainda não encontrei lançamentos neste mês.")
        return

    chart_buf = generate_expense_pie_chart(transactions)

    if not chart_buf:
        await message.answer("Ainda não há gastos registrados para gerar o gráfico.")
        return

    expenses = category_totals(transactions, "expense")
    caption = (
        f"💸 Gastos em {month_label(now.month, now.year)}: "
        f"<b>{format_currency(data.get('total_expense'))}</b>\n"
        f"{format_category_lines(expenses)}"
    )

    photo = BufferedInputFile(chart_buf.read(), filename="gastos.png")
    await message.answer_photo(photo, caption=caption, parse_mode="HTML")


@router.message(Command("extrato"))
async def cmd_statement(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    result = await call_finance_tool(
        "get_recent_transactions",
        {"user_id": message.from_user.id, "limit": 15},
    )

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao buscar extrato: {error.get('message', 'Erro desconhecido.')}")
        return

    transactions = result.get("data") or []

    if not transactions:
        await message.answer("Nenhum lançamento encontrado para exibir no extrato.")
        return

    lines = ["🧾 <b>Extrato - últimos lançamentos</b>"]
    for item in transactions:
        trans_type = item.get("type", "")
        date_raw = item.get("created_at", "")
        date_str = date_raw.split("T")[0] if date_raw else "sem data"
        category = html.escape(str(item.get("category") or "sem categoria"))
        amount = format_signed_currency(item.get("amount"), trans_type)
        description = html.escape(str(item.get("description") or "-"))
        lines.append(
            "\n"
            f"{type_emoji(trans_type)} <code>{date_str}</code> "
            f"<b>{category}</b> {amount}\n"
            f"<i>{description}</i>"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(lambda message: bool(message.text and message.text.startswith("/")))
async def unknown_command(message: Message):
    await message.answer("Comando não reconhecido. Use /ajuda para ver as opções.")


@router.message()
async def process_text(message: Message):
    if not message.text:
        return

    wait_msg = await message.answer("Processando sua mensagem...")

    data = await parse_expense_text(message.text)

    if not data:
        await wait_msg.edit_text(
            "Não consegui entender o valor. Tente algo como: "
            "<code>gastei 50 reais em mercado</code>",
            parse_mode="HTML",
        )
        return

    try:
        if message.from_user is None:
            await wait_msg.edit_text("Não consegui identificar seu usuário no Telegram.")
            return

        result = await call_finance_tool(
            "create_transaction",
            {
                "user_id": message.from_user.id,
                "amount": data["amount"],
                "trans_type": data["type"],
                "category": data["category"],
                "description": data.get("description", ""),
            },
        )

        if not result.get("ok"):
            error = result.get("error", {})
            await wait_msg.edit_text(
                f"Erro ao salvar no banco de dados: {error.get('message', 'Erro desconhecido.')}"
            )
            return

        now = datetime.datetime.now()
        summary = await get_monthly_summary(message.from_user.id, now)
        balance = None
        if summary.get("ok"):
            balance = summary.get("data", {}).get("balance")

        trans_type = data["type"]
        text = (
            "✅ <b>Registrado!</b>\n"
            f"{type_emoji(trans_type)} {html.escape(str(data['category']))}: "
            f"<b>{format_signed_currency(data['amount'], trans_type)}</b>\n"
            f"📝 {html.escape(str(data.get('description') or type_label(trans_type)))}"
        )

        if balance is not None:
            text += f"\n\n⚖️ Saldo do mês: <b>{format_currency(balance)}</b>"

        await wait_msg.edit_text(text, parse_mode="HTML")
    except Exception as exc:
        await wait_msg.edit_text(f"Erro ao salvar no banco de dados: {exc}")
