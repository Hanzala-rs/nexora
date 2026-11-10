"""Remove simulator channel (WhatsApp only).

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM conversations WHERE channel = 'simulator'")  # cascades to messages/requests
    op.drop_constraint("ck_conversations_channel", "conversations", type_="check")
    op.create_check_constraint("ck_conversations_channel", "conversations", "channel = 'whatsapp'")
    op.drop_column("conversations", "create_request_id")
    op.drop_column("messages", "input_hash")


def downgrade() -> None:
    op.add_column("messages", sa.Column("input_hash", sa.String(64)))
    op.add_column("conversations", sa.Column("create_request_id", sa.String(36), unique=True))
    op.drop_constraint("ck_conversations_channel", "conversations", type_="check")
    op.create_check_constraint("ck_conversations_channel", "conversations", "channel IN ('whatsapp', 'simulator')")
