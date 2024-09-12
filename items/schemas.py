from pydantic import BaseModel


class ItemBase(BaseModel):
    url: str
    product_name: str
    price: float
    currency: str


class ItemCreate(ItemBase):
    pass


class Item(ItemBase):
    id: int
