import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from database import async_session_factory
from handlers import admin_router, common_router, participant_router, registration_router
from middlewares import DatabaseMiddleware
from scheduler.tasks import check_and_close_auctions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DatabaseMiddleware(async_session_factory))

    # Registration and common handlers first so FSM states are matched first
    dp.include_router(common_router)
    dp.include_router(registration_router)
    dp.include_router(admin_router)
    dp.include_router(participant_router)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        check_and_close_auctions,
        trigger="interval",
        minutes=1,
        kwargs={"bot": bot},
    )
    scheduler.start()
    logger.info("Scheduler started — checking auctions every minute.")

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot, skip_updates=True, scheduler=scheduler)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
