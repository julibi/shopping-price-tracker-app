from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    product_name: Mapped[str] = mapped_column(String, unique=True)
    price: Mapped[str] = mapped_column(String, index=True)
    currency: Mapped[str] = mapped_column(String, index=True)
