from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class product(SQLModel,table=True):
    id: Optional[int] = Field(default=None,primary_key=True)
    shop_id: int
    name: str
    barcode: Optional[str]= None
    buying_price: float
    selling_price: float
    stock_quantity: int = 0
    min_stock_alert: int = 0
    is_active:bool
    create_at:datetime= Field(default_factory=datetime.utcnow)
    updatd_at:datetime= Field(deafult_factory=datetime.utcnow)