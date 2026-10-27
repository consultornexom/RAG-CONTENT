from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from domain.profiles.entities import CampoMetadato, PerfilProyecto, TipoDato
from domain.profiles.exceptions import ProfileVersionAlreadyExistsError, VersionDePerfilInvalidaError
from infrastructure.filesystem.profile_loader import YamlProfileRepository

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_perfiles_test")


@pytest.fixture()
def repo():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield YamlProfileRepository(RAIZ_PRUEBA)
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_save_y_get_recuperan_el_perfil_guardado(repo: YamlProfileRepository) -> None:
    perfil = PerfilProyecto(
        id="perfil_disco",
        version="0.1",
        campos_metadato=[CampoMetadato(field_id="titulo", nombre_visible="Titulo", tipo_dato=TipoDato.TEXTO)],
    )
    repo.save(perfil)

    recuperado = repo.get("perfil_disco")
    assert recuperado is not None
    assert recuperado.version == "0.1"
    assert recuperado.campos_metadato[0].field_id == "titulo"


def test_save_no_permite_sobrescribir_una_version_publicada(repo: YamlProfileRepository) -> None:
    perfil = PerfilProyecto(id="perfil_disco", version="0.1")
    repo.save(perfil)
    with pytest.raises(ProfileVersionAlreadyExistsError):
        repo.save(perfil)


def test_get_devuelve_la_version_de_numero_mas_alto(repo: YamlProfileRepository) -> None:
    repo.save(PerfilProyecto(id="perfil_disco", version="0.2"))
    repo.save(PerfilProyecto(id="perfil_disco", version="0.10"))
    repo.save(PerfilProyecto(id="perfil_disco", version="0.9"))

    vigente = repo.get("perfil_disco")
    assert vigente is not None
    assert vigente.version == "0.10"  # comparacion semantica, no alfabetica
    assert repo.list_versions("perfil_disco") == ["0.2", "0.9", "0.10"]


def test_get_de_perfil_inexistente_devuelve_none(repo: YamlProfileRepository) -> None:
    assert repo.get("no_existe") is None
    assert repo.get_version("no_existe", "0.1") is None


def test_archivo_de_perfil_mal_nombrado_lanza_excepcion_de_dominio(repo: YamlProfileRepository) -> None:
    """Hallazgo real de la cuarta auditoria general (2026-08-01): un
    archivo YAML de perfil mal nombrado (copia manual, typo, version con
    formato invalido) en `perfiles/<id>/` hacia que `list_versions()`
    lanzara un `ValueError` nativo de Python (de `int('x')`) en vez de
    una excepcion de dominio traducible a un mensaje amigable en la UI."""
    perfil = PerfilProyecto(id="perfil_disco", version="0.1")
    repo.save(perfil)
    # Simula el archivo mal nombrado directamente en disco -- no se puede
    # producir via `save()`, que ya valida el formato a traves de
    # PerfilProyecto.version.
    (RAIZ_PRUEBA / "perfil_disco" / "version_invalida.yaml").write_text("id: perfil_disco\nversion: x\n")

    with pytest.raises(VersionDePerfilInvalidaError):
        repo.list_versions("perfil_disco")

    with pytest.raises(VersionDePerfilInvalidaError):
        repo.get("perfil_disco")
