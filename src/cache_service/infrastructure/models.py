"""SQLAlchemy table definitions."""

from sqlalchemy import CHAR, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by all tables."""


class TransformedStringRow(Base):
    """Cached transformer outcome for one input string."""

    __tablename__ = "transformed_strings"

    # Keyed by digest rather than the text itself: B-tree entries are size-limited in
    # Postgres and the source string can be long and multibyte.
    source_hash: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)


class PayloadRow(Base):
    """A generated payload, keyed by the digest of its inputs."""

    __tablename__ = "payloads"

    id: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    output: Mapped[str] = mapped_column(Text)
