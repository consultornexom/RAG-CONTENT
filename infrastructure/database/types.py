"""Tipo de columna SQLAlchemy compartido por ambas bases (aplicacion.db
y proyecto.db) que garantiza que toda fecha/hora guardada y leida sea
siempre UTC con tzinfo explicito -- todo el nucleo construye sus
timestamps con `datetime.now(timezone.utc)` (ver domain/*/entities.py).

SQLite no tiene un tipo timezone-aware real: `sqlalchemy.DateTime
(timezone=True)` alli guarda la fecha pero *pierde* el tzinfo al leerla
de vuelta -- comportamiento documentado de SQLAlchemy+SQLite, no un
bug de esta herramienta. Sin este `TypeDecorator`, cada entidad
reconstruida desde la base perderia su tzinfo en silencio, rompiendo
cualquier comparacion posterior con un datetime aware nuevo (por
ejemplo, `Documento.avanzar_a()` calculando `_utcnow()`) con un
`TypeError: can't compare offset-naive and offset-aware datetimes`.
Descubierto por
tests/unit/application/test_sqlalchemy_document_repository.py
(round-trip completo contra SQLite real, no un doble en memoria).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "UTCDateTime requiere un datetime con tzinfo explicito "
                "(usar datetime.now(timezone.utc)), recibido uno naive."
            )
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)
