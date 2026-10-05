"""Conversation logic. Pure functions over the database, so it is easy to test."""

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Conversation, Order

MENU = (
    "Hi{name}! Welcome to {business}.\n"
    "Reply with a number:\n"
    "1. Track my order\n"
    "2. Business hours\n"
    "3. Talk to a person"
)

RESTART_WORDS = {"hi", "hello", "menu", "start", "salam", "0"}


def _menu(conv: Conversation, settings: Settings) -> str:
    name = f" {conv.name.split()[0]}" if conv.name else ""
    return MENU.format(name=name, business=settings.business_name)


def handle_message(db: Session, settings: Settings, wa_id: str, name: str | None, text: str) -> str | None:
    """Update the user's conversation state and return the reply text (None means stay silent)."""
    conv = db.get(Conversation, wa_id)
    if conv is None:
        conv = Conversation(wa_id=wa_id, name=name, state="MENU")
        db.add(conv)
    conv.last_message = text
    if name:
        conv.name = name

    lowered = text.lower().strip()

    if conv.handed_off:
        if lowered == "menu":
            conv.handed_off = False
            conv.state = "MENU"
            db.commit()
            return _menu(conv, settings)
        db.commit()
        return None  # a human agent is handling this chat

    if lowered in RESTART_WORDS:
        conv.state = "MENU"
        reply = _menu(conv, settings)
    elif conv.state == "AWAITING_ORDER_NUMBER":
        reply = _order_status(db, text.upper().replace("#", "").strip())
        conv.state = "MENU"
    elif lowered == "1":
        conv.state = "AWAITING_ORDER_NUMBER"
        reply = "Please send your order number (for example: A1001)."
    elif lowered == "2":
        reply = f"We are open {settings.business_hours}. Reply 'menu' to go back."
    elif lowered == "3":
        conv.handed_off = True
        conv.state = "HUMAN"
        reply = "Thanks! A team member will reply here shortly. Reply 'menu' anytime to return to the bot."
    else:
        reply = "Sorry, I did not understand that.\n\n" + _menu(conv, settings)

    db.commit()
    return reply


def _order_status(db: Session, number: str) -> str:
    order = db.get(Order, number)
    if order is None:
        return f"I could not find order {number}. Please check the number, or reply 3 to talk to a person."
    eta = f" Expected delivery: {order.eta}." if order.eta else ""
    return f"Order {order.number} is {order.status}.{eta}\n\nReply 'menu' for more options."
