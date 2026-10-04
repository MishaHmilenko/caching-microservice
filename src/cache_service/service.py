import hashlib
import json
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from cache_service.models import Payload, TransformedString
from cache_service.transformer import Transformer

OUTPUT_SEPARATOR = ", "


def payload_id(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Derive the identifier from the inputs so identical requests share one payload."""
    canonical = json.dumps([list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]


class PayloadService:
    def __init__(self, session: Session, transformer: Transformer) -> None:
        self._session = session
        self._transformer = transformer

    def get_output(self, id_: str) -> str | None:
        payload = self._session.get(Payload, id_)
        return payload.output if payload else None

    def create(self, list_1: Sequence[str], list_2: Sequence[str]) -> tuple[str, bool]:
        """Return the payload id and whether it was newly created."""
        id_ = payload_id(list_1, list_2)
        if self._session.get(Payload, id_):
            return id_, False
        try:
            self._store(id_, list_1, list_2)
        except IntegrityError:
            # A concurrent request stored some of the same rows first. Results are deterministic,
            # so start over and reuse what it wrote instead of failing the request.
            self._session.rollback()
            if self._session.get(Payload, id_):
                return id_, False
            self._store(id_, list_1, list_2)
        return id_, True

    def _store(self, id_: str, list_1: Sequence[str], list_2: Sequence[str]) -> None:
        results = self._transform_with_cache([*list_1, *list_2])
        output = OUTPUT_SEPARATOR.join(
            interleave([results[s] for s in list_1], [results[s] for s in list_2])
        )
        self._session.add(Payload(id=id_, output=output))
        self._session.commit()

    def _transform_with_cache(self, strings: Sequence[str]) -> dict[str, str]:
        """Map every distinct input to its transformed value, calling the transformer at most
        once, and only for strings that have never been seen."""
        distinct = list(dict.fromkeys(strings))
        rows = self._session.exec(
            select(TransformedString).where(col(TransformedString.source).in_(distinct))
        )
        results = {row.source: row.result for row in rows}

        missing = [s for s in distinct if s not in results]
        if missing:
            transformed = self._transformer(missing)
            if len(transformed) != len(missing):
                raise RuntimeError("Transformer returned a different number of results")
            for source, result in zip(missing, transformed, strict=True):
                results[source] = result
                self._session.add(TransformedString(source=source, result=result))
        return results
