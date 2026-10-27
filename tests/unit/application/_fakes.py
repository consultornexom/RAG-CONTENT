"""Fakes en memoria compartidos entre pruebas de `tests/unit/application/`.

Hallazgo real de la cuarta auditoria general (2026-08-01): `_FakeAuditLogger`
y `_FakeDocumentRepository` estaban duplicados, palabra por palabra (o casi
-- ver mas abajo), en 14 y 23 archivos de prueba respectivamente. Si el
puerto correspondiente (`domain.projects.ports.AuditLogger`,
`domain.documents.ports.DocumentRepository`) gana un metodo nuevo, hay
que recordar tocarlo en cada copia dispersa; olvidar una no falla
ruidosamente hasta que ese archivo especifico ejercite el metodo
faltante.

Deliberadamente NO es un `conftest.py`: un modulo plano evita que pytest
lo cargue como plugin implicito para toda la suite (mismo motivo, ver
`pyproject.toml`, por el que este proyecto no tiene ningun
`conftest.py` -- pytest-qt no debe cargarse por accidente). Cada archivo
de prueba que lo use lo importa explicitamente, como cualquier otro
modulo.

Alcance de esta consolidacion (primera pasada, honesto sobre lo que
falta): `_FakeVigenciaRepository` y `_FakeIncidentRepository`, tambien
senalados por la auditoria como duplicados, resultaron tener MAS
variacion real entre archivos de lo que la auditoria estimo -- varias
copias difieren en metodos o comportamiento segun lo que cada prueba
necesita, no son duplicados mecanicos seguros de consolidar sin revisar
cada uno con cuidado. Se dejan como estan; consolidarlos queda como
trabajo futuro, no una omision silenciosa."""
from __future__ import annotations

from domain.audit.entities import EventoAuditoria
from domain.documents.entities import Documento
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger


class _FakeAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []

    def record(self, proyecto_id, accion, valor_anterior, valor_nuevo, motivo):
        self.eventos.append(
            EventoAuditoria(
                proyecto_id=proyecto_id, accion=accion, valor_anterior=valor_anterior, valor_nuevo=valor_nuevo, motivo=motivo
            )
        )

    def list_by_project(self, proyecto_id, limite=None):
        eventos = [e for e in self.eventos if e.proyecto_id == proyecto_id]
        return eventos if limite is None else eventos[:limite]


class _FakeDocumentRepository(DocumentRepository):
    def __init__(self, documentos: list[Documento] | None = None) -> None:
        self._por_id: dict[str, Documento] = {d.id: d for d in (documentos or [])}

    def save(self, documento: Documento) -> None:
        self._por_id[documento.id] = documento

    def get(self, documento_id: str):
        return self._por_id.get(documento_id)

    def get_by_hash(self, hash_sha256: str):
        return next((d for d in self._por_id.values() if d.hash_sha256 == hash_sha256), None)

    def list_by_estado(self, estado):
        return [d for d in self._por_id.values() if d.estado == estado]

    def list(self):
        return list(self._por_id.values())
