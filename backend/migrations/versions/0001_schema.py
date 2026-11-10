"""Initial schema.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "menu_nodes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("action_id", sa.String(64), nullable=False, unique=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("menu_nodes.id")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("kind IN ('submenu', 'info', 'book', 'handoff')", name="ck_menu_nodes_kind"),
        sa.CheckConstraint("action_id ~ '^[a-z0-9_-]{1,64}$'", name="ck_menu_nodes_action_id"),
    )
    op.create_table(
        "menu_translations",
        sa.Column("node_id", sa.Integer, sa.ForeignKey("menu_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("lang", sa.String(2), primary_key=True),
        sa.Column("title", sa.String(24), nullable=False),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.CheckConstraint("lang IN ('en', 'ar')", name="ck_menu_translations_lang"),
    )
    op.create_table(
        "ui_texts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("lang", sa.String(2), primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.CheckConstraint("lang IN ('en', 'ar')", name="ck_ui_texts_lang"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("user_ref", sa.String(32)),
        sa.Column("create_request_id", sa.String(36), unique=True),
        sa.Column("language", sa.String(2)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("context", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("channel", "user_ref"),
        sa.CheckConstraint("channel IN ('whatsapp', 'simulator')", name="ck_conversations_channel"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("direction", sa.String(3), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("client_msg_id", sa.String(128)),
        sa.Column("input_hash", sa.String(64)),
        sa.Column("reply_to", sa.BigInteger, sa.ForeignKey("messages.id"), index=True),
        _created_at(),
        sa.UniqueConstraint("conversation_id", "client_msg_id"),
        sa.CheckConstraint("direction IN ('in', 'out')", name="ck_messages_direction"),
    )
    op.create_table(
        "consultation_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reference", sa.String(16), nullable=False, unique=True),
        sa.Column("service_action_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("preferred_date", sa.Date, nullable=False),
        sa.Column("preferred_slot", sa.String(32), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        _created_at(),
    )
    op.create_table(
        "handoff_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        _created_at(),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_handoff_requests_status"),
    )


def downgrade() -> None:
    for table in ("handoff_requests", "consultation_requests", "messages", "conversations",
                  "ui_texts", "menu_translations", "menu_nodes"):
        op.drop_table(table)
