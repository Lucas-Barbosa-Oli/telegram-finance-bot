"""Temporary deployment provisioning; never exposes stored credentials."""
import asyncio
import logging
import os
import secrets
import time
from urllib.parse import urlparse

import httpx
from aiogram.types import BotCommand
from fastapi import HTTPException, Request

from bot.runtime import Settings, runtime

COMMANDS = {
    'ajuda': 'exemplos e comandos', 'resumo': 'entradas, saídas e saldo',
    'extrato': 'consultar lançamentos', 'relatorio': 'totais por categoria',
    'grafico': 'gráficos financeiros', 'exportar': 'exportar CSV',
    'pendentes': 'pagamentos planejados', 'ver': 'detalhes por ID',
    'editar': 'corrigir lançamento', 'cancelar': 'excluir com confirmação',
}


async def provision(request: Request):
    expected = os.getenv('BOT_SETUP_TOKEN', '')
    supplied = request.headers.get('X-Bot-Setup-Token', '')
    if len(expected) < 32:
        raise HTTPException(404, 'Not found')
    if not secrets.compare_digest(expected, supplied):
        raise HTTPException(403, 'Forbidden')
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, 'Invalid request') from None
    action = payload.get('action') if isinstance(payload, dict) else None
    if action not in ('inspect', 'configure', 'verify_summary', 'verify_chart'):
        raise HTTPException(400, 'Invalid action')
    base = os.getenv('BOT_PUBLIC_URL', '').rstrip('/')
    parsed = urlparse(base)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.path or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise HTTPException(503, 'Invalid production URL')
    try:
        async with asyncio.timeout(50):
            settings = Settings.from_env(webhook=True)
            async with runtime(settings) as (bot, _, store, _):
                await store.health()
                identity = await bot.get_me()
                if action == 'configure':
                    await bot.set_webhook(
                        url=base + '/webhook', secret_token=settings.webhook_secret,
                        allowed_updates=['message', 'callback_query'],
                        max_connections=2, drop_pending_updates=False,
                    )
                    await bot.set_my_commands([
                        BotCommand(command=name, description=description)
                        for name, description in COMMANDS.items()
                    ])
                elif action.startswith('verify_'):
                    # Only read-only commands, sent through the real authenticated webhook.
                    user = min(settings.users)
                    command = '/resumo tudo' if action == 'verify_summary' else '/grafico tudo'
                    update = {
                        'update_id': 2_000_000_000,
                        'message': {
                            'message_id': 2_000_000_000, 'date': int(time.time()),
                            'from': {'id': user, 'is_bot': False, 'first_name': 'Verification'},
                            'chat': {'id': user, 'type': 'private'}, 'text': command,
                        },
                    }
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            base + '/webhook', json=update,
                            headers={'X-Telegram-Bot-Api-Secret-Token': settings.webhook_secret},
                            timeout=40,
                        )
                        response.raise_for_status()
                info = await bot.get_webhook_info()
                return {
                    'ok': True, 'action': action, 'bot_username': identity.username,
                    'allowed_user_count': len(settings.users),
                    'webhook_url': info.url, 'pending_updates': info.pending_update_count,
                    'last_error_date': info.last_error_date,
                    'last_error_message': info.last_error_message,
                }
    except HTTPException:
        raise
    except Exception as exc:
        logging.getLogger(__name__).error('Provisioning failed (%s)', type(exc).__name__)
        raise HTTPException(503, 'Provisioning failed; inspect runtime logs') from None

