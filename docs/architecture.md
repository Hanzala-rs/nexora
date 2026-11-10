# Nexora WhatsApp Menu Bot — V1 Architecture

## Scope

V1 is a **deterministic, menu-driven** WhatsApp bot for Nexora Consulting, in English and Arabic.

In scope:
- Language selection (EN / AR), switchable at any time
- Menu navigation (services, about, contact, FAQs), with content stored in the database
- Consultation booking (guided step-by-step form)
- Human handoff (bot pauses, request is logged for staff)

Out of scope: RAG, LLMs, AI agents, NLP intent detection, web frontend, queues/workers, caches, microservices.

## Components

```
WhatsApp user ──► Meta Cloud API ──► POST /webhook ──► Bot engine ──► PostgreSQL
      ▲                                                    │
      └────────────── Cloud API send (background) ◄────────┘
```

One FastAPI app, one PostgreSQL database.

| Component | Responsibility |
|---|---|
| `routes/webhook.py` | Verify Meta webhook (GET), validate `X-Hub-Signature-256` (POST), hand messages to the conversation layer, queue replies |
| `bot/engine.py` | State machine. Pure business logic: `(state, input, content, dates) -> (new state, replies)`. No HTTP or DB code. |
| `bot/conversation.py` | Per-message transaction: dedupe, row lock, idle reset, run engine, persist messages/bookings/handoffs |
| `bot/content.py` | Load menu nodes and translations from DB |
| `whatsapp.py` | Signature check, inbound parsing, Cloud API client (text / buttons / list) |
| `models.py`, `db.py`, `config.py`, `errors.py` | Models, DB session, settings, JSON error responses |
| `migrations/` | Alembic migrations + seed data for menu content |

Endpoints: `GET /webhook` (Meta verification), `POST /webhook` (inbound messages), `GET /api/health`.

## Layout

```
backend/
  app/
    main.py  config.py  db.py  errors.py  models.py  whatsapp.py
    routes/  webhook.py
    bot/     engine.py  conversation.py  content.py
  migrations/
  tests/
docs/
```

Dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg`, `alembic`, `httpx`, `pydantic-settings`, `tzdata`, `pytest`.

## Routing rule

The engine routes **only on stable action IDs** (pattern `^[a-z0-9_-]{1,64}$`, e.g. `menu_services`, `book_confirm`, `date_2026-11-12`), never on displayed titles. Button/list replies carry the action ID. Free text is used only where a step expects text input (name, email) and for global keywords.

## Bot message object

Engine replies are channel-neutral; `whatsapp.py` converts them to Cloud API payloads.

| Field | Notes |
|---|---|
| `type` | `text` \| `buttons` (1–3 options) \| `list` (4–10 options) |
| `text` | Message body |
| `options` | `[{ "id": action_id, "title": str }]` |
| `button` | `list` only: label of the button that opens the list |

## Conversation states

```
LANG_SELECT ─► MENU ◄──────────────────────────────────────┐
                │                                          │
                ├─► BOOK_SERVICE ─► BOOK_NAME ─► BOOK_EMAIL │
                │     ─► BOOK_DATE ─► BOOK_TIME ─► BOOK_CONFIRM
                │
                └─► HUMAN (bot silent except for global actions)
