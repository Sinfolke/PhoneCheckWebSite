from enum import Enum
from typing import Optional
from xmlrpc.client import DateTime

from pydantic import BaseModel
class payWith(str, Enum):
    cash = "cash"
    card = "card"
    card_now = "card-now"

class Order(BaseModel):
    name: str
    contact: str
    model: str
    ad_link: Optional[str] = None
    latitude: float
    longitude: float
    meeting_time: str
    payment_method: payWith