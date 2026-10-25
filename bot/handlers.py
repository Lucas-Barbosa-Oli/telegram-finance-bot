import asyncio
import re
from datetime import timedelta
from uuid import UUID
from aiogram import BaseMiddleware, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from utils.ai_parser import infer_category, parse_local
from utils.domain import Transaction, currency, normalize, parse_money, parse_period, today
from utils.reports import categories, csv_export, generate_chart, totals

HELP = """💰 Seu controle financeiro
Envie uma compra ou recebimento:
• gastei 50 reais em mercado
• paguei 25,90 no Uber ontem
• recebi meu salário de 3000
• vou pagar 900 de aluguel amanhã

Consultas:
• quanto gastei com alimentação este mês?
• mostre minhas entradas e saídas
• gráfico do mês passado

 /resumo [período] — entradas, saídas e saldo
 /relatorio [período] — categorias
 /grafico [período] — categorias e evolução mensal
 /extrato [período] — lançamentos, 10 por página
 /pendentes [período] — planejados
 /contas [período] — realizados e previstos
 /exportar [período|tudo] — CSV completo
 /ver ID — detalhes e ações
 /editar ID valor 25,90
 /editar ID categoria Alimentação
 /editar ID data 2026-10-22
 /editar ID descricao Compra no mercado
 /confirmar ID ou /desconfirmar ID
 /cancelar ID — pede confirmação para excluir

Períodos: hoje, ontem, semana, mês passado, 2026-10
ou 2026-10-01 2026-10-23. Padrão: mês atual.
Filtro opcional: categoria:Alimentação (no final).
Registro explícito:
 /gasto 25,90 Alimentação 2026-10-22 Almoço
 /entrada 3000 Salário 2026-10-05 Pagamento
Valores em reais. Uma transação por mensagem.
Use /ajuda para rever estes exemplos."""


def keyboard(*buttons):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=data) for label, data in buttons]])


def actions(row):
    target = 'planned' if row.get('status') == 'confirmed' else 'confirmed'
    label = 'Marcar planejado' if target == 'planned' else 'Confirmar pagamento'
    return keyboard((label, f"status:{row['id']}:{target}"), ('Excluir', f"delete:{row['id']}"))


def transaction_text(row):
    sign = '+' if row['type'] == 'income' else '-'
    state = 'Planejado' if row.get('status') == 'planned' else 'Confirmado'
    return (f"#{row.get('id', 'prévia')} • {row['occurred_on']} • {state}\n"
            f"{sign}{currency(row['amount'])} • {row['category']}\n{row.get('description') or ''}")


async def send_chunks(message, text):
    while text:
        split = text.rfind('\n', 0, 3500) if len(text) > 3500 else len(text)
        if split <= 0:
            split = 3500
        await message.answer(text[:split])
        text = text[split:].lstrip('\n')


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_users):
        self.allowed_users = allowed_users

    async def __call__(self, handler, event, data):
        user = event.from_user
        message = event.message if isinstance(event, CallbackQuery) else event
        if not user or user.id not in self.allowed_users:
            if isinstance(event, CallbackQuery):
                await event.answer('Acesso não autorizado.', show_alert=True)
            elif isinstance(event, Message) and event.chat.type == 'private':
                await event.answer(f'Bot privado. Seu ID para configuração pelo proprietário: {user.id if user else "desconhecido"}')
            return
        if not isinstance(message, Message) or message.chat.type != 'private':
            if isinstance(event, CallbackQuery):
                await event.answer('Use uma conversa privada com o bot.')
            elif isinstance(event, Message):
                await event.answer('Use uma conversa privada com o bot.')
            return
        try:
            return await handler(event, data)
        except ValueError as exc:
            if isinstance(event, CallbackQuery):
                await event.answer(str(exc)[:190], show_alert=True)
            else:
                await event.answer(str(exc))


def query_action(text):
    value = normalize(text)
    if value.startswith('show '):
        return 'resumo'
    if re.search(r'\b(grafico|chart|graph)\b', value):
        return 'grafico'
    if re.search(r'\b(exportar|export|csv)\b', value):
        return 'exportar'
    if re.search(r'\b(extrato|lancamentos|historico|transactions)\b', value):
        return 'extrato'
    if re.search(r'\b(pendentes|planejados)\b', value):
        return 'pendentes'
    if re.search(r'\b(quanto|quais|mostre|mostrar|resumo|saldo|relatorio|how much|balance)\b', value):
        return 'resumo'
    if re.fullmatch(r'(minhas? )?(entradas|saidas|ganhos|gastos)( e (entradas|saidas|ganhos|gastos))?', value.strip()):
        return 'resumo'
    return None


