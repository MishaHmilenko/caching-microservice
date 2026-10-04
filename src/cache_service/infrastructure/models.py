from sqlalchemy import CHAR, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransformedStringRow(Base):
    __tablename__ = "transformed_strings"

    # Keyed by digest rather than the text itself: B-tree entries are size-limited in
    # Postgres and the source string can be long and multibyte.
    source_hash: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)


class PayloadRow(Base):
    __tablename__ = "payloads"

    id: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    output: Mapped[str] = mapped_column(Text)
