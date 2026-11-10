"""Deterministic conversation state machine. Pure logic: no HTTP, no database."""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

ACTION_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")

ROOT = "menu_main"
SERVICES = "menu_services"
GLOBAL_ACTIONS = {ROOT, "change_language", "handoff"}
MENU_KEYWORDS = {"menu", "القائمة", "0"}
LANG_ACTIONS = {"lang_en": "en", "lang_ar": "ar"}
SLOTS = ("slot_morning", "slot_afternoon")
BOOKING_STATES = {"BOOK_SERVICE", "BOOK_NAME", "BOOK_EMAIL", "BOOK_DATE", "BOOK_TIME", "BOOK_CONFIRM"}


@dataclass
class Node:
    action_id: str
    parent: str | None
    kind: str  # submenu | info | book | handoff
    title: dict[str, str]
    body: dict[str, str]


@dataclass
class Content:
    nodes: dict[str, Node]  # by action_id, in sort order
    texts: dict[tuple[str, str], str]  # (key, lang) -> text

    def text(self, key: str, lang: str) -> str:
        return self.texts[(key, lang)]

    def children(self, action_id: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.parent == action_id]


@dataclass
class Result:
    state: str
    language: str | None
    context: dict
    replies: list[dict] = field(default_factory=list)
    booking: dict | None = None  # consultation request to store
    handoff: bool = False  # handoff requested
    stored_input: dict | None = None  # replaces the raw input in message history (redaction)


def offered_dates(today: date, working_days: frozenset[int], count: int) -> list[date]:
    """The next `count` working days after `today` (today excluded)."""
    dates, d = [], today
    while len(dates) < count:
        d += timedelta(days=1)
        if d.weekday() in working_days:
            dates.append(d)
    return dates


def mask_email(value: str) -> str:
    if not EMAIL_RE.match(value):
        return "***"
    local, domain = value.split("@", 1)
    return f"{local[0]}***@{domain}"


# ---------- rendering ----------

def _message(c: Content, lang: str, text: str, options: list[tuple[str, str]] | None = None) -> dict:
    if not options:
        return {"type": "text", "text": text}
    opts = [{"id": i, "title": t} for i, t in options]
    if len(opts) <= 3:
        return {"type": "buttons", "text": text, "options": opts}
    return {"type": "list", "text": text, "button": c.text("list_button", lang), "options": opts}


def welcome(c: Content) -> dict:
    text = c.text("welcome", "en") + "\n" + c.text("welcome", "ar")
    return {"type": "buttons", "text": text, "options": [
        {"id": "lang_en", "title": c.text("lang_option", "en")},
        {"id": "lang_ar", "title": c.text("lang_option", "ar")},
    ]}


def _node_message(c: Content, lang: str, node: Node) -> dict:
    if node.kind == "submenu":
        options = [(n.action_id, n.title[lang]) for n in c.children(node.action_id)]
        if node.action_id == ROOT:
            options.append(("change_language", c.text("opt_change_language", lang)))
        else:
            options.append((ROOT, c.nodes[ROOT].title[lang]))
    else:  # info
        options = [(a, c.nodes[a].title[lang]) for a in ("book_start", ROOT, "handoff") if a in c.nodes]
    return _message(c, lang, node.body[lang], options)


def _date_title(c: Content, lang: str, d: date) -> str:
    weekday = c.text("weekdays", lang).split(",")[d.weekday()]
    month = c.text("months", lang).split(",")[d.month - 1]
    return f"{weekday} {d.day} {month}"


def _services(c: Content) -> list[Node]:
    return [n for n in c.children(SERVICES) if n.kind == "info"]


def _prompt(c: Content, state: str, lang: str, ctx: dict, dates: list[date]) -> list[dict]:
    """The current step's prompt, re-sent after invalid input."""
    booking = ctx.get("booking", {})
    if state == "LANG_SELECT":
        return [welcome(c)]
    if state == "MENU":
        return [_node_message(c, lang, c.nodes.get(ctx.get("node_id")) or c.nodes[ROOT])]
    if state == "BOOK_SERVICE":
        options = [(n.action_id, n.title[lang]) for n in _services(c)]
        return [_message(c, lang, c.text("book_choose_service", lang), options)]
    if state == "BOOK_NAME":
        return [_message(c, lang, c.text("book_ask_name", lang))]
    if state == "BOOK_EMAIL":
        return [_message(c, lang, c.text("book_ask_email", lang))]
    if state == "BOOK_DATE":
        options = [(f"date_{d.isoformat()}", _date_title(c, lang, d)) for d in dates]
        return [_message(c, lang, c.text("book_ask_date", lang), options)]
    if state == "BOOK_TIME":
        return [_message(c, lang, c.text("book_ask_time", lang), [(s, c.text(s, lang)) for s in SLOTS])]
    if state == "BOOK_CONFIRM":
        summary = c.text("book_summary", lang).format(
            service=c.nodes[booking["service"]].title[lang],
            name=booking["name"],
            email=mask_email(booking["email"]),
            date=_date_title(c, lang, date.fromisoformat(booking["date"])),
            slot=c.text(booking["slot"], lang),
        )
        options = [("book_confirm", c.text("book_confirm", lang)), ("book_cancel", c.text("book_cancel", lang))]
        return [_message(c, lang, summary, options)]
    return []  # HUMAN


