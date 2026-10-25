from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import FastAPI
from bot import provisioning

app = FastAPI()
app.post('/admin/bootstrap')(provisioning.provision)

async def test_provisioning_disabled_and_authenticated_before_services(monkeypatch):
    monkeypatch.delenv('BOT_SETUP_TOKEN', raising=False)
    monkeypatch.setattr(provisioning, 'runtime', lambda *_: pytest.fail('must not initialize'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://test', trust_env=False) as client:
        assert (await client.post('/admin/bootstrap', json={'action':'configure'})).status_code == 404
        monkeypatch.setenv('BOT_SETUP_TOKEN', 'x'*40)
        assert (await client.post('/admin/bootstrap', json={'action':'configure'})).status_code == 403
        headers = {'X-Bot-Setup-Token':'x'*40}
        assert (await client.post('/admin/bootstrap', json={'action':'delete'}, headers=headers)).status_code == 400

async def test_provisioning_configures_only_fixed_server_url_without_disclosing_keys(monkeypatch):
    monkeypatch.setenv('BOT_SETUP_TOKEN', 'x'*40)
    monkeypatch.setenv('BOT_PUBLIC_URL', 'https://production.example')
    settings = SimpleNamespace(users={17}, webhook_secret='private-webhook-secret')
    monkeypatch.setattr(provisioning.Settings, 'from_env', lambda **_: settings)
    bot, store = AsyncMock(), AsyncMock()
    bot.get_me.return_value = SimpleNamespace(username='finance_bot')
    bot.get_webhook_info.return_value = SimpleNamespace(url='https://production.example/webhook', pending_update_count=0, last_error_date=None, last_error_message=None)
    @asynccontextmanager
    async def fake_runtime(_):
        yield bot, None, store, None
    monkeypatch.setattr(provisioning, 'runtime', fake_runtime)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://test', trust_env=False) as client:
        response = await client.post('/admin/bootstrap', json={'action':'configure', 'url':'https://evil.example'}, headers={'X-Bot-Setup-Token':'x'*40})
        assert response.status_code == 200
        assert 'private-webhook-secret' not in response.text
        store.health.assert_awaited_once()
        assert bot.set_webhook.call_args.kwargs['url'] == 'https://production.example/webhook'
        assert bot.set_webhook.call_args.kwargs['drop_pending_updates'] is False
        bot.set_my_commands.assert_awaited_once()

async def test_provisioning_error_is_sanitized(monkeypatch):
    monkeypatch.setenv('BOT_SETUP_TOKEN', 'x'*40)
    monkeypatch.setenv('BOT_PUBLIC_URL', 'https://production.example')
    monkeypatch.setattr(provisioning.Settings, 'from_env', lambda **_: (_ for _ in ()).throw(ValueError('sensitive-detail')))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://test', trust_env=False) as client:
        response = await client.post('/admin/bootstrap', json={'action':'inspect'}, headers={'X-Bot-Setup-Token':'x'*40})
        assert response.status_code == 503 and 'sensitive-detail' not in response.text
