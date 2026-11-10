"""Pure state-machine tests (no database)."""
from datetime import date

import pytest

from app.bot.engine import handle, mask_email, offered_dates

SUN_THU = frozenset({6, 0, 1, 2, 3})
TODAY = date(2026, 11, 10)  # Tuesday
DATES = offered_dates(TODAY, SUN_THU, 7)


def run(content, state, language, action_id=None, text=None, context=None):
    return handle(state, language, context or {}, action_id, text, content, DATES, lambda: "NX-TEST")


def ids(message):
    return [o["id"] for o in message.get("options", [])]


def all_text(result):
    return " ".join(m["text"] + " ".join(o["title"] for o in m.get("options", [])) for m in result.replies)


# ---------- content ----------

def test_seed_titles_fit_whatsapp_limits(content):
    for node in content.nodes.values():
        for lang in ("en", "ar"):
            assert 0 < len(node.title[lang]) <= 24, node.action_id
    button_titles = [content.nodes[a].title[l] for a in ("book_start", "menu_main", "handoff") for l in ("en", "ar")]
    button_titles += [content.text(k, l) for k in ("lang_option", "slot_morning", "slot_afternoon", "book_confirm",
                                                    "book_cancel", "list_button") for l in ("en", "ar")]
    assert all(len(t) <= 20 for t in button_titles)
    for lang in ("en", "ar"):  # date rows over a full year
        for start in range(0, 365, 7):
            dates = offered_dates(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + start), SUN_THU, 7)
            r = handle("BOOK_EMAIL", lang, {"booking": {}}, None, "a@b.co", content, dates, lambda: "")
            assert all(len(o["title"]) <= 24 for o in r.replies[0]["options"])
    keys = {k for k, _ in content.texts}
    assert all((k, l) in content.texts for k in keys for l in ("en", "ar"))


# ---------- dates ----------

def test_offered_dates_skip_today_and_non_working_days():
    assert DATES[0] == date(2026, 11, 11)  # Wed, today excluded
    assert len(DATES) == 7
    assert all(d.weekday() in SUN_THU for d in DATES)
    assert date(2026, 11, 13) not in DATES and date(2026, 11, 14) not in DATES  # Fri, Sat


def test_mask_email():
    assert mask_email("sara@example.com") == "s***@example.com"
    assert mask_email("not-an-email") == "***"


# ---------- language selection & menu ----------

def test_language_selection_shows_main_menu_in_both_languages(content):
    en = run(content, "LANG_SELECT", None, "lang_en")
    assert (en.state, en.language) == ("MENU", "en")
    menu = en.replies[0]
    assert menu["type"] == "list" and ids(menu)[-1] == "change_language"
    assert {"menu_services", "book_start", "handoff"} <= set(ids(menu))
    ar = run(content, "LANG_SELECT", None, "lang_ar")
    assert ar.language == "ar" and ar.replies[0]["text"] == content.nodes["menu_main"].body["ar"]
    assert ar.replies[0]["button"] == "عرض الخيارات"


def test_unknown_input_in_lang_select_resends_welcome(content):
    r = run(content, "LANG_SELECT", None, text="hello")
    assert r.state == "LANG_SELECT" and ids(r.replies[0]) == ["lang_en", "lang_ar"]


def test_submenu_and_info_navigation(content):
    r = run(content, "MENU", "en", "menu_services", context={"node_id": "menu_main"})
    assert r.context["node_id"] == "menu_services"
    assert ids(r.replies[0]) == ["svc_strategy", "svc_digital", "svc_operations", "svc_hr", "menu_main"]
    info = run(content, "MENU", "en", "svc_digital", context=r.context)
    assert info.replies[0]["type"] == "buttons" and ids(info.replies[0]) == ["book_start", "menu_main", "handoff"]


def test_invalid_menu_input_hints_and_repeats_prompt(content):
    r = run(content, "MENU", "ar", text="مرحبا", context={"node_id": "menu_faq"})
    assert r.state == "MENU"
    assert r.replies[0]["text"] == content.text("hint_choose", "ar")
    assert "faq_cost" in ids(r.replies[1])


# ---------- global actions ----------

ALL_STATES = {
    "LANG_SELECT": {},
    "MENU": {"node_id": "menu_main"},
    "BOOK_SERVICE": {"booking": {}},
    "BOOK_NAME": {"booking": {"service": "svc_hr"}},
    "BOOK_EMAIL": {"booking": {"service": "svc_hr", "name": "Sara"}},
    "BOOK_DATE": {"booking": {"service": "svc_hr", "name": "Sara", "email": "s@x.com"}},
    "BOOK_TIME": {"booking": {"service": "svc_hr", "name": "Sara", "email": "s@x.com", "date": "2026-11-11"}},
    "BOOK_CONFIRM": {"booking": {"service": "svc_hr", "name": "Sara", "email": "s@x.com", "date": "2026-11-11",
                                 "slot": "slot_morning"}},
    "HUMAN": {},
}