# ---------- transitions ----------

def handle(
    state: str,
    language: str | None,
    context: dict,
    action_id: str | None,
    text: str | None,
    c: Content,
    dates: list[date],
    new_reference: Callable[[], str],
) -> Result:
    """Apply one user input. Exactly one of action_id/text is normally set; both None = unsupported input."""
    ctx = dict(context)
    if language is None:
        state = "LANG_SELECT"
    if state in BOOKING_STATES and "booking" not in ctx:
        state = "MENU"  # defensive: inconsistent stored state
    r = Result(state, language, ctx)

    if text is not None and text.strip().casefold() in MENU_KEYWORDS:
        action_id, text = ROOT, None
    if state == "BOOK_EMAIL" and text is not None:
        r.stored_input = {"text": mask_email(text.strip()), "redacted": True}

    def go(new_state: str, replies: list[dict]) -> Result:
        r.state = new_state
        r.replies = replies
        return r

    def hint() -> Result:
        return go(state, [_message(c, language, c.text("hint_choose", language))] + _prompt(c, state, language, ctx, dates))

    def main_menu(prefix: list[dict] | None = None) -> Result:
        ctx.pop("booking", None)
        ctx["node_id"] = ROOT
        return go("MENU", (prefix or []) + [_node_message(c, r.language, c.nodes[ROOT])])

    # Global actions: every state, checked first, always discard an unfinished booking.
    if action_id in GLOBAL_ACTIONS:
        ctx.pop("booking", None)
        if language is None:
            return go("LANG_SELECT", [welcome(c)])
        if action_id == ROOT:
            return main_menu()
        if action_id == "change_language":
            return go("LANG_SELECT", [welcome(c)])
        r.handoff = True
        return go("HUMAN", [_message(c, language, c.text("handoff_ack", language))])

    if state == "HUMAN":
        return r  # silent until a global action

    if state == "LANG_SELECT":
        if action_id in LANG_ACTIONS:
            r.language = LANG_ACTIONS[action_id]
            return main_menu()
        return go(state, [welcome(c)])

    lang = language
    booking = dict(ctx.get("booking", {}))

    def step(new_state: str, **values) -> Result:
        booking.update(values)
        ctx["booking"] = booking
        return go(new_state, _prompt(c, new_state, lang, ctx, dates))

    if state == "MENU":
        node = c.nodes.get(action_id) if action_id else None
        if node and node.kind == "book":
            ctx["booking"] = {}
            return go("BOOK_SERVICE", _prompt(c, "BOOK_SERVICE", lang, ctx, dates))
        if node and node.kind in ("submenu", "info"):
            ctx["node_id"] = node.action_id
            return go("MENU", [_node_message(c, lang, node)])
        return hint()

    if state == "BOOK_SERVICE":
        if action_id in {n.action_id for n in _services(c)}:
            return step("BOOK_NAME", service=action_id)
        return hint()

    if state == "BOOK_NAME":
        name = " ".join((text or "").split())
        if 2 <= len(name) <= 100 and name.isprintable():
            return step("BOOK_EMAIL", name=name)
        return go(state, [_message(c, lang, c.text("hint_name", lang))])

    if state == "BOOK_EMAIL":
        email = (text or "").strip()
        if len(email) <= 254 and EMAIL_RE.match(email):
            return step("BOOK_DATE", email=email)
        return go(state, [_message(c, lang, c.text("hint_email", lang))])

    if state == "BOOK_DATE":
        if action_id in {f"date_{d.isoformat()}" for d in dates}:
            return step("BOOK_TIME", date=action_id.removeprefix("date_"))
        return hint()

    if state == "BOOK_TIME":
        if action_id in SLOTS:
            return step("BOOK_CONFIRM", slot=action_id)
        return hint()

    if state == "BOOK_CONFIRM":
        if action_id == "book_cancel":
            return main_menu([_message(c, lang, c.text("book_cancelled", lang))])
        if action_id == "book_confirm":
            if date.fromisoformat(booking["date"]) not in dates:  # date window moved on since it was chosen
                return go("BOOK_DATE", [_message(c, lang, c.text("hint_choose", lang))] + _prompt(c, "BOOK_DATE", lang, ctx, dates))
            reference = new_reference()
            r.booking = {
                "reference": reference,
                "service_action_id": booking["service"],
                "name": booking["name"],
                "email": booking["email"],
                "preferred_date": date.fromisoformat(booking["date"]),
                "preferred_slot": booking["slot"],
                "language": lang,
            }
            confirmed = c.text("book_confirmed", lang).format(reference=reference)
            return main_menu([_message(c, lang, confirmed)])
        return hint()

    return hint()
