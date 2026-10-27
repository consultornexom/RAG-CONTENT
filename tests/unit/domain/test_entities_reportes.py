"""Fase 8: domain.reports son value objects puros (sin metodos de
negocio) -- estas pruebas solo verifican los valores por defecto y que
las listas mutables no se comparten entre instancias (mismo riesgo que
cualquier `Field(default_factory=list)` de pydantic, ya cubierto para
otras entidades del proyecto)."""
from __future__ import annotations

from domain.reports.entities import (
    ActaCierreLote,
    FilaCalidad,
    FilaIncidencia,
    FilaInventario,
)


def test_fila_incidencia_vencida_desconocida_por_defecto() -> None:
    fila = FilaIncidencia(
        incidencia_id="inc-1",
        documento_id="doc-1",
        etapa="revision",
        tipo="cifra_dudosa",
        severidad="alta",
        estado="abierta",
        responsable="",
        abierta=True,
    )
    assert fila.vencida is None


def test_fila_calidad_advertencias_e_incumplimientos_por_defecto_vacios() -> None:
    fila = FilaCalidad(documento_id="doc-1", estado="validado", semaforo="amarillo")
    assert fila.incumplimientos == []
    assert fila.advertencias_extraccion == []
    assert fila.advertencias_markdown == []


def test_listas_por_defecto_no_se_comparten_entre_instancias() -> None:
    fila_1 = FilaCalidad(documento_id="doc-1", estado="validado", semaforo="verde")
    fila_2 = FilaCalidad(documento_id="doc-2", estado="validado", semaforo="verde")
    fila_1.incumplimientos.append("algo")
    fila_1.advertencias_extraccion.append("otra cosa")
    assert fila_2.incumplimientos == []
    assert fila_2.advertencias_extraccion == []


def test_fila_inventario_construye_con_todos_los_campos() -> None:
    fila = FilaInventario(
        documento_id="doc-1",
        nombre_original="politica.pdf",
        formato="pdf",
        area_propietaria="rh",
        prioridad="normal",
        criticidad="no_critico",
        estado="liberado",
        vigencia="vigente",
    )
    assert fila.vigencia == "vigente"


def test_acta_cierre_lote_version_por_defecto() -> None:
    acta = ActaCierreLote(lote_id="lote-1", nombre_lote="Lote 1")
    assert acta.version == "v1"
    assert acta.liberados == []
    assert acta.fecha_cierre is None
