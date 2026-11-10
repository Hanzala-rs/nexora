"""Meta WhatsApp Cloud API webhook."""
import hmac
import json

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app import whatsapp
from app.bot import conversation
from app.config import get_settings
from app.db import get_db
from app.errors import ApiError

router = APIRouter(prefix="/webhook")


@router.get("")
def verify(request: Request):
    params = request.query_params
    token, expected = params.get("hub.verify_token", ""), get_settings().wa_verify_token
    if params.get("hub.mode") == "subscribe" and expected and hmac.compare_digest(token, expected):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise ApiError(403, "forbidden", "Webhook verification failed.")


def _handle(db: Session, data: dict, background: BackgroundTasks) -> None:
    for m in whatsapp.parse_messages(data):
        replies = conversation.whatsapp_message(db, m["wa_id"], m["wa_message_id"], m["action_id"], m["title"], m["text"])
        if replies:
            background.add_task(whatsapp.send_replies, m["wa_id"], replies)


@router.post("")
async def receive(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.body()
    if not whatsapp.verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise ApiError(401, "invalid_signature", "Invalid signature.")
    try:
        data = json.loads(body)
    except ValueError:
        raise ApiError(400, "invalid_request", "Invalid JSON.")
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_request", "Invalid payload.")
    await run_in_threadpool(_handle, db, data, background)
    return {"status": "ok"}
