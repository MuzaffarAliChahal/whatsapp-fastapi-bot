from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    """One row per WhatsApp user: where they are in the menu flow."""

    __tablename__ = "conversations"

    wa_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(32), default="MENU")
    handed_off: Mapped[bool] = mapped_column(default=False)
    last_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Order(Base):
    __tablename__ = "orders"

    number: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_phone: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    eta: Mapped[str | None] = mapped_column(String(64))


class ProcessedMessage(Base):
    """WhatsApp may deliver the same webhook more than once; we remember message ids."""

    __tablename__ = "processed_messages"

    message_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
