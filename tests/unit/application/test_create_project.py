"""CrearProyecto (Documento Maestro, Hito H2 / Modulo 1).

Hallazgo real de la cuarta auditoria general (2026-08-01): este caso de
uso -- el unico del contexto Proyectos -- no tenia ningun test en
tests/unit/, solo el smoke test real
(tests/integration/test_crear_proyecto_extremo_a_extremo.py, que sigue siendo
la cobertura de punta a punta contra bootstrap/SQLite/sistema de
archivos reales). Este archivo agrega la cobertura rapida con fakes en
memoria que el resto de contextos (documentos, lotes, incidencias...) ya
tiene, usando el mismo patron de fakes que
test_agregar_quitar_documento_lote.py."""
from __future__ import annotations

import pytest

from application.projects.commands.create_project import CrearProyecto
from domain.profiles.entities import PerfilProyecto
from domain.profiles.ports import ProfileRepository
from domain.projects.entities import EstadoProyecto, NivelConfidencialidad, Proyecto
from domain.projects.exceptions import DuplicateProjectNameError, ProfileNotFoundError
from domain.projects.ports import ProjectFileStore, ProjectRepository

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
        # de Archivar/Eliminar proyecto): solo entre ACTIVOS, mismo
        # criterio que SqlAlchemyProjectRepository.get_by_name() real --
        # ver su docstring en infrastructure/database/repository.py.
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


class _FakeProfileRepository(ProfileRepository):
    def __init__(self, perfiles: list[PerfilProyecto] | None = None) -> None:
        self._por_id: dict[str, PerfilProyecto] = {p.id: p for p in (perfiles or [])}

    def get(self, perfil_id: str):
        return self._por_id.get(perfil_id)

    def get_version(self, perfil_id: str, version: str):
        perfil = self._por_id.get(perfil_id)
        return perfil if perfil is not None and perfil.version == version else None

    def list_versions(self, perfil_id: str):
        perfil = self._por_id.get(perfil_id)
        return [perfil.version] if perfil is not None else []

    def list(self):
        return list(self._por_id.values())

    def save(self, perfil: PerfilProyecto) -> None:
        self._por_id[perfil.id] = perfil


class _FakeProjectFileStore(ProjectFileStore):
    def __init__(self) -> None:
        self.llamadas: list[str] = []
        self.llamadas_delete: list[str] = []

    def create_structure(self, proyecto: Proyecto) -> str:
        self.llamadas.append(proyecto.id)
        return f"/proyectos/{proyecto.id}_{proyecto.nombre.lower()}"

    def delete_structure(self, proyecto: Proyecto) -> None:
        self.llamadas_delete.append(proyecto.id)


def _perfil(perfil_id: str = "perfil_generico") -> PerfilProyecto:
    return PerfilProyecto(id=perfil_id, version="0.1")


def test_crear_proyecto_exitoso_devuelve_proyecto_con_ruta_carpeta() -> None:
    file_store = _FakeProjectFileStore()
    audit = _FakeAuditLogger()
    caso_de_uso = CrearProyecto(_FakeProjectRepository(), _FakeProfileRepository([_perfil()]), file_store, audit)

    proyecto = caso_de_uso.execute(nombre="Proyecto RH", perfil_id="perfil_generico")

    assert proyecto.nombre == "Proyecto RH"
    assert proyecto.perfil_id == "perfil_generico"
    assert proyecto.ruta_carpeta == f"/proyectos/{proyecto.id}_proyecto rh"
    assert file_store.llamadas == [proyecto.id]


def test_crear_proyecto_deja_un_evento_de_auditoria() -> None:
    audit = _FakeAuditLogger()
    caso_de_uso = CrearProyecto(_FakeProjectRepository(), _FakeProfileRepository([_perfil()]), _FakeProjectFileStore(), audit)

    proyecto = caso_de_uso.execute(nombre="Proyecto RH", perfil_id="perfil_generico")

    assert [e.accion for e in audit.eventos] == ["crear_proyecto"]
    assert audit.eventos[0].proyecto_id == proyecto.id
    assert audit.eventos[0].valor_nuevo == "Proyecto RH"


