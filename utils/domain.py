"""Validation shared by parsing, reports and database writes."""
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


def today():
    return datetime.now(ZoneInfo(os.getenv('BOT_TIMEZONE', 'America/Sao_Paulo'))).date()


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not Decimal('0') < number <= Decimal('9999999999.99'):
            raise ValueError('O valor deve ser positivo e menor que R$ 10 bilhões.')
        if number != number.quantize(Decimal('.01')):
            raise ValueError('Use no máximo duas casas decimais.')
        return number.quantize(Decimal('.01'))
    except (InvalidOperation, TypeError):
        raise ValueError('Valor inválido.') from None


def parse_money(text):
    value = re.sub(r'(?i)r\$|reais|brl|\s', '', text)
    if ',' in value:
        if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})+|\d+),\d{1,2}', value):
            raise ValueError('Valor inválido. Exemplo: 1.234,56.')
        value = value.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(?:\.\d{3})+', value):
        value = value.replace('.', '')
    return money(value)


def currency(value):
    return ('R$ ' + f'{Decimal(str(value)):,.2f}').replace(',', 'X').replace('.', ',').replace('X', '.')


@dataclass(frozen=True)
class Transaction:
    amount: Decimal
    type: str
    category: str
    description: str
    occurred_on: date
    status: str = 'confirmed'

    @classmethod
    def from_dict(cls, data):
        amount = money(data.get('amount'))
        kind, status = data.get('type'), data.get('status', 'confirmed')
        if kind not in ('income', 'expense') or status not in ('confirmed', 'planned'):
            raise ValueError('Tipo ou status inválido.')
        category, description = data.get('category'), data.get('description', '')
        if not isinstance(category, str) or not 1 <= len(category.strip()) <= 60:
            raise ValueError('Categoria deve ter de 1 a 60 caracteres.')
        if not isinstance(description, str) or len(description) > 500:
            raise ValueError('Descrição deve ter até 500 caracteres.')
        when = date.fromisoformat(str(data.get('occurred_on')))
        if not date(2000, 1, 1) <= when <= today() + timedelta(days=3660):
            raise ValueError('Data fora do intervalo permitido.')
        return cls(amount, kind, category.strip(), description.strip(), when, status)

    def as_dict(self):
        return {**self.__dict__, 'amount': str(self.amount), 'occurred_on': self.occurred_on.isoformat()}


@dataclass(frozen=True)
class Period:
    start: date
    end: date  # exclusive

    @property
    def label(self):
        return f'{self.start:%d/%m/%Y} a {self.end - timedelta(days=1):%d/%m/%Y}'


def month_period(year, month):
    return Period(date(year, month, 1), date(year + (month == 12), month % 12 + 1, 1))


MONTHS = ('janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro')


def parse_period(text, reference=None):
    ref, value = reference or today(), normalize(text)
    dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', value)
    if dates:
        if len(dates) > 2:
            raise ValueError('Use uma data ou um intervalo de duas datas.')
        start, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
        if last < start:
            raise ValueError('A data final deve ser posterior à inicial.')
        return Period(start, last + timedelta(days=1))
    match = re.search(r'\b(\d{4})-(\d{2})\b', value)
    if match:
        return month_period(*map(int, match.groups()))
    match = re.search(r'\b(\d{2})/(\d{4})\b', value)
    if match:
        return month_period(int(match[2]), int(match[1]))
    if re.search(r'\b(hoje|today)\b', value):
        return Period(ref, ref + timedelta(days=1))
    if re.search(r'\b(ontem|yesterday)\b', value):
        return Period(ref - timedelta(days=1), ref)
    if re.search(r'\b(semana|week)\b', value):
        start = ref - timedelta(days=ref.weekday())
        if re.search(r'passada|anterior|last', value):
            start -= timedelta(days=7)
        return Period(start, start + timedelta(days=7))
    if re.search(r'mes passado|mes anterior|last month', value):
        prev = ref.replace(day=1) - timedelta(days=1)
        return month_period(prev.year, prev.month)
    for month, name in enumerate(MONTHS, 1):
        if re.search(rf'\b{name}\b', value):
            year = re.search(r'\b(20\d{2})\b', value)
            return month_period(int(year[1]) if year else ref.year, month)
    if re.search(r'\d|ano|year|amanha|tomorrow|ultim|last|proxim|next', value):
        raise ValueError('Período não reconhecido. Use hoje, ontem, semana, mês passado, AAAA-MM ou AAAA-MM-DD AAAA-MM-DD.')
    return month_period(ref.year, ref.month)
