import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from bot.handlers import router
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def main():
    logging.basicConfig(level=logging.INFO)

    if not TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    await bot.set_my_commands(
        [
            BotCommand(command="ajuda", description="ver exemplos e comandos"),
            BotCommand(command="resumo", description="resumo do mês"),
            BotCommand(command="extrato", description="últimos lançamentos"),
            BotCommand(command="relatorio", description="ganhos e gastos por categoria"),
            BotCommand(command="grafico", description="gráfico de gastos"),
        ]
    )

    logging.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped!")
