import json
from datetime import date
from decimal import Decimal
import httpx
import pytest
from database.client import FinanceStore, DatabaseError
from utils.domain import Transaction, Period

TX = Transaction(Decimal('25.90'),'expense','Transporte','Uber',date(2026,10,22))

async def test_create_idempotent_does_not_overwrite():
    calls = []
    def handler(r):
        calls.append(r)
        if r.method == 'POST':
            assert r.url.params['on_conflict'] == 'user_id,source_chat_id,source_message_id'
            assert 'ignore-duplicates' in r.headers['Prefer']
            data = json.loads(r.content)
            assert data['user_id'] == 17 and data['source_message_id'] == 8
            return httpx.Response(201,json=[])
        assert r.url.params['user_id'] == 'eq.17'
        return httpx.Response(200,json=[dict(id=3,deleted_at='2026-10-23',**TX.as_dict())])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        row, created = await FinanceStore(client,'https://example.test','sb_secret_test').create(17,17,8,TX)
        assert not created and row['deleted_at']
        assert len(calls) == 2
        assert 'Authorization' not in calls[0].headers

async def test_pagination_handles_server_cap_and_all_rows():
    ids = list(range(1205,0,-1))
    calls = []
    def handler(r):
        calls.append(r)
        assert r.url.params['user_id'] == 'eq.17'
        assert r.url.params['deleted_at'] == 'is.null'
        assert r.url.params.get_list('occurred_on') == ['gte.2026-10-01','lt.2026-11-01']
        cursor = int(r.url.params.get('id','lt.99999')[3:])
        batch = [i for i in ids if i < cursor][:200] # server caps below client page size
        return httpx.Response(200,json=[dict(id=i,**TX.as_dict()) for i in batch])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await FinanceStore(client,'https://example.test','test').list(17,Period(date(2026,10,1),date(2026,11,1)))
        assert len(rows) == 1205 and len({row['id'] for row in rows}) == 1205
        assert len(calls) == 8

async def test_update_scoped_and_validated():
    calls = []
    def handler(r):
        calls.append(r)
        assert r.url.params['user_id'] == 'eq.17'
        assert r.url.params['id'] == 'eq.3'
        assert r.url.params['deleted_at'] == 'is.null'
        return httpx.Response(200,json=[dict(id=3,**TX.as_dict())])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = FinanceStore(client,'https://example.test','test')
        with pytest.raises(ValueError):
            await store.update(17,3,{'amount':'-1'})
        assert all(r.method == 'GET' for r in calls)
        await store.update(17,3,{'amount':'30.10'})
        assert json.loads(calls[-1].content) == {'amount':'30.10'}

async def test_cross_user_not_found_prevents_write():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=[]))) as client:
        with pytest.raises(ValueError,match='não encontrado'):
            await FinanceStore(client,'https://example.test','test').update(18,3,{'amount':'40'})

async def test_delete_is_scoped_soft_delete():
    def handler(r):
        assert r.method == 'PATCH'
        assert r.url.params['user_id'] == 'eq.17' and r.url.params['id'] == 'eq.3'
        assert 'deleted_at' in json.loads(r.content)
        return httpx.Response(200,json=[])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await FinanceStore(client,'https://example.test','test').delete(17,3)

async def test_error_sanitized():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(500,text='secret db details'))) as client:
        with pytest.raises(DatabaseError) as exc:
            await FinanceStore(client,'https://example.test','secret').health()
        assert 'secret' not in str(exc.value)

async def test_draft_ownership_expiry():
    def handler(r):
        assert r.url.params['user_id'] == 'eq.17'
        assert r.url.params['expires_at'].startswith('gt.')
        return httpx.Response(200,json=[])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match='expirou'):
            await FinanceStore(client,'https://example.test','test').get_draft(17,'00000000-0000-0000-0000-000000000001')
