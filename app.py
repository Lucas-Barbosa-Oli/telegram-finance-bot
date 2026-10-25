"""Vercel webhook: authenticate before contacting any service."""
import asyncio
import logging
import os
import secrets
from fastapi import FastAPI, HTTPException, Request
from aiogram.types import Update
from pydantic import ValidationError
from bot.runtime import Settings, runtime

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.get('/')
@app.get('/health')
async def health():
    return {'status': 'ok', 'service': 'telegram-finance-bot'}

@app.post('/webhook')
async def webhook(request: Request):
    secret = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
    supplied = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not secret or not secrets.compare_digest(secret, supplied):
        raise HTTPException(403, 'Forbidden')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 131072:
            raise HTTPException(413, 'Payload too large')
    try:
        update = Update.model_validate_json(body)
    except ValidationError:
        raise HTTPException(400, 'Invalid update') from None
    try:
        settings = Settings.from_env(webhook=True)
        # Await completion. Telegram retries 503s; unique source keys prevent duplicate entries.
        async with asyncio.timeout(50):
            async with runtime(settings) as (bot, dispatcher, store, parser):
                await dispatcher.feed_update(bot, update, store=store, parser=parser)
    except Exception as exc:
        logging.getLogger(__name__).error('Webhook failed (%s)', type(exc).__name__)
        raise HTTPException(503, 'Temporarily unavailable') from None
    return {'ok': True}

# Opt-in provisioning route; absent after the temporary token is removed.
if os.getenv('BOT_SETUP_TOKEN'):
    from bot.provisioning import provision
    app.post('/admin/bootstrap')(provision)
