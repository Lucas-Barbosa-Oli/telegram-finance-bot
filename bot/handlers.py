import datetime
import html
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

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


def status_label(status: str) -> str:
    return "✅ Confirmado" if status == "confirmed" else "⏳ Planejado"


def status_emoji(status: str) -> str:
    return "✅" if status == "confirmed" else "⏳"


def parse_confirmation_mode(text: str) -> str:
    lowered = text.lower()
    planned_hints = ("vou ", "a pagar", "previsto", "planejado", "pendente")
    return "planned" if any(hint in lowered for hint in planned_hints) else "confirmed"


def transaction_actions_keyboard(transaction_id: int, status: str) -> InlineKeyboardMarkup:
    target_status = "planned" if status == "confirmed" else "confirmed"
    label = "Desconfirmar" if target_status == "planned" else "Confirmar pagamento"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"tx_status:{transaction_id}:{target_status}",
                ),
                InlineKeyboardButton(
                    text="Cancelar",
                    callback_data=f"tx_delete:{transaction_id}",
                ),
            ]
        ]
    )


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
        {"user_id": user_id, "month": now.month, "year": now.year, "include_planned": False},
    )


def build_transaction_text(item: Dict[str, Any]) -> str:
    trans_type = item.get("type", "")
    status = str(item.get("status") or "confirmed")
    date_raw = item.get("created_at", "")
    date_str = date_raw.split("T")[0] if date_raw else "sem data"
    transaction_id = item.get("id")
    category = html.escape(str(item.get("category") or "sem categoria"))
    amount = format_signed_currency(item.get("amount"), trans_type)
    description = html.escape(str(item.get("description") or "-"))
    return (
        f"🆔 <code>{transaction_id}</code>  {type_emoji(trans_type)} <code>{date_str}</code>\n"
        f"<b>{category}</b> {amount}\n"
        f"{status_emoji(status)} <i>{status_label(status)}</i>\n"
        f"<i>{description}</i>"
    )


