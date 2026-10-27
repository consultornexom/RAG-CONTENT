"""Prueba de humo de la Fase 1 (ADR-001, seccion 15: "primer perfil de
prueba" + "pruebas de humo"). Usa una raiz temporal, nunca la ruta real
de datos (Documento Maestro, seccion 4.1) -- una prueba automatica no
debe escribir sobre el proyecto real del usuario.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.bootstrap import bootstrap
from domain.projects.entities import EstadoProyecto, NivelConfidencialidad
from domain.projects.exceptions import DuplicateProjectNameError, ProfileNotFoundError, ProjectInUseError
from infrastructure.filesystem.project_structure import SUBCARPETAS

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_smoke_test")


@pytest.fixture()
def raiz_temporal():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    perfiles_dir = RAIZ_PRUEBA / "perfiles" / "perfil_generico"
    perfiles_dir.mkdir(parents=True)
    shutil.copy(
        Path(__file__).resolve().parents[2] / "perfiles" / "perfil_generico" / "0.1.yaml",
        perfiles_dir / "0.1.yaml",
    )
    yield RAIZ_PRUEBA
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_crear_proyecto_completo(raiz_temporal: Path) -> None:
    ctx = bootstrap(raiz=str(raiz_temporal))

    proyecto = ctx.projects.crear_proyecto(
        nombre="Agente de prueba RH",
        perfil_id="perfil_generico",
        objetivo="Validar el nucleo de administracion de proyectos.",
        confidencialidad=NivelConfidencialidad.INTERNO,
    )

    # 1. El proyecto se puede recuperar tal cual se guardo.
    recuperado = ctx.projects.obtener_proyecto(proyecto.id)
    assert recuperado is not None
    assert recuperado.nombre == "Agente de prueba RH"
    assert recuperado.perfil_id == "perfil_generico"

    # 2. La carpeta fisica existe con las subcarpetas exactas (14 desde
    # que se agrego 14_entrega_rag_studio, 2026-07-31).
    carpeta = Path(proyecto.ruta_carpeta)
    assert carpeta.is_dir()
    for sub in SUBCARPETAS:
        assert (carpeta / sub).is_dir(), f"Falta la subcarpeta {sub}"
    assert (carpeta / "proyecto.yaml").is_file()

    # 3. Aparece en el listado.
    listados = ctx.projects.listar_proyectos()
    assert any(p.id == proyecto.id for p in listados)

    # 4. Quedo un evento de auditoria (Documento Maestro, seccion 4.1).
    from infrastructure.database.models import EventoAuditoriaModel

    eventos = ctx.session.query(EventoAuditoriaModel).filter_by(proyecto_id=proyecto.id).all()
    assert len(eventos) == 1
    assert eventos[0].accion == "crear_proyecto"


def test_no_permite_dos_proyectos_con_el_mismo_nombre(raiz_temporal: Path) -> None:
    ctx = bootstrap(raiz=str(raiz_temporal))
    ctx.projects.crear_proyecto(nombre="Duplicado", perfil_id="perfil_generico")

    with pytest.raises(DuplicateProjectNameError):
        ctx.projects.crear_proyecto(nombre="Duplicado", perfil_id="perfil_generico")


def test_no_permite_crear_proyecto_con_perfil_inexistente(raiz_temporal: Path) -> None:
    ctx = bootstrap(raiz=str(raiz_temporal))

    with pytest.raises(ProfileNotFoundError):
        ctx.projects.crear_proyecto(nombre="Sin perfil", perfil_id="perfil_que_no_existe")


def test_no_deja_carpeta_huerfana_si_falla_por_perfil_inexistente(raiz_temporal: Path) -> None:
    ctx = bootstrap(raiz=str(raiz_temporal))
    proyectos_dir = raiz_temporal / "proyectos"
    antes = set(proyectos_dir.iterdir()) if proyectos_dir.exists() else set()

    with pytest.raises(ProfileNotFoundError):
        ctx.projects.crear_proyecto(nombre="Intento fallido", perfil_id="perfil_que_no_existe")

    despues = set(proyectos_dir.iterdir()) if proyectos_dir.exists() else set()
    assert despues == antes, "Un intento fallido no debe dejar ninguna carpeta creada a medias."


def test_carpeta_real_con_nombre_acentuado_conserva_las_letras(raiz_temporal: Path) -> None:
    # Verificacion real contra el sistema de archivos (no solo la
    # entidad en memoria, ver test_entities_proyecto.py): un nombre con
    # acentos, comunes en espanol, debe producir una carpeta fisica
    # legible, sin perder letras.
    ctx = bootstrap(raiz=str(raiz_temporal))

    proyecto = ctx.projects.crear_proyecto(nombre="Área Legal - Configuración Ñoño", perfil_id="perfil_generico")

    carpeta = Path(proyecto.ruta_carpeta)
    assert carpeta.is_dir()
    assert carpeta.name == f"{proyecto.id}_area_legal_configuracion_nono"
    assert carpeta.parent == raiz_temporal / "proyectos"


# ---------- Archivar / eliminar (Auditoria 2026-09-02, RAG_CONTENT_01) ----------


def test_archivar_proyecto_lo_saca_del_listado_de_activos(raiz_temporal: Path) -> None:
    ctx = bootstrap(raiz=str(raiz_temporal))
    proyecto = ctx.projects.crear_proyecto(nombre="Para archivar", perfil_id="perfil_generico")

    archivado = ctx.projects.archivar_proyecto(proyecto.id)

    assert archivado.estado == EstadoProyecto.ARCHIVADO
    activos = ctx.projects.listar_proyectos(incluir_archivados=False)
    assert proyecto.id not in {p.id for p in activos}
    # Sigue existiendo si se piden todos, incluidos los archivados.
    todos = ctx.projects.listar_proyectos(incluir_archivados=True)
    assert proyecto.id in {p.id for p in todos}
    # Y su carpeta fisica sigue intacta -- archivar nunca borra nada.
    assert Path(proyecto.ruta_carpeta).is_dir()


def test_eliminar_proyecto_vacio_borra_la_carpeta_y_el_indice(raiz_temporal: Path) -> None:
    ctx = bootstrap(raiz=str(raiz_temporal))
    proyecto = ctx.projects.crear_proyecto(nombre="Para eliminar", perfil_id="perfil_generico")
    carpeta = Path(proyecto.ruta_carpeta)
    assert carpeta.is_dir()

    ctx.projects.eliminar_proyecto(proyecto.id)

    assert not carpeta.exists()
    assert ctx.projects.obtener_proyecto(proyecto.id) is None


def test_eliminar_proyecto_con_documentos_registrados_falla_y_no_borra_nada(raiz_temporal: Path) -> None:
    from app.bootstrap import abrir_proyecto

    ctx = bootstrap(raiz=str(raiz_temporal))
    proyecto = ctx.projects.crear_proyecto(nombre="Con trabajo real", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    origenes_dir = raiz_temporal / "_origenes_de_prueba"
    origenes_dir.mkdir(exist_ok=True)
    archivo = origenes_dir / "documento.txt"
    archivo.write_text("contenido de prueba", encoding="utf-8")
    pctx.documents.registrar_documento(proyecto_id=proyecto.id, ruta_origen=str(archivo))
    pctx.session.close()  # libera el handle de proyecto.db antes de intentar eliminar

    with pytest.raises(ProjectInUseError) as exc_info:
        ctx.projects.eliminar_proyecto(proyecto.id)

    assert exc_info.value.cantidad_documentos == 1
    assert Path(proyecto.ruta_carpeta).is_dir()
    assert ctx.projects.obtener_proyecto(proyecto.id) is not None


def test_eliminar_proyecto_que_nunca_se_abrio_para_trabajar_tambien_funciona(raiz_temporal: Path) -> None:
    # Un proyecto recien creado ya tiene proyecto.yaml y sus subcarpetas
    # (create_structure()), pero proyecto.db todavia no existe -- nunca
    # se llamo a abrir_proyecto() sobre el. ProjectContentChecker debe
    # tratarlo como vacio sin necesitar crear proyecto.db solo para
    # responder (ver SqlAlchemyProjectContentChecker).
    ctx = bootstrap(raiz=str(raiz_temporal))
    proyecto = ctx.projects.crear_proyecto(nombre="Nunca abierto", perfil_id="perfil_generico")
    assert not (Path(proyecto.ruta_carpeta) / "proyecto.db").exists()

    ctx.projects.eliminar_proyecto(proyecto.id)

    assert not Path(proyecto.ruta_carpeta).exists()


def test_eliminar_proyecto_deja_un_evento_de_auditoria_que_sobrevive_al_borrado(raiz_temporal: Path) -> None:
    """Auditoria 2026-09-02 (hallazgo real de la auditoria independiente
    de esta misma ronda, severidad medio-alta): antes de este fix,
    eliminar un proyecto no dejaba ningun rastro en `eventos_auditoria`.
    De punta a punta contra SQLite real: el evento debe seguir siendo
    consultable despues del borrado, porque `eventos_auditoria` vive en
    `aplicacion.db` (la base global), separada de la carpeta del
    proyecto que se acaba de borrar."""
    from infrastructure.database.models import EventoAuditoriaModel

    ctx = bootstrap(raiz=str(raiz_temporal))
    proyecto = ctx.projects.crear_proyecto(nombre="Para eliminar con auditoria", perfil_id="perfil_generico")

    ctx.projects.eliminar_proyecto(proyecto.id)

    eventos = ctx.session.query(EventoAuditoriaModel).filter_by(proyecto_id=proyecto.id).all()
    acciones = sorted(e.accion for e in eventos)
    assert acciones == ["crear_proyecto", "eliminar_proyecto"]


def test_crear_proyecto_reutiliza_el_nombre_de_un_proyecto_archivado(raiz_temporal: Path) -> None:
    """Auditoria 2026-09-02 (hallazgo real de la auditoria independiente
    de esta misma ronda, severidad alta): de punta a punta contra SQLite
    real -- antes de este fix, la restriccion UNIQUE de la base
    bloqueaba esto con un IntegrityError crudo (ni siquiera llegaba a
    convertirse en DuplicateProjectNameError), sin importar que el
    proyecto existente estuviera archivado."""
    ctx = bootstrap(raiz=str(raiz_temporal))
    original = ctx.projects.crear_proyecto(nombre="Cliente ACME", perfil_id="perfil_generico")
    ctx.projects.archivar_proyecto(original.id)

    nuevo = ctx.projects.crear_proyecto(nombre="Cliente ACME", perfil_id="perfil_generico")

    assert nuevo.id != original.id
    assert nuevo.nombre == "Cliente ACME"
    activos = ctx.projects.listar_proyectos(incluir_archivados=False)
    assert {p.id for p in activos} == {nuevo.id}
