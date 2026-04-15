from aiogram import F, Router
from aiogram.types import CallbackQuery

from .auctions import router as auctions_router
from .staff import router as staff_router
from .users import router as users_router

router = Router()
# FSM routers first so state handlers take priority over text handlers
router.include_router(auctions_router)
router.include_router(staff_router)
router.include_router(users_router)


@router.callback_query(F.data == "noop")
async def _noop(callback: CallbackQuery) -> None:
    await callback.answer()
