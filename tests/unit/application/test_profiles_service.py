from __future__ import annotations

import pytest

from application.profiles.service import ProfilesService
from domain.profiles.entities import CampoMetadato, PerfilProyecto, TipoDato
from domain.profiles.exceptions import ProfileNotFoundError, ProfileVersionAlreadyExistsError
from domain.profiles.ports import ProfileRepository


class _FakeProfileRepository(ProfileRepository):
    """Doble de pruebas en memoria -- misma semantica de inmutabilidad
    por version que YamlProfileRepository, sin tocar el disco."""

    def __init__(self) -> None:
        self._almacen: dict[str, dict[str, PerfilProyecto]] = {}

    def get(self, perfil_id):
        versiones = self.list_versions(perfil_id)
        if not versiones:
            return None
        return self.get_version(perfil_id, versiones[-1])

    def get_version(self, perfil_id, version):
        return self._almacen.get(perfil_id, {}).get(version)

    def list(self):
        return [self.get(pid) for pid in self._almacen if self.get(pid) is not None]

    def list_versions(self, perfil_id):
        def clave(v: str) -> tuple[int, int]:
            mayor, menor = v.split(".")
            return (int(mayor), int(menor))

        return sorted(self._almacen.get(perfil_id, {}), key=clave)

    def save(self, perfil):
        versiones = self._almacen.setdefault(perfil.id, {})
        if perfil.version in versiones:
            raise ProfileVersionAlreadyExistsError(perfil.id, perfil.version)
        versiones[perfil.version] = perfil


@pytest.fixture()
def service() -> ProfilesService:
    return ProfilesService(_FakeProfileRepository())


def test_crear_perfil_publica_primera_version(service: ProfilesService) -> None:
    perfil = service.crear_perfil(
        perfil_id="perfil_x",
        campos_metadato=[CampoMetadato(field_id="titulo", nombre_visible="Titulo", tipo_dato=TipoDato.TEXTO)],
    )
    assert perfil.version == "0.1"
    assert service.obtener_perfil("perfil_x") is not None


def test_crear_perfil_con_version_duplicada_falla(service: ProfilesService) -> None:
    service.crear_perfil(perfil_id="perfil_x")
    with pytest.raises(ProfileVersionAlreadyExistsError):
        service.crear_perfil(perfil_id="perfil_x")


def test_publicar_nueva_version_sin_perfil_previo_falla(service: ProfilesService) -> None:
    nueva = PerfilProyecto(id="perfil_y", version="0.2")
    with pytest.raises(ProfileNotFoundError):
        service.publicar_nueva_version("perfil_y", nueva)


def test_publicar_nueva_version_anterior_o_igual_falla(service: ProfilesService) -> None:
    service.crear_perfil(perfil_id="perfil_z", version="0.2")
    with pytest.raises(ValueError):
        service.publicar_nueva_version("perfil_z", PerfilProyecto(id="perfil_z", version="0.1"))
    with pytest.raises(ValueError):
        service.publicar_nueva_version("perfil_z", PerfilProyecto(id="perfil_z", version="0.2"))


def test_publicar_nueva_version_posterior_no_pisa_la_anterior(service: ProfilesService) -> None:
    service.crear_perfil(
        perfil_id="perfil_w",
        version="0.1",
        campos_metadato=[CampoMetadato(field_id="titulo", nombre_visible="Titulo", tipo_dato=TipoDato.TEXTO)],
    )
    service.publicar_nueva_version(
        "perfil_w",
        PerfilProyecto(
            id="perfil_w",
            version="0.2",
            campos_metadato=[
                CampoMetadato(field_id="titulo", nombre_visible="Titulo", tipo_dato=TipoDato.TEXTO),
                CampoMetadato(field_id="notas", nombre_visible="Notas", tipo_dato=TipoDato.TEXTO_LARGO, obligatorio=False),
            ],
        ),
    )
    assert service.listar_versiones("perfil_w") == ["0.1", "0.2"]
    # La version 0.1 sigue intacta.
    v1 = service.obtener_version("perfil_w", "0.1")
    assert v1 is not None
    assert len(v1.campos_metadato) == 1
    # La version vigente es la 0.2.
    vigente = service.obtener_perfil("perfil_w")
    assert vigente is not None
    assert vigente.version == "0.2"


def test_comparar_versiones_detecta_campos_agregados_y_eliminados(service: ProfilesService) -> None:
    service.crear_perfil(
        perfil_id="perfil_v",
        version="0.1",
        campos_metadato=[
            CampoMetadato(field_id="titulo", nombre_visible="Titulo", tipo_dato=TipoDato.TEXTO),
            CampoMetadato(field_id="viejo", nombre_visible="Viejo", tipo_dato=TipoDato.TEXTO, obligatorio=False),
        ],
    )
    service.publicar_nueva_version(
        "perfil_v",
        PerfilProyecto(
            id="perfil_v",
            version="0.2",
            campos_metadato=[
                CampoMetadato(field_id="titulo", nombre_visible="Titulo oficial", tipo_dato=TipoDato.TEXTO),
                CampoMetadato(field_id="nuevo", nombre_visible="Nuevo", tipo_dato=TipoDato.TEXTO, obligatorio=False),
            ],
        ),
    )
    comparacion = service.comparar_versiones("perfil_v", "0.1", "0.2")
    assert comparacion.campos_agregados == ["nuevo"]
    assert comparacion.campos_eliminados == ["viejo"]
    assert comparacion.campos_modificados == ["titulo"]
    assert comparacion.hay_cambios_incompatibles is True
