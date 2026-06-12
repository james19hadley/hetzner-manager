from aiogram import Router
from src.bot.handlers.base import router as base_router
from src.bot.handlers.message import router as message_router

router = Router()
router.include_router(base_router)
router.include_router(message_router)
