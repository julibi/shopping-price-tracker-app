from sqlalchemy import Column, Integer, String

from .database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    url = Column(String, index=True)
    product_name = Column(String, index=True)
    price = Column(String, index=True)
    currency = Column(String, index=True)
