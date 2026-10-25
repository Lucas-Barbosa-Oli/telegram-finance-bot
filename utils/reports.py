"""Exact financial arithmetic and local PNG/CSV rendering."""
import csv
import io
import os
import tempfile
import threading
from collections import defaultdict
from decimal import Decimal
from utils.domain import currency

_CHART_LOCK = threading.Lock()


def totals(rows):
    result = {key: Decimal('0.00') for key in ('income', 'expense', 'planned_income', 'planned_expense')}
    for row in rows:
        key = ('planned_' if row.get('status') == 'planned' else '') + row['type']
        result[key] += Decimal(str(row['amount']))
    result['balance'] = result['income'] - result['expense']
    result['projected_balance'] = result['balance'] + result['planned_income'] - result['planned_expense']
    return result


def categories(rows, kind='expense'):
    result = defaultdict(Decimal)
    for row in rows:
        if row['type'] == kind and row.get('status', 'confirmed') == 'confirmed':
            result[row.get('category') or 'Outros'] += Decimal(str(row['amount']))
    return dict(sorted(result.items(), key=lambda pair: pair[1], reverse=True))


def csv_export(rows):
    output = io.StringIO(newline='')
    writer = csv.writer(output, delimiter=';')
    fields = ['id', 'occurred_on', 'type', 'amount', 'category', 'description', 'status']
    writer.writerow(fields)
    for row in sorted(rows, key=lambda item: (item['occurred_on'], item['id'])):
        values = []
        for key in fields:
            value = str(row.get(key) or '')
            # Prevent spreadsheet formulas in user-controlled fields.
            if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return output.getvalue().encode('utf-8-sig')


def generate_chart(rows, label):
    if not rows:
        return None
    # Lazy import avoids matplotlib cold-start cost on ordinary webhook messages.
    os.environ.setdefault('MPLCONFIGDIR', os.path.join(tempfile.gettempdir(), 'finance-matplotlib'))
    with _CHART_LOCK:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        fig = Figure(figsize=(10, 7), dpi=140, layout='constrained')
        FigureCanvasAgg(fig)
        top, bottom = fig.subplots(2, 1)
        spending = categories(rows)
        items = list(spending.items())
        if len(items) > 8:
            items = items[:8] + [('Demais categorias', sum(value for _, value in items[8:]))]
        if items:
            names, values = zip(*reversed(items))
            bars = top.barh(names, [float(v) for v in values], color='#e26a51')
            top.bar_label(bars, labels=[currency(v) for v in values], padding=4, fontsize=8)
            top.set_xlim(0, float(max(values)) * 1.35)
        else:
            top.text(.5, .5, 'Sem gastos confirmados', ha='center', transform=top.transAxes)
        top.set_title('Gastos por categoria')
        monthly = defaultdict(lambda: {'income': Decimal(0), 'expense': Decimal(0)})
        for row in rows:
            if row.get('status', 'confirmed') == 'confirmed':
                monthly[row['occurred_on'][:7]][row['type']] += Decimal(str(row['amount']))
        months = sorted(monthly)
        x = list(range(len(months)))
        bottom.bar([i - .2 for i in x], [float(monthly[m]['income']) for m in months], width=.4, label='Entradas', color='#238b6d')
        bottom.bar([i + .2 for i in x], [float(monthly[m]['expense']) for m in months], width=.4, label='Saídas', color='#e26a51')
        step = max(1, (len(months) + 11) // 12)
        bottom.set_xticks(x[::step], months[::step], rotation=30)
        bottom.set_ylabel('R$')
        bottom.set_title('Entradas e saídas confirmadas')
        bottom.legend()
        fig.suptitle(label, fontsize=13, weight='bold')
        output = io.BytesIO()
        fig.savefig(output, format='png', facecolor='white')
        return output.getvalue()
