import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from handlers import router, set_notification_service
from admin_handlers import admin_router
from admin_edit_handlers import admin_edit_router  # НОВЫЙ РОУТЕР
from registration_handlers import registration_router
from notifications import NotificationService
from daily_reports import schedule_daily_reports
from cashier_handlers import cashier_router
from parent_handlers import parent_router
from parent_edit_handlers import parent_edit_router  # НОВЫЙ РОУТЕР
from payment_handlers import payment_router
from reports_handlers import reports_router
from unknown_hanlders import unknown_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""

    # Проверяем наличие токена
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Проверьте файл .env")
        return

    # Инициализируем бот и диспетчер
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Инициализируем базу данных
    try:
        await db.init_db()
        logger.info("✅ База данных SQLite инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        return

    # Инициализируем сервис уведомлений
    notification_service = NotificationService(bot)
    set_notification_service(notification_service)

    # Регистрируем роутеры (ВАЖЕН ПОРЯДОК!)
    dp.include_router(admin_edit_router)  # НОВЫЙ: Редактирование админских сущностей
    dp.include_router(admin_router)  # Основные админские обработчики
    dp.include_router(registration_router)  # Регистрационные обработчики
    dp.include_router(cashier_router)  # Обработчики кассира
    dp.include_router(parent_edit_router)  # НОВЫЙ: Редактирование родителями
    dp.include_router(parent_router)  # Основные обработчики родителей
    dp.include_router(payment_router)  # Обработчики оплат
    dp.include_router(reports_router)  # Обработчики отчетов
    dp.include_router(router)  # Основные обработчики
    dp.include_router(unknown_router)  # ПОСЛЕДНИМ - обработчик неизвестных команд

    # Запускаем планировщик ежедневных отчётов в фоне
    asyncio.create_task(schedule_daily_reports(bot))

    try:
        logger.info("🚀 Бот запущен на SQLite с функциями редактирования")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота...")
    finally:
        await db.close()
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")