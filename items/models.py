from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    product_name: Mapped[str] = mapped_column(String, unique=True)
    price: Mapped[str] = mapped_column(String, index=True)
    currency: Mapped[str] = mapped_column(String, index=True)
    last_updated: datetime = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)  # Use timezone-aware datetime

