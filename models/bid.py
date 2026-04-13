from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (
        UniqueConstraint("auction_id", "user_id", name="uq_bid_auction_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    auction_id: Mapped[int] = mapped_column(Integer, ForeignKey("auctions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    auction: Mapped["Auction"] = relationship("Auction", back_populates="bids")
    user: Mapped["User"] = relationship("User", back_populates="bids")
