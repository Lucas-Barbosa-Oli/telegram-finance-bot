from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from utils.ai_parser import parse_expense_text
from database.client import add_transaction, get_monthly_summary
from utils.reports import generate_expense_pie_chart
import datetime

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
    now = datetime.datetime.now()
    summary = await get_monthly_summary(message.from_user.id, now.month, now.year)
    
    if not summary:
        await message.answer("Nenhuma transação encontrada para este mês.")
        return

    total_income = sum(item['amount'] for item in summary if item['type'] == 'income')
    total_expense = sum(item['amount'] for item in summary if item['type'] == 'expense')
    balance = total_income - total_expense

    text = f"📊 *Resumo de {now.strftime('%B/%Y')}*\n\n"
    text += f"💰 Ganhos: R$ {total_income:.2f}\n"
    text += f"💸 Gastos: R$ {total_expense:.2f}\n"
    text += f"⚖️ Saldo: R$ {balance:.2f}\n"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("grafico"))
async def cmd_chart(message: Message):
    now = datetime.datetime.now()
    summary = await get_monthly_summary(message.from_user.id, now.month, now.year)
    
    if not summary:
        await message.answer("Nenhuma transação encontrada para este mês.")
        return

    chart_buf = generate_expense_pie_chart(summary)
    
    if not chart_buf:
        await message.answer("Não há gastos registrados para gerar o gráfico.")
        return

    photo = BufferedInputFile(chart_buf.read(), filename="chart.png")
    await message.answer_photo(photo, caption=f"Distribuição de gastos em {now.strftime('%B/%Y')}")

@router.message()
async def process_text(message: Message):
    # Ignore commands
    if message.text.startswith('/'):
        return

    wait_msg = await message.answer("Processando sua mensagem... 🤔")
    
    data = await parse_expense_text(message.text)
    
    if not data:
        await wait_msg.edit_text("Desculpe, não consegui entender os valores. Tente ser mais específico.")
        return

    try:
        await add_transaction(
            user_id=message.from_user.id,
            amount=data['amount'],
            trans_type=data['type'],
            category=data['category'],
            description=data.get('description', '')
        )
        
        type_emoji = "💰" if data['type'] == 'income' else "💸"
        await wait_msg.edit_text(
            f"Registrado com sucesso! {type_emoji}\n\n"
            f"Valor: R$ {data['amount']:.2f}\n"
            f"Categoria: {data['category']}\n"
            f"Descrição: {data.get('description', '')}"
        )
    except Exception as e:
        await wait_msg.edit_text(f"Erro ao salvar no banco de dados: {e}")