async def show_report(message, store, action, text):
    raw = text
    category = None
    match = re.search(r'categoria:(.+)$', text, re.I)
    if match:
        category = match[1].strip()
        text = text[:match.start()]
    elif not raw.startswith('/'):
        inferred = infer_category(text)
        category = inferred if inferred != 'Outros' else None
    cursor_match = re.search(r'\bantes\s+(\d+)\b', text)
    before = int(cursor_match[1]) if cursor_match else None
    text = re.sub(r'\bantes\s+\d+\b', '', text)
    value = normalize(text)
    all_time = bool(re.search(r'\b(tudo|todos|all)\b', value))
    period = None if all_time else parse_period(text)
    label = period.label if period else 'Todo o histórico'
    if category:
        label += f' • {category}'
    income = bool(re.search(r'\b(entradas?|ganhos?|receitas?|recebi|ganhei|income|earned)\b', value))
    expense = bool(re.search(r'\b(saidas?|gastos?|despesas?|gastei|spent|expenses?)\b', value))
    kind = ('income' if income else 'expense') if income != expense else None
    status = 'planned' if action == 'pendentes' else None
    is_list = action in ('extrato', 'pendentes')
    rows = await store.list(message.from_user.id, period, status, kind, category, limit=11 if is_list else None, before=before)
    if not rows:
        await message.answer(f'Nenhum lançamento encontrado.\n{label}')
        return
    if action == 'exportar':
        await message.answer_document(BufferedInputFile(csv_export(rows), filename='lancamentos.csv'), caption=label[:1000])
    elif action == 'grafico':
        png = await asyncio.to_thread(generate_chart, rows, label)
        await message.answer_photo(BufferedInputFile(png, filename='financas.png'), caption='Somente valores confirmados. Planejados aparecem em /resumo.')
    elif is_list:
        await send_chunks(message, label + '\n\n' + '\n\n'.join(transaction_text(row) for row in rows[:10]))
        if len(rows) > 10:
            clean = re.sub(r'\bantes\s+\d+\b', '', raw).strip()
            if clean.startswith('/'):
                command = clean
            else:
                command = f'/{action} ' + (f'{period.start} {period.end - timedelta(days=1)}' if period else 'tudo')
                if kind:
                    command += ' entradas' if kind == 'income' else ' saidas'
                if category:
                    command += f' categoria:{category}'
            head, sep, tail = command.partition('categoria:')
            command = f'{head.strip()} antes {rows[9]["id"]}' + (f' categoria:{tail}' if sep else '')
            await message.answer('Próxima página (copie e envie):\n' + command)
        await message.answer('Detalhes e ações: /ver ID. Todos os dados: /exportar tudo.')
    else:
        summary = totals(rows)
        result = (f'📊 {label}\n\n'
                  f'Entradas: {currency(summary["income"])}\nSaídas: {currency(summary["expense"])}\n'
                  f'Saldo do período: {currency(summary["balance"])}\n\n'
                  f'Entradas previstas: {currency(summary["planned_income"])}\n'
                  f'Saídas previstas: {currency(summary["planned_expense"])}\n'
                  f'Saldo projetado: {currency(summary["projected_balance"])}\n'
                  '(Saldo dos lançamentos, sem saldo inicial bancário.)')
        if kind:
            result += '\nFiltro: ' + ('somente entradas' if kind == 'income' else 'somente saídas')
        for trans_type, title in [('expense', 'Gastos por categoria'), ('income', 'Entradas por categoria')]:
            breakdown = categories(rows, trans_type)
            if breakdown:
                result += '\n\n' + title + '\n' + '\n'.join(f'• {name}: {currency(amount)}' for name, amount in breakdown.items())
        await send_chunks(message, result)


