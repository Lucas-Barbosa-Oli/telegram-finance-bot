"""Run explicitly after deployment; never invoked automatically at build/import."""
import argparse
import asyncio
from urllib.parse import urlparse
from aiogram.types import BotCommand
from bot.runtime import Settings, runtime

COMMANDS = {
    'ajuda': 'exemplos e comandos', 'resumo': 'entradas, saídas e saldo',
    'extrato': 'consultar lançamentos', 'relatorio': 'totais por categoria',
    'grafico': 'gráficos financeiros', 'exportar': 'exportar CSV',
    'pendentes': 'pagamentos planejados', 'ver': 'detalhes por ID',
    'editar': 'corrigir lançamento', 'cancelar': 'excluir com confirmação',
}


async def configure(mode, url=None):
    settings = Settings.from_env(webhook=mode == 'webhook')
    async with runtime(settings) as (bot, _, store, _):
        if mode == 'status':
            info = await bot.get_webhook_info()
            print(f'Webhook: {info.url or "(polling)"}; pending: {info.pending_update_count}')
            if info.last_error_message:
                print(f'Last Telegram delivery error: {info.last_error_message}')
            return
        await store.health()
        if mode == 'webhook':
            parsed = urlparse(url or '')
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
                raise ValueError('Supply your production HTTPS base URL, without credentials/query/fragment.')
            await bot.set_webhook(url=url.rstrip('/') + '/webhook', secret_token=settings.webhook_secret,
                                  allowed_updates=['message', 'callback_query'], max_connections=2,
                                  drop_pending_updates=False)
        else:
            await bot.delete_webhook(drop_pending_updates=False)
        await bot.set_my_commands([BotCommand(command=name, description=description) for name, description in COMMANDS.items()])
        print('Telegram configured. Pending updates were preserved.')


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('mode', choices=['webhook', 'polling', 'status'])
    args.add_argument('url', nargs='?')
    parsed = args.parse_args()
    asyncio.run(configure(parsed.mode, parsed.url))
