from decimal import Decimal
from utils.reports import totals, categories, csv_export, generate_chart

def row(id=1, amount='0.10', kind='expense', status='confirmed', category='Alimentação', description='Almoço'):
    return dict(id=id,amount=amount,type=kind,status=status,category=category,description=description,occurred_on='2026-10-23')

def test_totals_exact_separate_planned():
    data = [row(amount='0.10'),row(amount='0.20'),row(amount='1',kind='income'),
            row(amount='0.40',status='planned'),row(amount='2',kind='income',status='planned')]
    result = totals(data)
    assert result['expense'] == Decimal('.30')
    assert result['balance'] == Decimal('.70')
    assert result['projected_balance'] == Decimal('2.30')
    assert categories(data) == {'Alimentação': Decimal('.30')}

def test_csv_neutralizes_formulas_and_quotes():
    content = csv_export([row(category='=HYPERLINK("evil")',description=' \t+cmd;"quoted"\nnext')]).decode('utf-8-sig')
    assert "'=HYPERLINK" in content and "' \t+cmd" in content and '""quoted""' in content

def test_charts_empty_income_only_and_many_categories():
    assert generate_chart([], 'Empty') is None
    assert generate_chart([row(kind='income')], 'Only income').startswith(b'\x89PNG\r\n\x1a\n')
    png = generate_chart([row(id=i,amount=str(i+1),category=f'Categoria {i}') for i in range(12)], 'Outubro 2026')
    assert png.startswith(b'\x89PNG\r\n\x1a\n') and len(png) > 10000
