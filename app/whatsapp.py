"""Thin client for the WhatsApp Cloud API plus webhook helpers."""

import hashlib
import hmac
from dataclasses import dataclass

import httpx

from app.config import Settings


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Check Meta's X-Hub-Signature-256 header (HMAC-SHA256 of the raw body)."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    wa_id: str
    name: str | None
    text: str


def parse_messages(payload: dict) -> list[IncomingMessage]:
    """Extract text and button replies from a webhook payload. Status updates are ignored."""
    result: list[IncomingMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                text = ""
                if msg.get("type") == "text":
                    text = msg.get("text", {}).get("body", "")
                elif msg.get("type") == "interactive":
                    reply = msg.get("interactive", {})
                    text = (reply.get("button_reply") or reply.get("list_reply") or {}).get("id", "")
                if not text:
                    continue
                result.append(
                    IncomingMessage(
                        message_id=msg["id"],
                        wa_id=msg["from"],
                        name=names.get(msg["from"]),
                        text=text.strip(),
                    )
                )
    return result


class WhatsAppClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self._settings = settings
        self._http = http or httpx.AsyncClient(timeout=10)

    @property
    def messages_url(self) -> str:
        s = self._settings
        return f"{s.graph_api_base}/{s.graph_api_version}/{s.whatsapp_phone_number_id}/messages"

    async def send_text(self, to: str, body: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        headers = {"Authorization": f"Bearer {self._settings.whatsapp_token}"}
        response = await self._http.post(self.messages_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        await self._http.aclose()
