import httpx
import pytest
import respx

from app.config import Settings
from app.whatsapp import WhatsAppClient, parse_messages, verify_signature


@pytest.mark.anyio
@respx.mock
async def test_send_text_calls_graph_api():
    settings = Settings(whatsapp_token="tkn", whatsapp_phone_number_id="123", graph_api_version="v21.0")
    route = respx.post("https://graph.facebook.com/v21.0/123/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.ok"}]})
    )
    client = WhatsAppClient(settings)
    result = await client.send_text("9230000", "hello")
    await client.aclose()

    assert result["messages"][0]["id"] == "wamid.ok"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer tkn"
    assert b'"to":"9230000"' in request.content.replace(b" ", b"")


def test_signature_helper():
    assert not verify_signature("s", b"{}", None)
    assert not verify_signature("s", b"{}", "md5=abc")


def test_parse_button_reply():
    payload = {"entry": [{"changes": [{"value": {"messages": [{
        "id": "w1", "from": "92", "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "1", "title": "Track order"}},
    }]}}]}]}
    [msg] = parse_messages(payload)
    assert msg.text == "1" and msg.name is None


@pytest.fixture
def anyio_backend():
    return "asyncio"
