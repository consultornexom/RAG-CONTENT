from __future__ import annotations

import pytest

from domain.profiles.entities import (
    CampoMetadato,
    Catalogo,
    EntradaCatalogo,
    PerfilProyecto,
    ReglaNormalizacion,
    ReglaValidacion,
    TipoDato,
    clave_version,
)
from domain.profiles.exceptions import VersionDePerfilInvalidaError


def _perfil_minimo(**overrides) -> PerfilProyecto:
    datos = {
        "id": "perfil_prueba",
        "version": "0.1",
        "campos_metadato": [
            CampoMetadato(field_id="titulo", nombre_visible="Titulo", tipo_dato=TipoDato.TEXTO),
        ],
    }
    datos.update(overrides)
    return PerfilProyecto(**datos)


def test_campo_de_tipo_catalogo_requiere_catalogo_declarado() -> None:
    with pytest.raises(ValueError):
        CampoMetadato(field_id="area", nombre_visible="Area", tipo_dato=TipoDato.CATALOGO)


def test_campo_de_tipo_catalogo_con_catalogo_declarado_es_valido() -> None:
    campo = CampoMetadato(
        field_id="area", nombre_visible="Area", tipo_dato=TipoDato.CATALOGO, catalogo="areas"
    )
    assert campo.catalogo == "areas"


def test_field_id_debe_ser_snake_case() -> None:
    with pytest.raises(ValueError):
        CampoMetadato(field_id="Area Propietaria", nombre_visible="Area", tipo_dato=TipoDato.TEXTO)


def test_perfil_rechaza_campo_que_referencia_catalogo_inexistente() -> None:
    with pytest.raises(ValueError):
        _perfil_minimo(
            campos_metadato=[
                CampoMetadato(
                    field_id="area", nombre_visible="Area", tipo_dato=TipoDato.CATALOGO, catalogo="areas"
                )
            ],
            catalogos=[],
        )


def test_perfil_acepta_campo_con_catalogo_definido() -> None:
    perfil = _perfil_minimo(
        campos_metadato=[
            CampoMetadato(
                field_id="area", nombre_visible="Area", tipo_dato=TipoDato.CATALOGO, catalogo="areas"
            )
        ],
        catalogos=[Catalogo(nombre="areas", entradas=[EntradaCatalogo(codigo="rh", etiqueta="RH")])],
    )
    assert perfil.catalogos[0].contiene("rh")
    assert not perfil.catalogos[0].contiene("legal")


def test_perfil_rechaza_regla_que_referencia_field_id_inexistente() -> None:
    with pytest.raises(ValueError):
        _perfil_minimo(
            reglas_validacion=[ReglaValidacion(field_id="no_existe", tipo_regla="fecha_no_futura")]
        )


def test_version_debe_seguir_formato_numerico() -> None:
    with pytest.raises(ValueError):
        _perfil_minimo(version="v1")


def test_campos_obligatorios_filtra_correctamente() -> None:
    perfil = _perfil_minimo(
        campos_metadato=[
            CampoMetadato(field_id="titulo", nombre_visible="Titulo", tipo_dato=TipoDato.TEXTO, obligatorio=True),
            CampoMetadato(field_id="notas", nombre_visible="Notas", tipo_dato=TipoDato.TEXTO_LARGO, obligatorio=False),
        ]
    )
    obligatorios = [c.field_id for c in perfil.campos_obligatorios()]
    assert obligatorios == ["titulo"]


def test_firma_sha256_es_determinista_y_sensible_al_contenido() -> None:
    perfil_a = _perfil_minimo()
    perfil_b = _perfil_minimo()
    assert perfil_a.firma_sha256() == perfil_b.firma_sha256()

    perfil_c = _perfil_minimo(descripcion="cambio minimo")
    assert perfil_c.firma_sha256() != perfil_a.firma_sha256()


def test_reglas_normalizacion_por_defecto_es_lista_vacia() -> None:
    perfil = _perfil_minimo()
    assert perfil.reglas_normalizacion == []


def test_reglas_normalizacion_se_pueden_declarar() -> None:
    perfil = _perfil_minimo(
        reglas_normalizacion=[
            ReglaNormalizacion(tipo_regla="colapsar_saltos_de_linea", parametros={}),
            ReglaNormalizacion(
                tipo_regla="expandir_acronimo", parametros={"acronimo": "RH", "expansion": "Recursos Humanos"}
            ),
        ]
    )
    assert [r.tipo_regla for r in perfil.reglas_normalizacion] == ["colapsar_saltos_de_linea", "expandir_acronimo"]


def test_firma_sha256_cambia_si_cambian_las_reglas_de_normalizacion() -> None:
    perfil_sin_reglas = _perfil_minimo()
    perfil_con_reglas = _perfil_minimo(
        reglas_normalizacion=[ReglaNormalizacion(tipo_regla="colapsar_saltos_de_linea", parametros={})]
    )
    assert perfil_sin_reglas.firma_sha256() != perfil_con_reglas.firma_sha256()


def test_clave_version_ordena_semanticamente_no_alfabeticamente() -> None:
    assert clave_version("0.9") < clave_version("0.10")
    assert clave_version("1.0") > clave_version("0.99")


def test_clave_version_formato_invalido_lanza_excepcion_de_dominio() -> None:
    """Hallazgo real de la cuarta auditoria general (2026-08-01): antes
    esta conversion estaba duplicada en application e infrastructure,
    cada una lanzando un ValueError nativo de Python (`int('x')`) ante un
    formato invalido -- ahora es un unico punto en domain que traduce eso
    a una excepcion propia del contexto."""
    with pytest.raises(VersionDePerfilInvalidaError):
        clave_version("x")
    with pytest.raises(VersionDePerfilInvalidaError):
        clave_version("1.2.3")
    with pytest.raises(VersionDePerfilInvalidaError):
        clave_version("1")
