from pydantic import BaseModel


class ItemBase(BaseModel):
    url: str
    product_name: str
    price: str
    currency: str


class ItemCreate(ItemBase):
    pass


class Item(ItemBase):
    id: int
