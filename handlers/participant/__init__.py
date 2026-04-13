from aiogram import Router

from .auctions import router as auctions_router

router = Router()
router.include_router(auctions_router)
