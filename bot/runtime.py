import base64
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from zoneinfo import ZoneInfo
import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv
from bot.handlers import AccessMiddleware, create_router
from database.client import FinanceStore
from utils.ai_parser import AIParser

load_dotenv()


@dataclass
class Settings:
    token: str
    url: str
    key: str
    users: set
    webhook_secret: str = ''
    openai_key: str = ''
    openai_model: str = 'gpt-4o-mini'

    @classmethod
    def from_env(cls, webhook=False):
        token, url = os.getenv('TELEGRAM_BOT_TOKEN', ''), os.getenv('SUPABASE_URL', '')
        key = os.getenv('SUPABASE_SECRET_KEY') or os.getenv('SUPABASE_KEY', '')
        users = {int(value.strip()) for value in os.getenv('ALLOWED_TELEGRAM_USER_IDS', '').split(',') if value.strip()}
        secret = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
        if not token or not url.startswith('https://') or not key or not users or any(user <= 0 for user in users):
            raise ValueError('Configure TELEGRAM_BOT_TOKEN, SUPABASE_URL, SUPABASE_SECRET_KEY e ALLOWED_TELEGRAM_USER_IDS.')
        if not key.startswith('sb_secret_'):
            try:
                payload = key.split('.')[1]
                role = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))['role']
            except (ValueError, KeyError, IndexError):
                raise ValueError('Use uma chave secreta Supabase ou JWT service_role.') from None
            if role != 'service_role':
                raise ValueError('A chave anon não é aceita. Use uma chave secreta ou service_role somente no servidor.')
        if webhook and not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', secret):
            raise ValueError('TELEGRAM_WEBHOOK_SECRET deve ter 32 a 256 caracteres A-Z, a-z, 0-9, _ ou -.')
        ZoneInfo(os.getenv('BOT_TIMEZONE', 'America/Sao_Paulo'))
        return cls(token, url, key, users, secret,
                   os.getenv('OPENAI_API_KEY', '') if os.getenv('OPENAI_ENABLED', '').lower() == 'true' else '',
                   os.getenv('OPENAI_MODEL', 'gpt-4o-mini'))


@asynccontextmanager
async def runtime(settings):
    # One pool per polling process or webhook invocation; reused for DB/AI calls.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)) as client:
        bot = Bot(settings.token, session=AiohttpSession(timeout=15))
        dispatcher = Dispatcher(disable_fsm=True)
        router = create_router()
        access = AccessMiddleware(settings.users)
        router.message.outer_middleware(access)
        router.callback_query.outer_middleware(access)
        dispatcher.include_router(router)
        store = FinanceStore(client, settings.url, settings.key)
        parser = AIParser(client, settings.openai_key, settings.openai_model)
        try:
            yield bot, dispatcher, store, parser
        finally:
            await bot.session.close()
