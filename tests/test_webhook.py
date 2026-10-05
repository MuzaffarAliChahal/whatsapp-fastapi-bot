from tests.conftest import sign, text_payload


def post(client, body: bytes, signature: str | None = None):
    headers = {"Content-Type": "application/json"}
    headers["X-Hub-Signature-256"] = signature if signature is not None else sign(body)
    return client.post("/webhook", content=body, headers=headers)


def test_verification_handshake(client):
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"})
    assert bad.status_code == 403


def test_rejects_bad_signature(client, fake_wa):
    body = text_payload("hi")
    assert post(client, body, "sha256=deadbeef").status_code == 403
    assert fake_wa.sent == []


def test_menu_reply_is_sent(client, fake_wa):
    response = post(client, text_payload("hi"))
    assert response.status_code == 200
    assert response.json() == {"received": 1}
    to, body = fake_wa.sent[0]
    assert to == "923001234567"
    assert "Hi Ali" in body and "1. Track my order" in body


def test_duplicate_delivery_is_ignored(client, fake_wa):
    body = text_payload("hi", msg_id="wamid.same")
    post(client, body)
    second = post(client, body)
    assert second.json() == {"received": 0}
    assert len(fake_wa.sent) == 1


def test_order_tracking_flow(client, fake_wa):
    client.put("/api/orders", json={"number": "a1001", "customer_phone": "923001234567",
                                     "status": "out for delivery", "eta": "today by 6 PM"})
    post(client, text_payload("1", msg_id="m1"))
    post(client, text_payload("#a1001", msg_id="m2"))
    assert "Order A1001 is out for delivery" in fake_wa.sent[-1][1]
    assert "today by 6 PM" in fake_wa.sent[-1][1]


def test_status_updates_are_ignored(client, fake_wa):
    body = b'{"entry":[{"changes":[{"value":{"statuses":[{"id":"wamid.x","status":"read"}]}}]}]}'
    assert post(client, body).json() == {"received": 0}
    assert fake_wa.sent == []


def test_handoff_and_agent_reply(client, fake_wa):
    post(client, text_payload("3", msg_id="h1"))
    post(client, text_payload("where is my parcel?", msg_id="h2"))
    assert len(fake_wa.sent) == 1  # bot stays quiet after handoff

    waiting = client.get("/api/conversations", params={"handed_off": True}).json()
    assert waiting[0]["wa_id"] == "923001234567"

    r = client.post("/api/conversations/923001234567/reply", json={"text": "Hello, this is Sara from support."})
    assert r.status_code == 202
    assert fake_wa.sent[-1] == ("923001234567", "Hello, this is Sara from support.")
