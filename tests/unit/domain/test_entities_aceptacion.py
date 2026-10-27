"""Fase 9: domain.acceptance -- InformeAceptacion.aprobado()/
esta_completo() son las unicas dos consultas con logica real de este
contexto (el resto son value objects puros)."""
from __future__ import annotations

from domain.acceptance.entities import CriterioDominio, CriterioUmbral, InformeAceptacion


def _informe(criterios_dominio=None, criterios_umbral=None) -> InformeAceptacion:
    return InformeAceptacion(
        fecha="2026-07-29T00:00:00+00:00",
        corpus_ruta="/tmp/corpus",
        documentos_evaluados=["a.pdf"],
        criterios_dominio=criterios_dominio or [],
        criterios_umbral=criterios_umbral or [],
    )


def test_informe_vacio_esta_aprobado_y_completo() -> None:
    informe = _informe()
    assert informe.aprobado() is True
    assert informe.esta_completo() is True


def test_un_dominio_pendiente_no_esta_completo_pero_si_aprobado() -> None:
    informe = _informe(
        criterios_dominio=[
            CriterioDominio(dominio="OCR", descripcion="d", cumplido=None, detalle="sin corpus"),
            CriterioDominio(dominio="Inventario", descripcion="d", cumplido=True, detalle="ok"),
        ]
    )
    assert informe.esta_completo() is False
    assert informe.aprobado() is True


def test_un_dominio_fallido_no_esta_aprobado() -> None:
    informe = _informe(
        criterios_dominio=[CriterioDominio(dominio="Inventario", descripcion="d", cumplido=False, detalle="falla")]
    )
    assert informe.aprobado() is False


def test_un_umbral_incumplido_no_esta_aprobado() -> None:
    informe = _informe(
        criterios_umbral=[
            CriterioUmbral(indicador="Incidencias criticas abiertas", umbral_esperado="0", valor_observado="1", cumplido=False)
        ]
    )
    assert informe.aprobado() is False


def test_todos_los_umbrales_cumplidos_y_dominios_ok_aprueba() -> None:
    informe = _informe(
        criterios_dominio=[CriterioDominio(dominio="Inventario", descripcion="d", cumplido=True, detalle="ok")],
        criterios_umbral=[
            CriterioUmbral(indicador="Documentos con hash", umbral_esperado="100%", valor_observado="100%", cumplido=True)
        ],
    )
    assert informe.aprobado() is True
    assert informe.esta_completo() is True
