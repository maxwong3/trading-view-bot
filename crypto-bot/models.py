from pydantic import BaseModel
from typing import Optional

class AlertPayload(BaseModel):
    server_id: int
    ticker: str
    alert: str
    secret: Optional[str] = None
    signal_type: Optional[str] = None
    time: Optional[str] = None
    open: Optional[float] = None
    close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    interval: Optional[str] = None
    exchange: Optional[str] = None