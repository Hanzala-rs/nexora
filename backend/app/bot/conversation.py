"""Conversation persistence and idempotency for inbound WhatsApp messages."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.bot import engine
from app.bot.content import load_content
from app.config import get_settings
from app.models import ConsultationRequest, Conversation, HandoffRequest, Message

IDLE_TIMEOUT = timedelta(hours=24)


def _new_reference() -> str:
    return "NX-" + secrets.token_hex(4).upper()


def whatsapp_message(db: Session, wa_id: str, wa_message_id: str, action_id: str | None,
                     title: str | None, text: str | None) -> list[dict] | None:
    """Process one inbound WhatsApp message. Returns replies to send, or None for a duplicate delivery."""
    db.execute(
        insert(Conversation)
        .values(id=uuid.uuid4(), channel="whatsapp", user_ref=wa_id, state="LANG_SELECT", context={})
        .on_conflict_do_nothing(index_elements=["channel", "user_ref"])
    )
    # Row lock serializes concurrent deliveries for the same user.
    conv = db.scalar(select(Conversation)
                     .where(Conversation.channel == "whatsapp", Conversation.user_ref == wa_id)
                     .with_for_update())
    if db.scalar(select(Message.id).where(Message.conversation_id == conv.id,
                                          Message.client_msg_id == wa_message_id)):
        db.rollback()
        return None

    settings = get_settings()
    now = datetime.now(timezone.utc)
    if now - conv.updated_at > IDLE_TIMEOUT:
        conv.state = "MENU" if conv.language else "LANG_SELECT"
        conv.context = {}

    today = datetime.now(ZoneInfo(settings.business_timezone)).date()
    dates = engine.offered_dates(today, settings.working_days, settings.booking_days_ahead)
    result = engine.handle(conv.state, conv.language, conv.context or {}, action_id, text,
                           load_content(db), dates, _new_reference)

    if result.stored_input is not None:
        payload = result.stored_input
    elif action_id is not None:
        payload = {"action_id": action_id, "title": title}
    elif text is not None:
        payload = {"text": text}
    else:
        payload = {"unsupported": True}

    inbound = Message(conversation_id=conv.id, direction="in", payload=payload, client_msg_id=wa_message_id)
    db.add(inbound)
    db.flush()
    db.add_all(Message(conversation_id=conv.id, direction="out", payload=reply, reply_to=inbound.id)
               for reply in result.replies)
    if result.booking:
        db.add(ConsultationRequest(conversation_id=conv.id, phone=wa_id, **result.booking))
    if result.handoff and not db.scalar(select(HandoffRequest.id).where(
            HandoffRequest.conversation_id == conv.id, HandoffRequest.status == "open")):
        db.add(HandoffRequest(conversation_id=conv.id))

    conv.state, conv.language, conv.context, conv.updated_at = result.state, result.language, result.context, now
    db.commit()
    return result.replies
