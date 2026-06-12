import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from src.database.db import Database

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseMiddleware):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Extract from_user depending on the event type (Message, CallbackQuery, etc.)
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            # Let it pass if we can't extract a user (e.g. system messages)
            return await handler(event, data)

        # Check whitelist in DB
        db_user = await self.db.get_user_by_telegram_id(user.id)
        if not db_user:
            logger.warning(
                f"Unauthorized access attempt by Telegram User: {user.full_name} (@{user.username}, ID: {user.id})"
            )
            # Silent drop. If it's a private chat, we can optionally notify them.
            if isinstance(event, Message) and event.chat.type == "private":
                await event.answer("🔒 Вы не зарегистрированы в системе. Доступ запрещен.")
            return

        # Inject database user context into handler data dictionary
        data["db_user"] = db_user
        return await handler(event, data)
