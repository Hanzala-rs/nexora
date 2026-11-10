import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app import whatsapp
from app.models import ConsultationRequest, Conversation, HandoffRequest, Message

WA_ID = "966500000001"


def signed_post(client, payload, secret="test-app-secret"):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig,
                                                          "Content-Type": "application/json"})


def inbound(msg_id, **message):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp",
        "messages": [{"from": WA_ID, "id": msg_id, "timestamp": "1762770000", **message}]}}]}]}


def text_msg(msg_id, body):
    return inbound(msg_id, type="text", text={"body": body})


def button_msg(msg_id, action_id, title="x", kind="button_reply"):
    return inbound(msg_id, type="interactive",
                   interactive={"type": kind, kind: {"id": action_id, "title": title}})


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(whatsapp, "send_replies", lambda to, replies: calls.append((to, replies)))
    return calls


def test_verify_handshake(client):
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "test-verify-token",
                                        "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong",
                                         "hub.challenge": "12345"})
    assert bad.status_code == 403


def test_rejects_invalid_signature(client, sent, db):
    assert signed_post(client, text_msg("wamid.1", "hi"), secret="wrong").status_code == 401
    assert client.post("/webhook", json=text_msg("wamid.1", "hi")).status_code == 401
    assert sent == [] and db.scalar(select(func.count()).select_from(Conversation)) == 0


def test_first_message_gets_language_selection_and_duplicates_are_ignored(client, sent, db):
    assert signed_post(client, text_msg("wamid.1", "hi")).status_code == 200
    assert len(sent) == 1 and sent[0][0] == WA_ID
    assert [o["id"] for o in sent[0][1][0]["options"]] == ["lang_en", "lang_ar"]
    messages = db.scalar(select(func.count()).select_from(Message))
    assert signed_post(client, text_msg("wamid.1", "hi")).status_code == 200  # Meta retry
    assert len(sent) == 1 and db.scalar(select(func.count()).select_from(Message)) == messages


def test_button_and_list_replies_drive_the_flow(client, sent, db):
    signed_post(client, text_msg("wamid.1", "hi"))
    signed_post(client, button_msg("wamid.2", "lang_ar", "العربية"))
    menu = sent[-1][1][0]
    assert menu["type"] == "list" and menu["button"] == "عرض الخيارات"
    signed_post(client, button_msg("wamid.3", "book_start", kind="list_reply"))
    signed_post(client, button_msg("wamid.4", "svc_hr", kind="list_reply"))
    signed_post(client, text_msg("wamid.5", "سارة أحمد"))
    signed_post(client, text_msg("wamid.6", "sara@example.com"))
    date_id = sent[-1][1][0]["options"][0]["id"]
    signed_post(client, button_msg("wamid.7", date_id, kind="list_reply"))
    signed_post(client, button_msg("wamid.8", "slot_morning"))
    signed_post(client, button_msg("wamid.9", "book_confirm"))
    booking = db.scalars(select(ConsultationRequest)).one()
    assert (booking.phone, booking.language, booking.name) == (WA_ID, "ar", "سارة أحمد")
    stored = db.scalars(select(Message.payload).where(Message.client_msg_id == "wamid.6")).one()
    assert stored == {"text": "s***@example.com", "redacted": True}


def test_status_updates_and_unsupported_messages(client, sent):
    status = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.x", "status": "read"}]}}]}]}
    assert signed_post(client, status).status_code == 200 and sent == []
    signed_post(client, inbound("wamid.img", type="image", image={"id": "1"}))
    assert [o["id"] for o in sent[0][1][0]["options"]] == ["lang_en", "lang_ar"]


def test_cloud_payload_shapes():
    text = whatsapp.to_cloud_payload(WA_ID, {"type": "text", "text": "hi"})
    assert text["type"] == "text" and text["text"] == {"body": "hi"}
    buttons = whatsapp.to_cloud_payload(WA_ID, {"type": "buttons", "text": "t",
                                                "options": [{"id": "a", "title": "A"}]})
    assert buttons["interactive"]["action"]["buttons"] == [{"type": "reply", "reply": {"id": "a", "title": "A"}}]
    lst = whatsapp.to_cloud_payload(WA_ID, {"type": "list", "text": "t", "button": "View",
                                            "options": [{"id": "a", "title": "A"}]})
    assert lst["interactive"]["action"] == {"button": "View", "sections": [{"rows": [{"id": "a", "title": "A"}]}]}


def count(db, model):
    db.rollback()
    return db.scalar(select(func.count()).select_from(model))


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_handoff_creates_single_request_and_menu_returns(client, sent, db):
    signed_post(client, text_msg("wamid.1", "hi"))
    signed_post(client, button_msg("wamid.2", "lang_en"))
    signed_post(client, button_msg("wamid.3", "handoff"))
    replies_before = len(sent)
    signed_post(client, text_msg("wamid.4", "hello?"))  # HUMAN: silent
    assert len(sent) == replies_before
    signed_post(client, button_msg("wamid.5", "handoff"))
    assert count(db, HandoffRequest) == 1
    signed_post(client, text_msg("wamid.6", "menu"))
    assert sent[-1][1][0]["type"] == "list"
    assert db.scalar(select(Conversation.state)) == "MENU"
    assert db.scalar(select(HandoffRequest.status)) == "open"


def test_idle_conversation_restarts_at_main_menu(client, sent, db):
    signed_post(client, text_msg("wamid.1", "hi"))
    signed_post(client, button_msg("wamid.2", "lang_en"))
    signed_post(client, button_msg("wamid.3", "book_start"))
    db.execute(update(Conversation).values(updated_at=datetime.now(timezone.utc) - timedelta(hours=25)))
    db.commit()
    signed_post(client, text_msg("wamid.4", "Sara"))  # a name in BOOK_SERVICE context, unknown after reset
    assert sent[-1][1][0]["text"].startswith("Sorry")
    assert db.scalar(select(Conversation.state)) == "MENU"
    assert db.scalar(select(Conversation.context)) == {}


def test_concurrent_duplicate_deliveries_create_one_booking(client, sent, db):
    from concurrent.futures import ThreadPoolExecutor

    from app.bot import conversation
    from app.db import SessionLocal

    for msg in [text_msg("w1", "hi"), button_msg("w2", "lang_en"), button_msg("w3", "book_start"),
                             button_msg("w4", "svc_hr"), text_msg("w5", "Sara Ahmed"),
                             text_msg("w6", "sara@example.com")]:
        signed_post(client, msg)
    signed_post(client, button_msg("w7", sent[-1][1][0]["options"][0]["id"]))
    signed_post(client, button_msg("w8", "slot_morning"))

    def confirm(_):
        with SessionLocal() as s:
            return conversation.whatsapp_message(s, WA_ID, "w9", "book_confirm", "Confirm", None)

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(confirm, range(4)))
    assert sum(r is not None for r in results) == 1  # one processed, three ignored as duplicates
    assert count(db, ConsultationRequest) == 1
