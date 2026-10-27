"""ArchivarProyecto y EliminarProyecto (Auditoria 2026-09-02, hallazgo
real del consultor RAG_CONTENT_01: "tratamiento a proyecto que no
proceden, como eliminarlos" -- ver evidencias pruebas). Mismo patron de
fakes en memoria que test_create_project.py; reutiliza `_FakeAuditLogger`
de `_fakes.py` (consolidacion de la cuarta auditoria general)."""
from __future__ import annotations

import pytest

from application.projects.commands.archive_project import ArchivarProyecto
from application.projects.commands.delete_project import EliminarProyecto
from domain.projects.entities import EstadoProyecto, NivelConfidencialidad, Proyecto
from domain.projects.exceptions import (
    ProjectAlreadyArchivedError,
    ProjectInUseError,
    ProjectNotFoundError,
)
from domain.projects.ports import ProjectContentChecker, ProjectFileStore, ProjectRepository

from tests.unit.application._fakes import _FakeAuditLogger


class _FakeProjectRepository(ProjectRepository):
    def __init__(self, proyectos: list[Proyecto] | None = None) -> None:
        self._por_id: dict[str, Proyecto] = {p.id: p for p in (proyectos or [])}

    def save(self, proyecto: Proyecto) -> None:
        self._por_id[proyecto.id] = proyecto

    def get(self, proyecto_id: str):
        return self._por_id.get(proyecto_id)

    def get_by_name(self, nombre: str):
        # Auditoria 2026-09-02 (hallazgo real de la auditoria independiente
        # de esta misma ronda): solo entre ACTIVOS, mismo criterio que
        # SqlAlchemyProjectRepository.get_by_name() real.
        return next(
            (p for p in self._por_id.values() if p.nombre == nombre and p.estado == EstadoProyecto.ACTIVO), None
        )

    def list(self, incluir_archivados: bool = True):
        proyectos = list(self._por_id.values())
        if not incluir_archivados:
            proyectos = [p for p in proyectos if p.estado != EstadoProyecto.ARCHIVADO]
        return proyectos

    def delete(self, proyecto_id: str) -> None:
        self._por_id.pop(proyecto_id, None)


class _FakeProjectFileStore(ProjectFileStore):
    def __init__(self) -> None:
        self.llamadas_delete: list[str] = []

    def create_structure(self, proyecto: Proyecto) -> str:
        return f"/proyectos/{proyecto.id}_{proyecto.nombre.lower()}"

    def delete_structure(self, proyecto: Proyecto) -> None:
        self.llamadas_delete.append(proyecto.id)


class _FakeProjectContentChecker(ProjectContentChecker):
    def __init__(self, cantidad_por_proyecto: dict[str, int] | None = None) -> None:
        self._cantidad_por_proyecto = cantidad_por_proyecto or {}

    def tiene_documentos(self, proyecto: Proyecto) -> bool:
        return self._cantidad_por_proyecto.get(proyecto.id, 0) > 0

    def contar_documentos(self, proyecto: Proyecto) -> int:
        return self._cantidad_por_proyecto.get(proyecto.id, 0)


def _proyecto(**kwargs: object) -> Proyecto:
    base: dict[str, object] = dict(
        nombre="Proyecto de prueba", perfil_id="perfil_generico", confidencialidad=NivelConfidencialidad.INTERNO
    )
    base.update(kwargs)
    return Proyecto(**base)  # type: ignore[arg-type]


# ---------- ArchivarProyecto ----------


def test_archivar_proyecto_cambia_estado_y_lo_persiste() -> None:
    proyecto = _proyecto()
    repo = _FakeProjectRepository([proyecto])
    audit = _FakeAuditLogger()
    caso_de_uso = ArchivarProyecto(repo, audit)

    archivado = caso_de_uso.execute(proyecto.id)

    assert archivado.estado == EstadoProyecto.ARCHIVADO
    assert repo.get(proyecto.id).estado == EstadoProyecto.ARCHIVADO


def test_archivar_proyecto_deja_un_evento_de_auditoria() -> None:
    proyecto = _proyecto()
    repo = _FakeProjectRepository([proyecto])
    audit = _FakeAuditLogger()
    caso_de_uso = ArchivarProyecto(repo, audit)

    caso_de_uso.execute(proyecto.id)

    assert [e.accion for e in audit.eventos] == ["archivar_proyecto"]
    assert audit.eventos[0].valor_anterior == "activo"
    assert audit.eventos[0].valor_nuevo == "archivado"


def test_archivar_proyecto_inexistente_falla() -> None:
    caso_de_uso = ArchivarProyecto(_FakeProjectRepository(), _FakeAuditLogger())

    with pytest.raises(ProjectNotFoundError):
        caso_de_uso.execute("PROY-9999")


