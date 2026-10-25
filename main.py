"""Local polling entrypoint. Vercel uses app.py instead."""
import asyncio
import logging
from bot.runtime import Settings, runtime

async def main():
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    async with runtime(settings) as (bot, dispatcher, store, parser):
        await store.health()
        webhook = await bot.get_webhook_info()
        if webhook.url:
            raise RuntimeError('Webhook ativo. Use python -m scripts.configure_telegram polling antes de executar localmente.')
        await dispatcher.start_polling(bot, store=store, parser=parser,
                                       allowed_updates=['message', 'callback_query'], tasks_concurrency_limit=10)

if __name__ == '__main__':
    asyncio.run(main())
