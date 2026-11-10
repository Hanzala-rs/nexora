"""Meta WhatsApp Cloud API: signature check, inbound parsing, outbound sending."""
import hashlib
import hmac
import logging

import httpx

from app.bot.engine import ACTION_ID_RE
from app.config import get_settings

log = logging.getLogger(__name__)
MAX_TEXT = 500
_client: httpx.Client | None = None


def verify_signature(body: bytes, header: str | None) -> bool:
    secret = get_settings().wa_app_secret
    if not secret or not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def parse_messages(data: dict) -> list[dict]:
    """Extract inbound user messages from a webhook payload. Status updates are ignored."""
    messages = []
    for entry in data.get("entry") or []:
        for change in entry.get("changes") or []:
            for m in (change.get("value") or {}).get("messages") or []:
                wa_id, msg_id = str(m.get("from", "")), str(m.get("id", ""))
                if not (wa_id.isdigit() and len(wa_id) <= 32 and 0 < len(msg_id) <= 128):
                    continue
                action_id = title = text = None
                if m.get("type") == "text":
                    text = str((m.get("text") or {}).get("body", "")).strip()[:MAX_TEXT]
                elif m.get("type") == "interactive":
                    interactive = m.get("interactive") or {}
                    reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
                    if ACTION_ID_RE.match(str(reply.get("id", ""))):
                        action_id, title = reply["id"], str(reply.get("title", ""))[:64]
                messages.append({"wa_id": wa_id, "wa_message_id": msg_id,
                                 "action_id": action_id, "title": title, "text": text})
    return messages


def to_cloud_payload(to: str, message: dict) -> dict:
    """Convert a bot message object (see docs/architecture.md) to a Cloud API request body."""
    base = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
    if message["type"] == "text":
        return base | {"type": "text", "text": {"body": message["text"]}}
    if message["type"] == "buttons":
        action = {"buttons": [{"type": "reply", "reply": {"id": o["id"], "title": o["title"]}}
                              for o in message["options"]]}
        return base | {"type": "interactive",
                       "interactive": {"type": "button", "body": {"text": message["text"]}, "action": action}}
    rows = [{"id": o["id"], "title": o["title"], **({"description": o["description"]} if o.get("description") else {})}
            for o in message["options"]]
    action = {"button": message["button"], "sections": [{"rows": rows}]}
    return base | {"type": "interactive",
                   "interactive": {"type": "list", "body": {"text": message["text"]}, "action": action}}


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=10)
    return _client


def send_replies(to: str, replies: list[dict]) -> None:
    s = get_settings()
    if not (s.wa_access_token and s.wa_phone_number_id):
        log.warning("WhatsApp credentials not configured; %d replies not sent", len(replies))
        return
    url = f"https://graph.facebook.com/{s.wa_api_version}/{s.wa_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {s.wa_access_token}"}
    for message in replies:
        try:
            _http().post(url, json=to_cloud_payload(to, message), headers=headers).raise_for_status()
        except httpx.HTTPError as exc:  # recipient number deliberately not logged
            log.error("WhatsApp send failed: %s", exc.__class__.__name__)
            return  # keep order: stop after the first failure
