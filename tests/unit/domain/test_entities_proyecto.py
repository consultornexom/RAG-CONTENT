from __future__ import annotations

import pytest

from domain.projects.entities import EstadoProyecto, Proyecto
from domain.projects.exceptions import ProjectAlreadyArchivedError


def test_carpeta_normalizada_usa_id_y_nombre_en_minusculas() -> None:
    proyecto = Proyecto(id="PROY-0042", nombre="Agente de Recursos Humanos", perfil_id="perfil_generico")
    assert proyecto.carpeta_normalizada() == "PROY-0042_agente_de_recursos_humanos"


def test_carpeta_normalizada_conserva_letras_acentuadas_como_su_base_ascii() -> None:
    # Bug real encontrado al verificar la creacion de proyectos contra la
    # carpeta /proyectos real (2026-07-29): antes de la normalizacion
    # Unicode, una letra acentuada no caia ni en [a-zA-Z0-9] ni en el
    # separador -- quedaba eliminada en silencio (p.ej. "Area" perdia la
    # "A" y quedaba "rea"). Debe conservar la letra base.
    proyecto = Proyecto(id="PROY-0099", nombre="Área Legal - Configuración Ñoño N°5", perfil_id="perfil_generico")
    assert proyecto.carpeta_normalizada() == "PROY-0099_area_legal_configuracion_nono_n5"


def test_id_debe_seguir_el_formato_proy_0000() -> None:
    with pytest.raises(ValueError):
        Proyecto(id="RH-1", nombre="x", perfil_id="perfil_generico")


def test_nombre_vacio_no_es_valido() -> None:
    with pytest.raises(ValueError):
        Proyecto(id="PROY-0001", nombre="   ", perfil_id="perfil_generico")


def test_archivar_un_proyecto_activo_cambia_su_estado() -> None:
    # Auditoria 2026-09-02 (RAG_CONTENT_01): "tratamiento a proyecto que
    # no proceden, como eliminarlos" -- ver domain.projects.entities.
    # Proyecto.archivar() para el hallazgo completo.
    proyecto = Proyecto(id="PROY-0001", nombre="Proyecto de prueba", perfil_id="perfil_generico")
    assert proyecto.estado == EstadoProyecto.ACTIVO

    archivado = proyecto.archivar()

    assert archivado.estado == EstadoProyecto.ARCHIVADO
    assert archivado.id == proyecto.id
    # Inmutable, como el resto de las transiciones del dominio: el
    # objeto original no cambia.
    assert proyecto.estado == EstadoProyecto.ACTIVO


def test_archivar_actualiza_updated_at() -> None:
    proyecto = Proyecto(id="PROY-0001", nombre="Proyecto de prueba", perfil_id="perfil_generico")
    archivado = proyecto.archivar()
    assert archivado.updated_at >= proyecto.updated_at


def test_archivar_un_proyecto_ya_archivado_falla() -> None:
    proyecto = Proyecto(
        id="PROY-0001", nombre="Proyecto de prueba", perfil_id="perfil_generico", estado=EstadoProyecto.ARCHIVADO
    )
    with pytest.raises(ProjectAlreadyArchivedError):
        proyecto.archivar()