```

- A new WhatsApp user starts in `LANG_SELECT`; their first message gets the language selection.
- `MENU` covers all menu-tree navigation; the current node is kept in `context.node_id`. Any active menu node may be tapped while in `MENU`.
- Booking answers are kept in `context` until confirmed, then written to `consultation_requests`. Booking fields are removed from `context` when the booking is confirmed, cancelled, abandoned via a global action, or reset by idle timeout.
- Unknown input → short "please choose an option" hint + current step's prompt. In `HUMAN`, non-global input is stored but gets no reply.
- Conversations idle > 24h restart at main menu (or `LANG_SELECT` if no language yet).

### Global actions

Checked **before** any state-specific handling, in **every** state (including text-input steps and `HUMAN`). Every global action clears unfinished booking data.

| Input | Language set | No language yet |
|---|---|---|
| `menu_main`, text `menu` / `القائمة` / `0` | → `MENU`, show main menu | Re-send language selection |
| `change_language` | → `LANG_SELECT` | Re-send language selection |
| `handoff` | Create handoff request (if none open), → `HUMAN`, send acknowledgement | Re-send language selection |

Leaving `HUMAN` does not close the open handoff request; staff close it.

## Booking

| State | Bot asks | User sends |
|---|---|---|
| `BOOK_SERVICE` | Choose service (list) | `svc_*` |
| `BOOK_NAME` | Full name | text, 2–100 chars |
| `BOOK_EMAIL` | Email | text, valid email |
| `BOOK_DATE` | Preferred date (list) | `date_YYYY-MM-DD` |
| `BOOK_TIME` | Time slot (buttons) | `slot_morning` \| `slot_afternoon` |
| `BOOK_CONFIRM` | Summary with masked email | `book_confirm` \| `book_cancel` |

Confirmation stores the request once and replies with a reference (`NX-` + 8 hex chars).

Date settings (non-secret environment config):

| Variable | Example | Meaning |
|---|---|---|
| `BUSINESS_TIMEZONE` | `Asia/Riyadh` | IANA zone for "today" and booking dates |
| `BUSINESS_WORKING_DAYS` | `sun,mon,tue,wed,thu` | Days offered for booking |
| `BOOKING_DAYS_AHEAD` | `7` | Number of working days offered (1–10) |

- Offered dates = next `BOOKING_DAYS_AHEAD` working days **after** today (today excluded), recomputed on every message. A date not currently offered gets a hint; a chosen date that has expired by confirmation sends the user back to `BOOK_DATE`.
- No calendar integration or holiday calendar in V1.

## Data model

| Table | Key columns |
|---|---|
| `menu_nodes` | `id`, `action_id` (unique), `parent_id`, `kind` (`submenu` \| `info` \| `book` \| `handoff`), `sort_order`, `is_active` |
| `menu_translations` | `node_id`, `lang` (`en` \| `ar`), `title` (≤ 24 chars), `body` |
| `ui_texts` | `key`, `lang`, `text` — fixed bot prompts, hints, weekday/month names |
| `conversations` | `id`, `channel` (`whatsapp`), `user_ref` (wa_id), `language`, `state`, `context` (JSONB), `updated_at`; unique (`channel`, `user_ref`) |
| `messages` | `id`, `conversation_id`, `direction` (`in` \| `out`), `payload` (JSONB, redacted), `client_msg_id` (WhatsApp message id), `reply_to`; unique (`conversation_id`, `client_msg_id`) |
| `consultation_requests` | `id`, `conversation_id`, `reference`, `service_action_id`, `name`, `email`, `phone`, `preferred_date`, `preferred_slot`, `language`, `status` |
| `handoff_requests` | `id`, `conversation_id`, `status` (`open` \| `closed`) |

All user-visible text lives in `menu_translations` and `ui_texts`, in EN and AR. No translated strings in code.

## Idempotency

Meta retries webhook deliveries. Each inbound message is processed in one transaction:
1. Upsert and lock the user's conversation row (`SELECT … FOR UPDATE`).
2. If (`conversation_id`, WhatsApp message id) already exists → stop; nothing is stored or sent.
3. Otherwise run the engine, store inbound + outbound messages and any booking/handoff row, commit, then send replies in a background task.

The row lock serializes concurrent deliveries per user, so a redelivered `book_confirm` cannot create a second booking.

## WhatsApp constraints

- Reply buttons: max 3, title ≤ 20 chars. List messages: max 10 rows, row title ≤ 24 chars. Seed content is tested against these limits.
- Webhook returns `200` after processing; replies are sent after the response. A send failure is logged (without the phone number) and the remaining replies for that message are skipped.

## Security & privacy

- Secrets from environment only: `DATABASE_URL`, `WA_ACCESS_TOKEN`, `WA_PHONE_NUMBER_ID`, `WA_APP_SECRET`, `WA_VERIFY_TOKEN`.
- Every webhook POST validated with HMAC-SHA256 (`X-Hub-Signature-256`, `WA_APP_SECRET`); invalid or missing → `401`. Empty `WA_APP_SECRET` / `WA_VERIFY_TOKEN` reject everything.
- Inbound input validated: wa_id digits only, action IDs must match the pattern, text trimmed to 500 chars.
- **Email redaction:** the raw email is stored only in `conversations.context` (until the booking ends) and `consultation_requests.email`. Message history stores a masked value (`s***@example.com`), and bot replies show only the masked form. Phone numbers and emails are not logged.

## Testing

- `tests/test_engine.py`: pure state machine — transitions, both languages, invalid input, global actions in every state, date window, seed content limits.
- `tests/test_webhook.py`: against PostgreSQL — signature/verification, full booking over WhatsApp, redaction, duplicate and concurrent deliveries, handoff, idle reset. Cloud API sends are mocked.
- Tests use `TEST_DATABASE_URL` (wiped on each run), never `DATABASE_URL`.

## Open questions

1. How do staff receive handoff/booking notifications and close handoffs? V1: rows stored in the DB only.
2. Final menu content (services, FAQs, contact details) in both languages.
3. Actual business timezone and working days.
4. Slot hours for `morning` / `afternoon`; whether public holidays must be excluded.
5. Arabic date display: Western (`12`) or Arabic-Indic (`١٢`) digits.
6. Masked email in the summary means users cannot spot typos in the local part.