def help_text() -> str:
    return (
        "🤖 <b>Bot Financeiro</b>\n\n"
        "Você pode escrever naturalmente:\n"
        "<code>gastei 50 reais em mercado</code>\n"
        "<code>recebi meu salário de 3000</code>\n\n"
        "Comandos disponíveis:\n"
        "<code>┌ /resumo ............ totais do mês</code>\n"
        "<code>├ /extrato ........... últimos lançamentos (com botão)</code>\n"
        "<code>├ /pendentes ......... lançamentos planejados</code>\n"
        "<code>├ /contas ............ visão separada do mês</code>\n"
        "<code>├ /relatorio ......... categorias do mês</code>\n"
        "<code>├ /grafico ........... gráfico dos gastos</code>\n"
        "<code>├ /confirmar &lt;id&gt; ... marca como confirmado</code>\n"
        "<code>├ /desconfirmar &lt;id&gt; marca como planejado</code>\n"
        "<code>├ /cancelar &lt;id&gt; ... remove um lançamento</code>\n"
        "<code>└ /ajuda ............. ver esta mensagem</code>"
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
        "🧮 <b>Confirmados</b>\n"
        f"💰 Ganhos: <b>{format_currency(data.get('total_income'))}</b>\n"
        f"💸 Gastos: <b>{format_currency(data.get('total_expense'))}</b>\n"
        f"⚖️ Saldo: <b>{format_currency(data.get('balance'))}</b>"
    )
    planned_income = float(data.get("planned_income") or 0)
    planned_expense = float(data.get("planned_expense") or 0)
    if planned_income or planned_expense:
        text += (
            "\n\n⏳ <b>Planejados</b>\n"
            f"💰 Ganhos: <b>{format_currency(planned_income)}</b>\n"
            f"💸 Gastos: <b>{format_currency(planned_expense)}</b>\n"
            f"⚖️ Saldo previsto: <b>{format_currency(data.get('planned_balance'))}</b>"
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

    await message.answer("🧾 <b>Extrato - últimos lançamentos</b>", parse_mode="HTML")
    for item in transactions:
        transaction_id = int(item.get("id"))
        status = str(item.get("status") or "confirmed")
        await message.answer(
            build_transaction_text(item),
            parse_mode="HTML",
            reply_markup=transaction_actions_keyboard(transaction_id, status),
        )


@router.message(Command("pendentes"))
async def cmd_pending(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    result = await call_finance_tool(
        "get_recent_transactions",
        {"user_id": message.from_user.id, "limit": 50},
    )
    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao buscar pendentes: {error.get('message', 'Erro desconhecido.')}")
        return

    pending = [item for item in (result.get("data") or []) if (item.get("status") or "confirmed") == "planned"]
    if not pending:
        await message.answer("Você não tem lançamentos pendentes no momento. ✅")
        return

    await message.answer("⏳ <b>Lançamentos pendentes</b>", parse_mode="HTML")
    for item in pending[:15]:
        transaction_id = int(item.get("id"))
        await message.answer(
            build_transaction_text(item),
            parse_mode="HTML",
            reply_markup=transaction_actions_keyboard(transaction_id, "planned"),
        )


@router.message(Command("contas"))
async def cmd_accounts(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return

    now = datetime.datetime.now()
    result = await call_finance_tool(
        "get_monthly_summary",
        {"user_id": message.from_user.id, "month": now.month, "year": now.year, "include_planned": True},
    )

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Erro ao montar visão separada: {error.get('message', 'Erro desconhecido.')}")
        return

    transactions = (result.get("data") or {}).get("transactions") or []
    if not transactions:
        await message.answer("Ainda não encontrei lançamentos neste mês.")
        return

    groups = {
        ("income", "confirmed"): "💰✅ <b>Ganhos confirmados</b>",
        ("expense", "confirmed"): "💸✅ <b>Gastos confirmados</b>",
        ("income", "planned"): "💰⏳ <b>Ganhos planejados</b>",
        ("expense", "planned"): "💸⏳ <b>Gastos planejados</b>",
    }

    await message.answer(f"📂 <b>Contas separadas - {month_label(now.month, now.year)}</b>", parse_mode="HTML")

    for key, title in groups.items():
        trans_type, status = key
        items = [item for item in transactions if item.get("type") == trans_type and (item.get("status") or "confirmed") == status]
        if not items:
            await message.answer(f"{title}\n<i>nenhum lançamento</i>", parse_mode="HTML")
            continue

        await message.answer(title, parse_mode="HTML")
        for item in items:
            transaction_id = int(item.get("id"))
            await message.answer(
                build_transaction_text(item),
                parse_mode="HTML",
                reply_markup=transaction_actions_keyboard(transaction_id, status),
            )


@router.callback_query(F.data.startswith("tx_status:"))
async def on_transaction_status_change(callback: CallbackQuery):
    if callback.from_user is None or not callback.data:
        await callback.answer("Não consegui validar seu usuário.", show_alert=True)
        return

    try:
        _, raw_id, new_status = callback.data.split(":")
        transaction_id = int(raw_id)
    except ValueError:
        await callback.answer("Ação inválida.", show_alert=True)
        return

    result = await call_finance_tool(
        "update_transaction_status",
        {
            "user_id": callback.from_user.id,
            "transaction_id": transaction_id,
            "status": new_status,
        },
    )

    if not result.get("ok"):
        error = result.get("error", {})
        await callback.answer(error.get("message", "Não consegui atualizar o lançamento."), show_alert=True)
        return

    updated = result.get("data", {})
    trans_type = updated.get("type", "")
    category = html.escape(str(updated.get("category") or "sem categoria"))
    amount = format_signed_currency(updated.get("amount"), trans_type)
    description = html.escape(str(updated.get("description") or "-"))
    status = str(updated.get("status") or "confirmed")

    text = (
        "🧾 <b>Lançamento atualizado</b>\n"
        f"{type_emoji(trans_type)} <b>{category}</b> {amount}\n"
        f"{status_emoji(status)} <i>{status_label(status)}</i>\n"
        f"<i>{description}</i>"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=transaction_actions_keyboard(int(updated.get("id")), status),
    )
    await callback.answer("Status atualizado.")


@router.callback_query(F.data.startswith("tx_delete:"))
async def on_transaction_delete(callback: CallbackQuery):
    if callback.from_user is None or not callback.data:
        await callback.answer("Não consegui validar seu usuário.", show_alert=True)
        return

    try:
        _, raw_id = callback.data.split(":")
        transaction_id = int(raw_id)
    except ValueError:
        await callback.answer("Ação inválida.", show_alert=True)
        return

    result = await call_finance_tool(
        "delete_transaction",
        {"user_id": callback.from_user.id, "transaction_id": transaction_id},
    )
    if not result.get("ok"):
        error = result.get("error", {})
        await callback.answer(error.get("message", "Não consegui cancelar o lançamento."), show_alert=True)
        return

    deleted = result.get("data", {})
    trans_type = deleted.get("type", "")
    category = html.escape(str(deleted.get("category") or "sem categoria"))
    amount = format_signed_currency(deleted.get("amount"), trans_type)
    text = (
        "🗑️ <b>Lançamento cancelado</b>\n"
        f"{type_emoji(trans_type)} <b>{category}</b> {amount}"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer("Lançamento cancelado.")


@router.message(Command("confirmar"))
async def cmd_confirm(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return
    if not message.text:
        await message.answer("Use: /confirmar <id_do_lancamento>")
        return

    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Formato inválido. Exemplo: /confirmar 123")
        return

    transaction_id = int(parts[1])
    result = await call_finance_tool(
        "update_transaction_status",
        {
            "user_id": message.from_user.id,
            "transaction_id": transaction_id,
            "status": "confirmed",
        },
    )

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Não consegui confirmar: {error.get('message', 'Erro desconhecido.')}")
        return

    updated = result.get("data", {})
    trans_type = updated.get("type", "")
    category = html.escape(str(updated.get("category") or "sem categoria"))
    amount = format_signed_currency(updated.get("amount"), trans_type)
    description = html.escape(str(updated.get("description") or "-"))

    text = (
        "✅ <b>Lançamento confirmado</b>\n"
        f"{type_emoji(trans_type)} <b>{category}</b> {amount}\n"
        f"<i>{description}</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=transaction_actions_keyboard(transaction_id, "confirmed"))


@router.message(Command("desconfirmar"))
async def cmd_unconfirm(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return
    if not message.text:
        await message.answer("Use: /desconfirmar <id_do_lancamento>")
        return

    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Formato inválido. Exemplo: /desconfirmar 123")
        return

    transaction_id = int(parts[1])
    result = await call_finance_tool(
        "update_transaction_status",
        {
            "user_id": message.from_user.id,
            "transaction_id": transaction_id,
            "status": "planned",
        },
    )

    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Não consegui desconfirmar: {error.get('message', 'Erro desconhecido.')}")
        return

    updated = result.get("data", {})
    trans_type = updated.get("type", "")
    category = html.escape(str(updated.get("category") or "sem categoria"))
    amount = format_signed_currency(updated.get("amount"), trans_type)
    description = html.escape(str(updated.get("description") or "-"))

    text = (
        "⏳ <b>Lançamento desconfirmado</b>\n"
        f"{type_emoji(trans_type)} <b>{category}</b> {amount}\n"
        f"<i>{description}</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=transaction_actions_keyboard(transaction_id, "planned"))


@router.message(Command("cancelar"))
async def cmd_cancel(message: Message):
    if message.from_user is None:
        await message.answer("Não consegui identificar seu usuário no Telegram.")
        return
    if not message.text:
        await message.answer("Use: /cancelar <id_do_lancamento>")
        return

    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Formato inválido. Exemplo: /cancelar 123")
        return

    transaction_id = int(parts[1])
    result = await call_finance_tool(
        "delete_transaction",
        {"user_id": message.from_user.id, "transaction_id": transaction_id},
    )
    if not result.get("ok"):
        error = result.get("error", {})
        await message.answer(f"Não consegui cancelar: {error.get('message', 'Erro desconhecido.')}")
        return

    deleted = result.get("data", {})
    trans_type = deleted.get("type", "")
    category = html.escape(str(deleted.get("category") or "sem categoria"))
    amount = format_signed_currency(deleted.get("amount"), trans_type)
    await message.answer(
        f"🗑️ <b>Lançamento cancelado</b>\n{type_emoji(trans_type)} <b>{category}</b> {amount}",
        parse_mode="HTML",
    )


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

        status = parse_confirmation_mode(message.text)
        result = await call_finance_tool(
            "create_transaction",
            {
                "user_id": message.from_user.id,
                "amount": data["amount"],
                "trans_type": data["type"],
                "category": data["category"],
                "description": data.get("description", ""),
                "status": status,
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
            f"{status_emoji(status)} <i>{status_label(status)}</i>\n"
            f"📝 {html.escape(str(data.get('description') or type_label(trans_type)))}"
        )

        if balance is not None:
            text += f"\n\n⚖️ Saldo do mês: <b>{format_currency(balance)}</b>"

        reply_markup = None
        created_data = result.get("data") or []
        if created_data:
            transaction_id = int(created_data[0].get("id"))
            reply_markup = transaction_actions_keyboard(transaction_id, status)

        await wait_msg.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as exc:
        await wait_msg.edit_text(f"Erro ao salvar no banco de dados: {exc}")
