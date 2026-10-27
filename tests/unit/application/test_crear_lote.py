from __future__ import annotations

from application.batches.commands.crear_lote import CrearLote
from domain.batches.entities import EstadoLote, Lote
from domain.batches.ports import LoteRepository
from tests.unit.application._fakes import _FakeAuditLogger


class _FakeLoteRepository(LoteRepository):
    def __init__(self) -> None:
        self._por_id: dict[str, Lote] = {}

    def save(self, lote: Lote) -> None:
        self._por_id[lote.id] = lote

    def get(self, lote_id: str):
        return self._por_id.get(lote_id)

    def list_by_proyecto(self, proyecto_id: str):
        return [lote for lote in self._por_id.values() if lote.proyecto_id == proyecto_id]

    def list(self):
        return list(self._por_id.values())


def test_crear_lote_queda_abierto() -> None:
    repo = _FakeLoteRepository()
    audit = _FakeAuditLogger()
    lote = CrearLote(repo, audit).execute("PROY-0001", "Lote de enero")

    assert lote.estado == EstadoLote.ABIERTO
    assert lote.nombre == "Lote de enero"
    assert repo.get(lote.id) == lote
    assert [e.accion for e in audit.eventos] == ["crear_lote"]
