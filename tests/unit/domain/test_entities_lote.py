from __future__ import annotations

import pytest

from domain.batches.entities import EstadoLote, Lote
from domain.batches.exceptions import InvalidBatchStateTransitionError


def _lote(**overrides) -> Lote:
    datos = {"proyecto_id": "PROY-0001", "nombre": "Lote de prueba"}
    datos.update(overrides)
    return Lote(**datos)


def test_lote_nace_abierto() -> None:
    lote = _lote()
    assert lote.estado == EstadoLote.ABIERTO
    assert lote.cerrado_en is None


def test_nombre_vacio_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _lote(nombre="   ")


def test_cerrar_lote_abierto() -> None:
    lote = _lote()
    cerrado = lote.cerrar()
    assert cerrado.estado == EstadoLote.CERRADO
    assert cerrado.cerrado_en is not None


def test_cerrar_un_lote_ya_cerrado_falla() -> None:
    lote = _lote().cerrar()
    with pytest.raises(InvalidBatchStateTransitionError):
        lote.cerrar()
