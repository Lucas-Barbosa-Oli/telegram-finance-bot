from datetime import date
from decimal import Decimal
import httpx
import pytest
from utils.domain import parse_money, parse_period, Transaction
from utils.ai_parser import AIParser, parse_local
from bot.handlers import query_action

REF = date(2026, 10, 23)

@pytest.mark.parametrize('text,amount,kind,when,status', [
    ('gastei 50 reais em mercado', '50.00', 'expense', REF, 'confirmed'),
    ('paguei R$ 25,90 no Uber ontem', '25.90', 'expense', date(2026,10,22), 'confirmed'),
    ('recebi meu salário de 3.000', '3000.00', 'income', REF, 'confirmed'),
    ('comprei um livro por 1.234,56 em 2026-09-30', '1234.56', 'expense', date(2026,9,30), 'confirmed'),
    ('vou pagar 900 de aluguel amanhã', '900.00', 'expense', date(2026,10,24), 'planned'),
    ('mercado 80', '80.00', 'expense', REF, 'confirmed'),
    ('I spent 12.50 on lunch yesterday', '12.50', 'expense', date(2026,10,22), 'confirmed'),
    ('paguei 20 no mercado 01/10/2026', '20.00', 'expense', date(2026,10,1), 'confirmed'),
])
def test_local(text, amount, kind, when, status):
    tx = parse_local(text, REF)
    assert tx is not None
    assert (tx.amount, tx.type, tx.occurred_on, tx.status) == (Decimal(amount), kind, when, status)

@pytest.mark.parametrize('text', [
    'não gastei 50 em mercado', 'quanto gastei em mercado?', 'gastei 20 e 30 no mercado',
    'gastei -50 em mercado', 'gastei 0 em mercado', 'gastei 1,234 em mercado',
    'gastei 50 em mercado dia 2', 'gastei 50 em mercado mês passado',
    'gastei 50 em mercado em 2026-02-31', 'gastei 2 mil em mercado',
    'gastei 20 USD em mercado', 'gastei $20 em mercado', 'gastei 50 e recebi 20',
    'transferi 100 para poupança', 'talvez pague 40 no mercado', 'gastei NaN',
    'gastei 20 em mercado hoje e ontem',
])
def test_ambiguous_not_saved(text):
    assert parse_local(text, REF) is None

@pytest.mark.parametrize('text,result', [('1.234,56','1234.56'), ('25,9','25.90'), ('3000','3000.00'), ('3.000','3000.00'), ('25.90','25.90')])
def test_money(text,result):
    assert parse_money(text) == Decimal(result)

@pytest.mark.parametrize('text', ['NaN','Infinity','-1','0','1,234','1.234,567','10000000000'])
def test_invalid_money(text):
    with pytest.raises(ValueError):
        parse_money(text)

@pytest.mark.parametrize('text,start,end', [
    ('mês passado','2026-09-01','2026-10-01'), ('2024-02','2024-02-01','2024-03-01'),
    ('2026-12','2026-12-01','2027-01-01'), ('ontem','2026-10-22','2026-10-23'),
    ('semana','2026-10-19','2026-10-26'), ('semana passada','2026-10-12','2026-10-19'),
    ('2026-10-01 2026-10-23','2026-10-01','2026-10-24'),
    ('setembro 2025','2025-09-01','2025-10-01'),
])
def test_period(text,start,end):
    p = parse_period(text, REF)
    assert (p.start.isoformat(),p.end.isoformat()) == (start,end)

@pytest.mark.parametrize('text', ['2026-13','2026-10-23 2026-10-01','últimos 30 dias','2026-02-31'])
def test_bad_period(text):
    with pytest.raises(ValueError):
        parse_period(text, REF)

@pytest.mark.parametrize('text,action', [('quanto gastei este mês?', 'resumo'), ('mostre minhas entradas e saídas','resumo'), ('gráfico do mês passado','grafico'), ('gastei 50 no mercado',None)])
def test_queries(text,action):
    assert query_action(text) == action

async def test_ai_disabled_never_calls_network():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: pytest.fail('network'))) as client:
        assert await AIParser(client).parse('anything') is None

async def test_ai_schema_and_validation():
    payload = dict(is_transaction=True, amount='42.30', type='expense', category='Alimentação',
                   description='Jantar', occurred_on='2026-10-22', status='confirmed')
    def handler(request):
        import json
        body = json.loads(request.content)
        assert body['store'] is False and body['text']['format']['strict'] is True
        assert 'user_id' not in body and body['input'] == 'jantar quarenta e dois e trinta'
        return httpx.Response(200, json={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(payload)}]}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (await AIParser(client, 'test').parse('jantar quarenta e dois e trinta')).amount == Decimal('42.30')

@pytest.mark.parametrize('response', [
    {'status':'incomplete','output':[]},
    {'status':'completed','output':[{'content':[{'type':'refusal','refusal':'no'}]}]},
    {'status':'completed','output':[{'content':[{'type':'output_text','text':'not json'}]}]},
    {'status':'completed','output':[{'content':[{'type':'output_text','text':'{"is_transaction":true,"amount":"NaN"}'}]}]},
])
async def test_ai_bad_outputs(response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=response))) as client:
        assert await AIParser(client,'test').parse('ambiguous') is None