@pytest.mark.parametrize("state", ALL_STATES)
def test_global_actions_work_in_every_state(content, state):
    ctx = ALL_STATES[state]
    menu = run(content, state, "en", "menu_main", context=ctx)
    assert menu.state == "MENU" and "booking" not in menu.context and not menu.handoff
    keyword = run(content, state, "en", text="القائمة", context=ctx)
    assert keyword.state == "MENU" and keyword.stored_input is None
    lang = run(content, state, "en", "change_language", context=ctx)
    assert lang.state == "LANG_SELECT" and "booking" not in lang.context
    handoff = run(content, state, "en", "handoff", context=ctx)
    assert handoff.state == "HUMAN" and handoff.handoff and "booking" not in handoff.context
    assert handoff.replies[0]["text"] == content.text("handoff_ack", "en")


@pytest.mark.parametrize("action", ["menu_main", "change_language", "handoff"])
def test_global_actions_without_language_resend_language_selection(content, action):
    r = run(content, "LANG_SELECT", None, action)
    assert r.state == "LANG_SELECT" and not r.handoff and ids(r.replies[0]) == ["lang_en", "lang_ar"]


def test_human_state_is_silent_for_other_input(content):
    for kwargs in ({"text": "hello"}, {"action_id": "svc_hr"}, {}):
        r = run(content, "HUMAN", "en", **kwargs)
        assert r.state == "HUMAN" and r.replies == []


# ---------- booking ----------

def test_full_booking_flow_en(content):
    r = run(content, "MENU", "en", "book_start", context={"node_id": "menu_main"})
    assert r.state == "BOOK_SERVICE" and ids(r.replies[0])[0] == "svc_strategy"
    r = run(content, r.state, "en", "svc_strategy", context=r.context)
    assert r.state == "BOOK_NAME"
    r = run(content, r.state, "en", text="  Sara   Ahmed ", context=r.context)
    assert r.state == "BOOK_EMAIL" and r.context["booking"]["name"] == "Sara Ahmed"
    r = run(content, r.state, "en", text="sara@example.com", context=r.context)
    assert r.state == "BOOK_DATE" and r.stored_input == {"text": "s***@example.com", "redacted": True}
    assert ids(r.replies[0])[0] == "date_2026-11-11" and r.replies[0]["options"][0]["title"] == "Wed 11 Nov"
    r = run(content, r.state, "en", "date_2026-11-12", context=r.context)
    assert r.state == "BOOK_TIME" and ids(r.replies[0]) == ["slot_morning", "slot_afternoon"]
    r = run(content, r.state, "en", "slot_afternoon", context=r.context)
    assert r.state == "BOOK_CONFIRM" and ids(r.replies[0]) == ["book_confirm", "book_cancel"]
    assert "s***@example.com" in r.replies[0]["text"] and "sara@example.com" not in all_text(r)
    r = run(content, r.state, "en", "book_confirm", context=r.context)
    assert r.state == "MENU" and "booking" not in r.context
    assert r.booking == {"reference": "NX-TEST", "service_action_id": "svc_strategy", "name": "Sara Ahmed",
                         "email": "sara@example.com", "preferred_date": date(2026, 11, 12),
                         "preferred_slot": "slot_afternoon", "language": "en"}
    assert "NX-TEST" in r.replies[0]["text"] and "sara@example.com" not in all_text(r)


def test_arabic_date_titles(content):
    r = run(content, "BOOK_EMAIL", "ar", text="a@b.co", context=ALL_STATES["BOOK_EMAIL"])
    assert r.replies[0]["options"][0]["title"] == "الأربعاء 11 نوفمبر"


def test_invalid_name_and_email(content):
    r = run(content, "BOOK_NAME", "en", text="x", context=ALL_STATES["BOOK_NAME"])
    assert r.state == "BOOK_NAME" and r.replies[0]["text"] == content.text("hint_name", "en")
    r = run(content, "BOOK_EMAIL", "en", text="sara@", context=ALL_STATES["BOOK_EMAIL"])
    assert r.state == "BOOK_EMAIL" and r.replies[0]["text"] == content.text("hint_email", "en")
    assert r.stored_input == {"text": "***", "redacted": True}


def test_date_not_offered_is_rejected(content):
    for bad in ("date_2026-11-13", "date_2026-11-10", "date_2027-01-01"):  # Friday, today, outside window
        r = run(content, "BOOK_DATE", "en", bad, context=ALL_STATES["BOOK_DATE"])
        assert r.state == "BOOK_DATE" and r.replies[0]["text"] == content.text("hint_choose", "en")
        assert ids(r.replies[1])[0] == "date_2026-11-11"


def test_confirm_with_expired_date_asks_for_date_again(content):
    ctx = {"booking": dict(ALL_STATES["BOOK_CONFIRM"]["booking"], date="2026-11-09")}
    r = run(content, "BOOK_CONFIRM", "en", "book_confirm", context=ctx)
    assert r.state == "BOOK_DATE" and r.booking is None


def test_cancel_booking(content):
    r = run(content, "BOOK_CONFIRM", "en", "book_cancel", context=ALL_STATES["BOOK_CONFIRM"])
    assert r.state == "MENU" and r.booking is None and "booking" not in r.context
    assert r.replies[0]["text"] == content.text("book_cancelled", "en")


def test_stale_options_get_hint(content):
    r = run(content, "BOOK_TIME", "en", "svc_hr", context=ALL_STATES["BOOK_TIME"])
    assert r.state == "BOOK_TIME" and r.replies[0]["text"] == content.text("hint_choose", "en")
