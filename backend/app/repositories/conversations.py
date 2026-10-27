"""Conversations and their messages."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..db import Session
from ..db.tables import Conversation, Message


def get(session: Session, conversation_id: str) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def newest_active(session: Session, project_id: str) -> Conversation | None:
    return session.scalar(select(Conversation).where(Conversation.project_id == project_id, Conversation.status == "active")
                          .order_by(Conversation.created_at.desc(), Conversation.id.desc()))


def create(session: Session, **fields) -> Conversation:
    conv = Conversation(**fields)
    session.add(conv)
    session.commit()
    return conv


def append_message(session: Session, conv_id: str, **fields) -> Message | None:
    """Add a message numbered max+1; None if the unique (conversation, seq) key was hit (caller retries)."""
    seq = session.scalar(select(func.coalesce(func.max(Message.seq), 0)).where(Message.conversation_id == conv_id)) + 1
    m = Message(conversation_id=conv_id, seq=seq, **fields)
    session.add(m)
    try:
        session.commit()
        return m
    except IntegrityError:
        session.rollback()
        return None


def last_message(session: Session, conv_id: str) -> Message | None:
    return session.scalar(select(Message).where(Message.conversation_id == conv_id).order_by(Message.seq.desc()))


def messages_after_summary(session: Session, conv: Conversation, upto_seq: int) -> list[Message]:
    return list(session.scalars(select(Message).where(Message.conversation_id == conv.id, Message.seq > conv.summary_upto_seq,
                                                         Message.seq < upto_seq).order_by(Message.seq)))


def all_messages(session: Session, conv_id: str) -> list[Message]:
    return list(session.scalars(select(Message).where(Message.conversation_id == conv_id).order_by(Message.seq)))
