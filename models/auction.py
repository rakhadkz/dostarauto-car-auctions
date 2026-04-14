from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Auction(Base):
    __tablename__ = "auctions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    min_bid: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    bid_step: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=100000)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    winner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    photos: Mapped[list["AuctionPhoto"]] = relationship(
        "AuctionPhoto", back_populates="auction", cascade="all, delete-orphan"
    )
    bids: Mapped[list["Bid"]] = relationship(
        "Bid", back_populates="auction", cascade="all, delete-orphan"
    )
    winner: Mapped["User | None"] = relationship("User", foreign_keys=[winner_id])

    # Statuses: active | finished


class AuctionPhoto(Base):
    __tablename__ = "auction_photos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    auction_id: Mapped[int] = mapped_column(Integer, ForeignKey("auctions.id"), nullable=False)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)

    auction: Mapped["Auction"] = relationship("Auction", back_populates="photos")
