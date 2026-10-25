from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import httpx
import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.types import Message, Update
from bot.handlers import AccessMiddleware, create_router
from utils.ai_parser import parse_local
from utils.domain import today

class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
    async def close(self):
        pass
    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        return True
    async def stream_content(self, *args, **kwargs):
        yield b''

def update(text='', user=17, chat_type='private', callback=None):
    message = dict(message_id=10,date=int(datetime.now(timezone.utc).timestamp()),
                   chat={'id':user,'type':chat_type},from_user={'id':user,'is_bot':False,'first_name':'Test'},text=text)
    if callback:
        return Update(update_id=1,callback_query=dict(id='cb',from_user=message['from_user'],chat_instance='test',data=callback,message=message))
    return Update(update_id=1,message=message)

async def dispatch(text='', user=17, chat_type='private', callback=None, store=None, parser=None):
    session = FakeSession()
    bot = Bot('123456:TEST_TOKEN', session=session)
    dp = Dispatcher(disable_fsm=True)
    router = create_router()
    router.message.outer_middleware(AccessMiddleware({17}))
    router.callback_query.outer_middleware(AccessMiddleware({17}))
    dp.include_router(router)
    store, parser = store or AsyncMock(), parser or AsyncMock()
    await dp.feed_update(bot,update(text,user,chat_type,callback),store=store,parser=parser)
    await bot.session.close()
    return store, parser, session.calls

async def test_local_purchase_does_not_call_ai_or_summary():
    tx = parse_local('gastei 50 reais em mercado')
    store = AsyncMock()
    store.create.return_value = ({'id':1,**tx.as_dict()},True)
    _, parser, calls = await dispatch('gastei 50 reais em mercado',store=store)
    parser.parse.assert_not_called()
    store.list.assert_not_called()
    args = store.create.call_args.args
    assert args[:3] == (17,17,10)
    assert 'Registrado' in calls[-1].text

@pytest.mark.parametrize('user,chat_type',[(18,'private'),(17,'group')])
async def test_access_denied_before_services(user,chat_type):
    store,parser,calls = await dispatch('gastei 50',user=user,chat_type=chat_type)
    assert not store.mock_calls and not parser.mock_calls
    assert calls

async def test_unauthorized_callback():
    store,parser,_ = await dispatch(callback='delete_yes:1',user=18)
    assert not store.mock_calls and not parser.mock_calls

async def test_query_never_parses_or_inserts():
    store = AsyncMock()
    store.list.return_value = []
    _, parser, _ = await dispatch('quanto gastei com alimentação este mês?',store=store)
    store.create.assert_not_called()
    parser.parse.assert_not_called()
    assert store.list.call_args.args[3:5] == ('expense','Alimentação')

async def test_ai_preview_requires_confirmation():
    parser, store = AsyncMock(), AsyncMock()
    parser.parse.return_value = parse_local('gastei 50 em mercado')
    store.save_draft.return_value = '00000000-0000-0000-0000-000000000001'
    _,_,calls = await dispatch('almoço cinquenta reais',store=store,parser=parser)
    store.create.assert_not_called()
    assert calls[-1].reply_markup.inline_keyboard[0][0].callback_data.startswith('draft:')

async def test_delete_requires_confirmation():
    store = AsyncMock()
    store.get.return_value = {'id':1,**parse_local('gastei 50 em mercado').as_dict()}
    _,_,calls = await dispatch('/cancelar 1',store=store)
    store.delete.assert_not_called()
    assert calls[-1].reply_markup.inline_keyboard[0][0].callback_data == 'delete_yes:1'

async def test_duplicate_delivery_still_returns_saved_record():
    store = AsyncMock()
    store.create.return_value = ({'id':1,**parse_local('gastei 50 em mercado').as_dict()},False)
    _,_,calls = await dispatch('gastei 50 em mercado',store=store)
    assert 'já foi registrada' in calls[-1].text

async def test_bad_command_does_not_touch_services():
    store,parser,calls = await dispatch('/editar 1')
    assert not store.mock_calls and not parser.mock_calls
    assert 'Use /editar' in calls[-1].text

async def test_webhook_auth_and_health(monkeypatch):
    import app
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET','x'*32)
    monkeypatch.setattr(app,'runtime',lambda *_:pytest.fail('must not initialize'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='https://test',trust_env=False) as client:
        assert (await client.get('/health')).status_code == 200
        assert (await client.post('/webhook',json={})).status_code == 403
        assert (await client.post('/webhook',content='bad',headers={'X-Telegram-Bot-Api-Secret-Token':'x'*32})).status_code == 400
        assert (await client.post('/webhook',content='a'*131073,headers={'X-Telegram-Bot-Api-Secret-Token':'x'*32})).status_code == 413

async def test_webhook_awaits_work_and_retries_failures(monkeypatch):
    import app
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET','x'*32)
    monkeypatch.setattr(app.Settings,'from_env',lambda **_:None)
    done = []
    dp = AsyncMock()
    async def process(*_,**__):
        done.append(True)
    dp.feed_update.side_effect = process
    @asynccontextmanager
    async def fake_runtime(_):
        yield None,dp,None,None
    monkeypatch.setattr(app,'runtime',fake_runtime)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='https://test',trust_env=False) as client:
        headers = {'X-Telegram-Bot-Api-Secret-Token':'x'*32}
        assert (await client.post('/webhook',json={'update_id':1},headers=headers)).status_code == 200
        assert done
        dp.feed_update.side_effect = RuntimeError('private detail')
        response = await client.post('/webhook',json={'update_id':2},headers=headers)
        assert response.status_code == 503 and 'private detail' not in response.text
