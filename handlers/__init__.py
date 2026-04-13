from .admin import router as admin_router
from .common import router as common_router
from .participant import router as participant_router
from .registration import router as registration_router

__all__ = ["common_router", "registration_router", "admin_router", "participant_router"]
