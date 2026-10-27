"""RuleBasedNormalizationEngine (Modulo 9) -- motor de reglas propio,
sin dependencias externas ni de red, asi que se prueba de forma directa
y exhaustiva (a diferencia de OCR/transcripcion, aqui no hay ninguna
restriccion real de entorno que documentar).
"""
from __future__ import annotations

from domain.documents.exceptions import ReglaNormalizacionDesconocidaError
from domain.profiles.entities import ReglaNormalizacion
from infrastructure.normalization.rule_based_normalization_engine import RuleBasedNormalizationEngine

import pytest


def _regla(tipo_regla: str, **parametros: str) -> ReglaNormalizacion:
    return ReglaNormalizacion(tipo_regla=tipo_regla, parametros=parametros)


def test_sin_reglas_devuelve_el_markdown_intacto() -> None:
    engine = RuleBasedNormalizationEngine()
    resultado = engine.normalizar("# Titulo\n\ncontenido", [])
    assert resultado.markdown_normalizado == "# Titulo\n\ncontenido"
    assert resultado.cambios == []


def test_eliminar_linea_repetida_quita_todas_las_apariciones() -> None:
    engine = RuleBasedNormalizationEngine()
    markdown = "Confidencial\nContenido real\nConfidencial\n"
    resultado = engine.normalizar(markdown, [_regla("eliminar_linea_repetida", texto="Confidencial")])
    assert "Confidencial" not in resultado.markdown_normalizado
    assert "Contenido real" in resultado.markdown_normalizado
    assert resultado.cambios == ["Se eliminaron 2 linea(s) repetida(s): 'Confidencial'."]


def test_eliminar_linea_repetida_sin_coincidencias_no_deja_cambio() -> None:
    engine = RuleBasedNormalizationEngine()
    resultado = engine.normalizar("contenido", [_regla("eliminar_linea_repetida", texto="no existe")])
    assert resultado.markdown_normalizado == "contenido"
    assert resultado.cambios == []


def test_colapsar_saltos_de_linea_reduce_a_un_parrafo() -> None:
    engine = RuleBasedNormalizationEngine()
    resultado = engine.normalizar("a\n\n\n\n\nb", [_regla("colapsar_saltos_de_linea")])
    assert resultado.markdown_normalizado == "a\n\nb"
    assert len(resultado.cambios) == 1


def test_colapsar_saltos_de_linea_sin_excesos_no_deja_cambio() -> None:
    engine = RuleBasedNormalizationEngine()
    resultado = engine.normalizar("a\n\nb", [_regla("colapsar_saltos_de_linea")])
    assert resultado.markdown_normalizado == "a\n\nb"
    assert resultado.cambios == []


def test_expandir_acronimo_solo_afecta_la_primera_aparicion() -> None:
    engine = RuleBasedNormalizationEngine()
    markdown = "El area de RH aprobo esto. RH tambien lo reviso."
    resultado = engine.normalizar(
        markdown, [_regla("expandir_acronimo", acronimo="RH", expansion="Recursos Humanos")]
    )
    assert "Recursos Humanos (RH) aprobo" in resultado.markdown_normalizado
    assert "RH tambien lo reviso" in resultado.markdown_normalizado
    assert resultado.markdown_normalizado.count("Recursos Humanos") == 1
    assert resultado.cambios == ["Se expandio la primera aparicion de 'RH' a 'Recursos Humanos'."]


def test_expandir_acronimo_no_coincide_con_subcadenas() -> None:
    engine = RuleBasedNormalizationEngine()
    resultado = engine.normalizar(
        "PRHOYECTO especial", [_regla("expandir_acronimo", acronimo="RH", expansion="Recursos Humanos")]
    )
    assert resultado.markdown_normalizado == "PRHOYECTO especial"
    assert resultado.cambios == []


def test_redactar_patron_reemplaza_todas_las_coincidencias() -> None:
    engine = RuleBasedNormalizationEngine()
    markdown = "Contacto: ana@ejemplo.com o luis@ejemplo.com"
    resultado = engine.normalizar(
        markdown, [_regla("redactar_patron", patron=r"[\w.+-]+@[\w-]+\.[\w.-]+", descripcion="correo")]
    )
    assert "ana@ejemplo.com" not in resultado.markdown_normalizado
    assert resultado.markdown_normalizado.count("[DATO SENSIBLE REDACTADO]") == 2
    assert resultado.cambios == ["Se redactaron 2 coincidencia(s) del patron 'correo'."]


def test_redactar_patron_invalido_lanza_excepcion_clara() -> None:
    engine = RuleBasedNormalizationEngine()
    with pytest.raises(ReglaNormalizacionDesconocidaError):
        engine.normalizar("contenido", [_regla("redactar_patron", patron="(")])


def test_normalizar_espacios_en_tablas_recorta_celdas() -> None:
    engine = RuleBasedNormalizationEngine()
    markdown = "| nombre  |  area |\n|---|---|\n| Ana |  RH  |"
    resultado = engine.normalizar(markdown, [_regla("normalizar_espacios_en_tablas")])
    assert "| nombre | area |" in resultado.markdown_normalizado
    assert "| Ana | RH |" in resultado.markdown_normalizado
    assert resultado.cambios


def test_normalizar_espacios_en_tablas_sin_excesos_no_deja_cambio() -> None:
    engine = RuleBasedNormalizationEngine()
    markdown = "| nombre | area |\n| --- | --- |\n| Ana | RH |"
    resultado = engine.normalizar(markdown, [_regla("normalizar_espacios_en_tablas")])
    assert resultado.markdown_normalizado == markdown
    assert resultado.cambios == []


def test_regla_desconocida_lanza_excepcion_en_vez_de_ignorarse() -> None:
    engine = RuleBasedNormalizationEngine()
    with pytest.raises(ReglaNormalizacionDesconocidaError):
        engine.normalizar("contenido", [_regla("regla_que_no_existe")])


def test_varias_reglas_se_aplican_en_orden_y_acumulan_cambios() -> None:
    engine = RuleBasedNormalizationEngine()
    markdown = "Confidencial\n\n\n\nEl area de RH revisa esto.\n\nConfidencial"
    reglas = [
        _regla("eliminar_linea_repetida", texto="Confidencial"),
        _regla("colapsar_saltos_de_linea"),
        _regla("expandir_acronimo", acronimo="RH", expansion="Recursos Humanos"),
    ]
    resultado = engine.normalizar(markdown, reglas)
    assert "Confidencial" not in resultado.markdown_normalizado
    assert "Recursos Humanos (RH)" in resultado.markdown_normalizado
    assert len(resultado.cambios) == 3