def create_router():
    router = Router()

    @router.message(F.text)
    async def on_text(message: Message, store, parser):
        text = message.text.strip()
        if len(text) > 500:
            raise ValueError('Use até 500 caracteres e uma transação por mensagem.')
        parts = text.split()
        if not parts:
            return
        command = parts[0].split('@')[0].lower() if text.startswith('/') else ''
        if command in ('/start', '/ajuda', '/help'):
            await message.answer(HELP)
            return
        if command in ('/gasto', '/entrada'):
            fields = text.split(maxsplit=4)
            if len(fields) < 4:
                raise ValueError('Use: /gasto 25,90 Alimentação 2026-10-22 Almoço')
            when = fields[3]
            transaction = Transaction.from_dict({
                'amount': parse_money(fields[1]), 'type': 'expense' if command == '/gasto' else 'income',
                'category': fields[2], 'occurred_on': when, 'description': fields[4] if len(fields) > 4 else '',
                'status': 'planned' if when > today().isoformat() else 'confirmed'})
            await save(message, store, transaction)
            return
        if command in ('/ver', '/confirmar', '/desconfirmar', '/cancelar', '/editar'):
            if len(parts) < 2 or not parts[1].isdigit():
                raise ValueError(f'Use {command} ID. Encontre o ID em /extrato.')
            transaction_id = int(parts[1])
            if command == '/cancelar':
                row = await store.get(message.from_user.id, transaction_id)
                await message.answer('Excluir este lançamento?\n' + transaction_text(row),
                    reply_markup=keyboard(('Sim, excluir', f'delete_yes:{transaction_id}'), ('Manter', 'keep')))
                return
            if command in ('/confirmar', '/desconfirmar'):
                row = await store.update(message.from_user.id, transaction_id, {'status': 'confirmed' if command == '/confirmar' else 'planned'})
            elif command == '/editar':
                fields = text.split(maxsplit=3)
                names = {'valor': 'amount', 'categoria': 'category', 'descricao': 'description', 'data': 'occurred_on'}
                if len(fields) != 4 or normalize(fields[2]) not in names:
                    raise ValueError('Use /editar ID valor|categoria|descricao|data NOVO_VALOR.')
                key = names[normalize(fields[2])]
                value = str(parse_money(fields[3])) if key == 'amount' else fields[3]
                row = await store.update(message.from_user.id, transaction_id, {key: value})
            else:
                row = await store.get(message.from_user.id, transaction_id)
            await message.answer(transaction_text(row), reply_markup=actions(row))
            return
        report_commands = ('/resumo', '/relatorio', '/grafico', '/extrato', '/pendentes', '/contas', '/exportar')
        action = command[1:] if command in report_commands else query_action(text) if not command else None
        if action:
            await show_report(message, store, action, text)
            return
        if command:
            raise ValueError('Comando não reconhecido. Use /ajuda.')
        transaction = parse_local(text)
        if transaction:
            await save(message, store, transaction)
            return
        transaction = await parser.parse(text)
        if transaction:
            draft_id = await store.save_draft(message.from_user.id, message.chat.id, message.message_id, transaction)
            await message.answer('Confira a interpretação antes de salvar (válida por 15 minutos):\n' + transaction_text(transaction.as_dict()),
                reply_markup=keyboard(('Salvar', f'draft:{draft_id}'), ('Descartar', f'discard:{draft_id}')))
        else:
            await message.answer('Não registrei nada: preciso de um valor, tipo e data claros. Exemplo: "gastei 25,90 em mercado ontem".\n'
                                 'Ou use /gasto 25,90 Alimentação 2026-10-22 Almoço.\nPara consultar, use /resumo ou /ajuda.')

    @router.callback_query()
    async def on_callback(callback: CallbackQuery, store):
        message, user_id = callback.message, callback.from_user.id
        parts = (callback.data or '').split(':')
        action = parts[0]
        if action == 'keep':
            await callback.answer('Mantido.')
            await message.edit_reply_markup(reply_markup=None)
            return
        if action in ('draft', 'discard') and len(parts) == 2:
            draft_id = str(UUID(parts[1]))
            draft = await store.get_draft(user_id, draft_id)
            if draft['source_chat_id'] != message.chat.id:
                raise ValueError('Conversa inválida.')
            if action == 'draft':
                row, _ = await store.create(user_id, draft['source_chat_id'], draft['source_message_id'], Transaction.from_dict(draft['payload']))
                if row.get('deleted_at'):
                    await message.edit_text('Este lançamento já foi excluído.')
                else:
                    await message.edit_text('✅ Registrado!\n' + transaction_text(row), reply_markup=actions(row))
            else:
                await message.edit_text('Prévia descartada. Nenhum lançamento salvo.')
            await store.delete_draft(user_id, draft_id)
        elif action in ('status', 'delete', 'delete_yes') and len(parts) >= 2:
            transaction_id = int(parts[1])
            if action == 'delete_yes':
                await store.delete(user_id, transaction_id)
                await message.edit_text('Lançamento excluído dos relatórios.')
            elif action == 'delete':
                row = await store.get(user_id, transaction_id)
                await message.edit_text('Excluir este lançamento?\n' + transaction_text(row),
                    reply_markup=keyboard(('Sim, excluir', f'delete_yes:{transaction_id}'), ('Manter', 'keep')))
            else:
                if len(parts) != 3:
                    raise ValueError('Ação inválida.')
                row = await store.update(user_id, transaction_id, {'status': parts[2]})
                await message.edit_text(transaction_text(row), reply_markup=actions(row))
        else:
            raise ValueError('Ação inválida. Use /extrato.')
        await callback.answer()

    @router.message()
    async def on_other(message: Message):
        await message.answer('Por enquanto aceito mensagens de texto. Use /ajuda para exemplos.')

    return router


async def save(message, store, transaction):
    row, created = await store.create(message.from_user.id, message.chat.id, message.message_id, transaction)
    if row.get('deleted_at'):
        await message.answer('Esta mensagem já havia sido registrada e excluída. Nenhum novo lançamento salvo.')
        return
    title = '✅ Registrado!' if created else '✅ Esta mensagem já foi registrada.'
    await message.answer(title + '\n' + transaction_text(row), reply_markup=actions(row))