def test_crear_proyecto_nombre_duplicado_falla() -> None:
    existente = Proyecto(nombre="Proyecto RH", perfil_id="perfil_generico", confidencialidad=NivelConfidencialidad.INTERNO)
    repo = _FakeProjectRepository([existente])
    file_store = _FakeProjectFileStore()
    caso_de_uso = CrearProyecto(repo, _FakeProfileRepository([_perfil()]), file_store, _FakeAuditLogger())

    with pytest.raises(DuplicateProjectNameError):
        caso_de_uso.execute(nombre="Proyecto RH", perfil_id="perfil_generico")

    # No debe haber intentado crear la carpeta fisica para un proyecto
    # que de todas formas se va a rechazar.
    assert file_store.llamadas == []


def test_crear_proyecto_reutiliza_el_nombre_de_un_proyecto_archivado() -> None:
    """Auditoria 2026-09-02 (hallazgo real de la auditoria independiente
    de la ronda de Archivar/Eliminar proyecto, RAG_CONTENT_01): antes de
    este fix, `DuplicateProjectNameError` bloqueaba para siempre volver
    a usar el nombre de un proyecto ya archivado -- contradiciendo el
    proposito mismo de archivar ("ya no procede", ver Manual de Usuario
    6.1) y el propio mensaje de la excepcion, que dice "un proyecto
    ACTIVO con ese nombre". Escenario real: se crea "Cliente ACME" por
    error, se archiva, y luego se quiere crear el "Cliente ACME"
    correcto -- debe poder hacerlo."""
    archivado = Proyecto(
        nombre="Cliente ACME",
        perfil_id="perfil_generico",
        confidencialidad=NivelConfidencialidad.INTERNO,
        estado=EstadoProyecto.ARCHIVADO,
    )
    repo = _FakeProjectRepository([archivado])
    file_store = _FakeProjectFileStore()
    caso_de_uso = CrearProyecto(repo, _FakeProfileRepository([_perfil()]), file_store, _FakeAuditLogger())

    nuevo = caso_de_uso.execute(nombre="Cliente ACME", perfil_id="perfil_generico")

    assert nuevo.nombre == "Cliente ACME"
    assert nuevo.estado == EstadoProyecto.ACTIVO
    assert nuevo.id != archivado.id
    assert file_store.llamadas == [nuevo.id]
    # El proyecto archivado sigue existiendo tal cual -- crear uno nuevo
    # con el mismo nombre no lo toca ni lo reemplaza.
    assert repo.get(archivado.id) is not None


def test_crear_proyecto_nombre_duplicado_con_otro_activo_sigue_fallando() -> None:
    """Complemento de la prueba anterior: el fix relaja la unicidad solo
    frente a proyectos ARCHIVADO, nunca entre dos proyectos ACTIVO."""
    activo = Proyecto(nombre="Cliente ACME", perfil_id="perfil_generico", confidencialidad=NivelConfidencialidad.INTERNO)
    repo = _FakeProjectRepository([activo])
    file_store = _FakeProjectFileStore()
    caso_de_uso = CrearProyecto(repo, _FakeProfileRepository([_perfil()]), file_store, _FakeAuditLogger())

    with pytest.raises(DuplicateProjectNameError):
        caso_de_uso.execute(nombre="Cliente ACME", perfil_id="perfil_generico")

    assert file_store.llamadas == []


def test_crear_proyecto_perfil_inexistente_falla_sin_crear_carpeta() -> None:
    file_store = _FakeProjectFileStore()
    caso_de_uso = CrearProyecto(_FakeProjectRepository(), _FakeProfileRepository(), file_store, _FakeAuditLogger())

    with pytest.raises(ProfileNotFoundError):
        caso_de_uso.execute(nombre="Proyecto sin perfil", perfil_id="perfil_que_no_existe")

    assert file_store.llamadas == []


def test_crear_proyecto_usa_valores_por_defecto_para_campos_opcionales() -> None:
    caso_de_uso = CrearProyecto(
        _FakeProjectRepository(), _FakeProfileRepository([_perfil()]), _FakeProjectFileStore(), _FakeAuditLogger()
    )

    proyecto = caso_de_uso.execute(nombre="Proyecto minimo", perfil_id="perfil_generico")

    assert proyecto.objetivo == ""
    assert proyecto.usuarios_objetivo == []
    assert proyecto.idioma == "es"
    assert proyecto.confidencialidad == NivelConfidencialidad.INTERNO
    assert proyecto.responsables == []
