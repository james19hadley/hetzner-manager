import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from src.database.db import Database
from src.bot.middleware.auth import AuthMiddleware
from src.bot.handlers import router
from src.bot.alerts import monitor_alerts

# Load environment variables
load_dotenv()

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hetzner_bot")

async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    db_path = os.getenv("DATABASE_PATH", "data/bot_state.db")
    if not os.path.isabs(db_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, db_path)

    # Initialize Database
    db = Database(db_path)
    await db.initialize()

    # Pre-populate default admin user if configured in env
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if admin_id:
        try:
            admin_id = int(admin_id)
            existing = await db.get_user_by_telegram_id(admin_id)
            if not existing:
                uid = await db.add_user("Admin")
                await db.register_telegram_account(admin_id, uid, "Primary Admin Account")
                logger.info(f"Pre-registered primary admin Telegram ID: {admin_id}")
        except Exception as e:
            logger.error(f"Failed to auto-register admin: {e}")

    # Initialize Bot & Dispatcher
    bot = Bot(token=token)
    dp = Dispatcher()

    # Set Bot Commands
    commands = [
        BotCommand(command="start", description="Запуск и справка"),
        BotCommand(command="sysinfo", description="Метрики системы (CPU, RAM, Диск)"),
        BotCommand(command="daemons", description="Статус системных служб (Systemd)"),
        BotCommand(command="docker", description="Статус Docker-контейнеров"),
        BotCommand(command="restart_daemon", description="Перезапустить службу: /restart_daemon <имя>"),
        BotCommand(command="restart_container", description="Перезапустить контейнер: /restart_container <имя>"),
        BotCommand(command="sysusers", description="Список пользователей системы"),
        BotCommand(command="sysgroups", description="Список групп системы"),
        BotCommand(command="syssudoers", description="Список прав sudoers"),
        BotCommand(command="syschmod", description="Изменить права: /syschmod <права> <путь>"),
        BotCommand(command="syschown", description="Изменить владельца: /syschown <пользователь:группа> <путь>"),
        BotCommand(command="sysusermod", description="Изменить пользователя: /sysusermod <аргументы>"),
        BotCommand(command="sysuseradd", description="Добавить пользователя: /sysuseradd <аргументы>"),
        BotCommand(command="sysuserdel", description="Удалить пользователя: /sysuserdel <имя>"),
        BotCommand(command="sh_status", description="Статус текущей сессии шелла"),
        BotCommand(command="su", description="Сменить пользователя сессии: /su <имя>"),
        BotCommand(command="sh", description="Выполнить команду или войти в интерактивный шелл"),
        BotCommand(command="sh_exit", description="Выйти из интерактивного режима шелла")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot commands registered.")

    # Register Middlewares
    dp.message.outer_middleware(AuthMiddleware(db))
    dp.callback_query.outer_middleware(AuthMiddleware(db))

    # Include Handlers Router
    dp.include_router(router)

    # Inject DB context
    dp["db"] = db

    logger.info("Bot starting...")
    alerts_task = asyncio.create_task(monitor_alerts(bot, db))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        alerts_task.cancel()
        try:
            await alerts_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        logger.info("Bot shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution interrupted.")
