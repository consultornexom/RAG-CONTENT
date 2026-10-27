"""Prueba dirigida del bug que motivo infrastructure.database.types
(ver su docstring): sin UTCDateTime, un datetime aware pierde su tzinfo
al volver de SQLite."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, select

from infrastructure.database.types import UTCDateTime


@pytest.fixture()
def tabla_de_prueba():
    engine = create_engine("sqlite:///:memory:")
    meta = MetaData()
    tabla = Table(
        "t",
        meta,
        Column("id", String, primary_key=True),
        Column("momento", UTCDateTime),
    )
    meta.create_all(engine)
    return engine, tabla


def test_datetime_aware_conserva_tzinfo_utc_tras_el_ciclo(tabla_de_prueba) -> None:
    engine, tabla = tabla_de_prueba
    ahora = datetime.now(timezone.utc)

    with engine.begin() as conn:
        conn.execute(tabla.insert().values(id="1", momento=ahora))

    with engine.connect() as conn:
        fila = conn.execute(select(tabla)).first()

    assert fila.momento.tzinfo == timezone.utc
    assert fila.momento == ahora


def test_datetime_en_otra_zona_se_normaliza_a_utc(tabla_de_prueba) -> None:
    from datetime import timedelta

    engine, tabla = tabla_de_prueba
    zona_menos_seis = timezone(timedelta(hours=-6))
    momento_local = datetime(2026, 7, 28, 10, 0, 0, tzinfo=zona_menos_seis)

    with engine.begin() as conn:
        conn.execute(tabla.insert().values(id="1", momento=momento_local))

    with engine.connect() as conn:
        fila = conn.execute(select(tabla)).first()

    assert fila.momento == momento_local  # mismo instante
    assert fila.momento.tzinfo == timezone.utc
    assert fila.momento.hour == 16  # 10:00 -06:00 == 16:00 UTC


def test_datetime_naive_es_rechazado(tabla_de_prueba) -> None:
    from sqlalchemy.exc import StatementError

    engine, tabla = tabla_de_prueba
    naive = datetime(2026, 7, 28, 10, 0, 0)

    # SQLAlchemy envuelve el ValueError original de process_bind_param
    # en StatementError al ejecutar el INSERT.
    with pytest.raises(StatementError, match="tzinfo explicito"):
        with engine.begin() as conn:
            conn.execute(tabla.insert().values(id="1", momento=naive))


def test_valor_nulo_se_conserva(tabla_de_prueba) -> None:
    engine, tabla = tabla_de_prueba
    with engine.begin() as conn:
        conn.execute(tabla.insert().values(id="1", momento=None))

    with engine.connect() as conn:
        fila = conn.execute(select(tabla)).first()
    assert fila.momento is None
