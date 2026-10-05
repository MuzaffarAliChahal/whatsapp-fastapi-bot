from app.bot import handle_message
from app.config import Settings
from app.db import Base, engine
from app.models import Conversation, Order

settings = Settings(business_name="Test Shop", business_hours="9 to 5")


def setup_function():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_unknown_text_shows_menu(db):
    reply = handle_message(db, settings, "1", None, "blah")
    assert reply.startswith("Sorry") and "Test Shop" in reply


def test_business_hours(db):
    assert "9 to 5" in handle_message(db, settings, "1", None, "2")


def test_unknown_order(db):
    handle_message(db, settings, "1", None, "1")
    reply = handle_message(db, settings, "1", None, "zz99")
    assert "could not find order ZZ99" in reply
    assert db.get(Conversation, "1").state == "MENU"


def test_known_order_without_eta(db):
    db.add(Order(number="B7", customer_phone="1", status="packed", eta=None))
    db.commit()
    handle_message(db, settings, "1", None, "1")
    assert handle_message(db, settings, "1", None, "b7").startswith("Order B7 is packed.")


def test_menu_word_ends_handoff(db):
    handle_message(db, settings, "1", None, "3")
    assert handle_message(db, settings, "1", None, "anyone?") is None
    reply = handle_message(db, settings, "1", None, "menu")
    assert "Track my order" in reply
    assert db.get(Conversation, "1").handed_off is False
