from typing import Optional
from pydantic import BaseModel



class ProductCreate(BaseModel):
    name:str
    barcode: Optional[str] = None
    buying_price: float
    selling_price: float
    stock_quantity: int = 0
    min_stock_alert: int = 0


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    barcode: Optional[str] = None
    buying_price: Optional[float] = None
    selling_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    min_stock_alert: Optional[int] = None
    is_active: Optional[bool] = None


class ProductRead(BaseModel):
    id: int
    shop_id: int
    name: str
    barcode: Optional[str]
    buying_price: float
    selling_price: float
    stock_quantity: int
    min_stock_alert: int
    is_active: bool

    class Config:
        from_attributes = True