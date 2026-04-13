from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    iin: Mapped[str] = mapped_column(String(12), nullable=False)
    bank_account: Mapped[str] = mapped_column(String(34), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_review")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    bids: Mapped[list["Bid"]] = relationship("Bid", back_populates="user")

    # Statuses: pending_review | approved_waiting_payment | payment_pending_check | approved | rejected
