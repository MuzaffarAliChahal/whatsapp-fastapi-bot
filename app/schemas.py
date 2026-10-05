from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderIn(BaseModel):
    number: str = Field(min_length=2, max_length=20, examples=["A1001"])
    customer_phone: str = Field(min_length=6, max_length=32, examples=["923001234567"])
    status: str = Field(min_length=2, max_length=32, examples=["out for delivery"])
    eta: str | None = Field(default=None, max_length=64, examples=["today by 6 PM"])


class OrderOut(OrderIn):
    model_config = ConfigDict(from_attributes=True)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wa_id: str
    name: str | None
    state: str
    handed_off: bool
    last_message: str | None
    updated_at: datetime


class AgentReply(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