def test_archivar_proyecto_ya_archivado_falla() -> None:
    proyecto = _proyecto(estado=EstadoProyecto.ARCHIVADO)
    repo = _FakeProjectRepository([proyecto])
    caso_de_uso = ArchivarProyecto(repo, _FakeAuditLogger())

    with pytest.raises(ProjectAlreadyArchivedError):
        caso_de_uso.execute(proyecto.id)


def test_listar_proyectos_sin_incluir_archivados_los_excluye() -> None:
    activo = _proyecto(nombre="Activo")
    archivado = _proyecto(nombre="Archivado", estado=EstadoProyecto.ARCHIVADO)
    repo = _FakeProjectRepository([activo, archivado])

    assert {p.id for p in repo.list(incluir_archivados=False)} == {activo.id}
    assert {p.id for p in repo.list(incluir_archivados=True)} == {activo.id, archivado.id}


# ---------- EliminarProyecto ----------


def test_eliminar_proyecto_sin_documentos_borra_carpeta_e_indice() -> None:
    proyecto = _proyecto(ruta_carpeta="/proyectos/PROY-0001_prueba")
    repo = _FakeProjectRepository([proyecto])
    file_store = _FakeProjectFileStore()
    checker = _FakeProjectContentChecker()
    caso_de_uso = EliminarProyecto(repo, file_store, checker, _FakeAuditLogger())

    caso_de_uso.execute(proyecto.id)

    assert file_store.llamadas_delete == [proyecto.id]
    assert repo.get(proyecto.id) is None


def test_eliminar_proyecto_deja_un_evento_de_auditoria() -> None:
    """Auditoria 2026-09-02 (hallazgo real de la auditoria independiente
    de esta misma ronda, severidad medio-alta): la primera version de
    EliminarProyecto no registraba nada en `eventos_auditoria` -- la
    unica operacion mutadora de todo el sistema sin ningun rastro. Ver
    el docstring del modulo `delete_project.py` para el detalle
    completo del hallazgo."""
    proyecto = _proyecto(ruta_carpeta="/proyectos/PROY-0001_prueba")
    repo = _FakeProjectRepository([proyecto])
    file_store = _FakeProjectFileStore()
    checker = _FakeProjectContentChecker()
    audit = _FakeAuditLogger()
    caso_de_uso = EliminarProyecto(repo, file_store, checker, audit)

    caso_de_uso.execute(proyecto.id)

    assert [e.accion for e in audit.eventos] == ["eliminar_proyecto"]
    assert audit.eventos[0].proyecto_id == proyecto.id
    assert audit.eventos[0].valor_anterior == "activo"
    assert audit.eventos[0].valor_nuevo is None


def test_eliminar_proyecto_con_documentos_falla_sin_borrar_nada() -> None:
    proyecto = _proyecto(ruta_carpeta="/proyectos/PROY-0001_prueba")
    repo = _FakeProjectRepository([proyecto])
    file_store = _FakeProjectFileStore()
    checker = _FakeProjectContentChecker({proyecto.id: 3})
    audit = _FakeAuditLogger()
    caso_de_uso = EliminarProyecto(repo, file_store, checker, audit)

    with pytest.raises(ProjectInUseError) as exc_info:
        caso_de_uso.execute(proyecto.id)

    assert exc_info.value.cantidad_documentos == 3
    # Ni la carpeta ni el registro del indice se tocan si se rechaza --
    # y tampoco debe quedar ningun evento de auditoria de un borrado que
    # nunca ocurrio.
    assert file_store.llamadas_delete == []
    assert repo.get(proyecto.id) is not None
    assert audit.eventos == []


def test_eliminar_proyecto_inexistente_falla() -> None:
    caso_de_uso = EliminarProyecto(
        _FakeProjectRepository(), _FakeProjectFileStore(), _FakeProjectContentChecker(), _FakeAuditLogger()
    )

    with pytest.raises(ProjectNotFoundError):
        caso_de_uso.execute("PROY-9999")


def test_eliminar_proyecto_archivado_sin_documentos_tambien_se_permite() -> None:
    # Archivar y eliminar son operaciones independientes -- un proyecto
    # archivado y vacio sigue siendo elegible para el borrado real,
    # mismo criterio que un proyecto activo y vacio.
    proyecto = _proyecto(ruta_carpeta="/proyectos/PROY-0001_prueba", estado=EstadoProyecto.ARCHIVADO)
    repo = _FakeProjectRepository([proyecto])
    file_store = _FakeProjectFileStore()
    caso_de_uso = EliminarProyecto(repo, file_store, _FakeProjectContentChecker(), _FakeAuditLogger())

    caso_de_uso.execute(proyecto.id)

    assert repo.get(proyecto.id) is None
