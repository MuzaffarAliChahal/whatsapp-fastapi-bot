import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bot import handle_message
from app.config import Settings, get_settings
from app.db import Base, engine, get_db
from app.models import Conversation, Order, ProcessedMessage
from app.schemas import AgentReply, ConversationOut, OrderIn, OrderOut
from app.whatsapp import WhatsAppClient, parse_messages, verify_signature

log = logging.getLogger("whatsapp-bot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    app.state.wa_client = WhatsAppClient(get_settings())
    yield
    await app.state.wa_client.aclose()


app = FastAPI(
    title="WhatsApp Support Bot",
    description="FastAPI webhook for the WhatsApp Cloud API: order tracking, FAQ and human handoff.",
    version="1.0.0",
    lifespan=lifespan,
)


def get_wa_client(request: Request) -> WhatsAppClient:
    return request.app.state.wa_client


async def send_reply(client: WhatsAppClient, to: str, text: str) -> None:
    try:
        await client.send_text(to, text)
    except Exception:  # never let a failed send crash the webhook worker
        log.exception("Failed to send WhatsApp message to %s", to)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/webhook", response_class=PlainTextResponse, tags=["webhook"])
def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> str:
    """Meta calls this once when you register the webhook URL."""
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return challenge
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")


@app.post("/webhook", tags=["webhook"])
async def receive_webhook(
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: WhatsAppClient = Depends(get_wa_client),
) -> dict:
    body = await request.body()
    if not verify_signature(settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid signature")

    handled = 0
    for msg in parse_messages(await request.json()):
        try:
            db.add(ProcessedMessage(message_id=msg.message_id))
            db.commit()
        except IntegrityError:  # duplicate delivery, already answered
            db.rollback()
            continue
        reply = handle_message(db, settings, msg.wa_id, msg.name, msg.text)
        if reply:
            background.add_task(send_reply, client, msg.wa_id, reply)
        handled += 1
    # Always answer 200 quickly, otherwise Meta retries the delivery.
    return {"received": handled}


# ---- Admin API (protect it behind your gateway or VPN in production) ----

@app.put("/api/orders", response_model=OrderOut, tags=["admin"])
def upsert_order(order: OrderIn, db: Session = Depends(get_db)) -> Order:
    entity = db.get(Order, order.number.upper()) or Order(number=order.number.upper())
    entity.customer_phone = order.customer_phone
    entity.status = order.status
    entity.eta = order.eta
    db.add(entity)
    db.commit()
    return entity


@app.get("/api/conversations", response_model=list[ConversationOut], tags=["admin"])
def list_conversations(handed_off: bool | None = None, db: Session = Depends(get_db)) -> list[Conversation]:
    query = select(Conversation).order_by(Conversation.updated_at.desc())
    if handed_off is not None:
        query = query.where(Conversation.handed_off == handed_off)
    return list(db.scalars(query))


@app.post("/api/conversations/{wa_id}/reply", status_code=status.HTTP_202_ACCEPTED, tags=["admin"])
async def agent_reply(
    wa_id: str,
    reply: AgentReply,
    db: Session = Depends(get_db),
    client: WhatsAppClient = Depends(get_wa_client),
) -> Response:
    """Lets a human agent answer a handed-off chat from a dashboard."""
    if db.get(Conversation, wa_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    await client.send_text(wa_id, reply.text)
    return Response(status_code=status.HTTP_202_ACCEPTED)
