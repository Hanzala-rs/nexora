import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MenuNode(Base):
    __tablename__ = "menu_nodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[str] = mapped_column(String(64), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("menu_nodes.id"))
    kind: Mapped[str] = mapped_column(String(16))  # submenu | info | book | handoff
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MenuTranslation(Base):
    __tablename__ = "menu_translations"
    node_id: Mapped[int] = mapped_column(ForeignKey("menu_nodes.id", ondelete="CASCADE"), primary_key=True)
    lang: Mapped[str] = mapped_column(String(2), primary_key=True)
    title: Mapped[str] = mapped_column(String(24))
    body: Mapped[str] = mapped_column(Text, default="")


class UiText(Base):
    __tablename__ = "ui_texts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    lang: Mapped[str] = mapped_column(String(2), primary_key=True)
    text: Mapped[str] = mapped_column(Text)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("channel", "user_ref"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(String(16))  # whatsapp
    user_ref: Mapped[str | None] = mapped_column(String(32))  # wa_id
    language: Mapped[str | None] = mapped_column(String(2))
    state: Mapped[str] = mapped_column(String(16))
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "client_msg_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(3))  # in | out
    payload: Mapped[dict] = mapped_column(JSONB)
    client_msg_id: Mapped[str | None] = mapped_column(String(128))  # WhatsApp message id (dedupe)
    reply_to: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsultationRequest(Base):
    __tablename__ = "consultation_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    reference: Mapped[str] = mapped_column(String(16), unique=True)
    service_action_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_date: Mapped[date] = mapped_column(Date)
    preferred_slot: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(16), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HandoffRequest(Base):
    __tablename__ = "handoff_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
