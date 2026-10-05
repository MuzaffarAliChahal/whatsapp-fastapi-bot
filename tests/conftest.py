import hashlib
import hmac
import json
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["WHATSAPP_APP_SECRET"] = "test-secret"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "verify-me"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app, get_wa_client  # noqa: E402


class FakeWhatsAppClient:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, to: str, body: str) -> dict:
        self.sent.append((to, body))
        return {"messages": [{"id": "wamid.fake"}]}

    async def aclose(self) -> None:
        pass


@pytest.fixture
def fake_wa():
    return FakeWhatsAppClient()


@pytest.fixture
def client(fake_wa):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_wa_client] = lambda: fake_wa
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def sign(body: bytes, secret: str = "test-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def text_payload(text: str, wa_id: str = "923001234567", msg_id: str = "wamid.1", name: str = "Ali Khan") -> bytes:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": wa_id, "profile": {"name": name}}],
                    "messages": [{"id": msg_id, "from": wa_id, "type": "text", "text": {"body": text}}],
                },
            }],
        }],
    }
    return json.dumps(payload).encode()
