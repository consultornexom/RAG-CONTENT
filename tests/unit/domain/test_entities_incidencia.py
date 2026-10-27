from __future__ import annotations

import pytest

from domain.incidents.entities import (
    EstadoIncidencia,
    EtapaIncidencia,
    Incidencia,
    SeveridadIncidencia,
    filtrar_criticas_abiertas,
)
from domain.incidents.exceptions import InvalidIncidentStateTransitionError


def _incidencia(**overrides) -> Incidencia:
    datos = {
        "proyecto_id": "PROY-0001",
        "documento_id": "doc-1",
        "etapa": EtapaIncidencia.REVISION,
        "tipo": "cifra_dudosa",
        "severidad": SeveridadIncidencia.ALTA,
        "evidencia": "La cifra '1,000,000' en la pagina 3 no coincide con el original.",
        "impacto": "Puede afectar la interpretacion del monto total del contrato.",
    }
    datos.update(overrides)
    return Incidencia(**datos)


def test_incidencia_nace_en_estado_abierta_sin_los_campos_del_ciclo() -> None:
    incidencia = _incidencia()
    assert incidencia.estado == EstadoIncidencia.ABIERTA
    assert incidencia.responsable is None
    assert incidencia.respuesta is None
    assert incidencia.decision is None
    assert incidencia.cierre is None


def test_tipo_vacio_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _incidencia(tipo="   ")


def test_evidencia_vacia_es_rechazada() -> None:
    with pytest.raises(ValueError):
        _incidencia(evidencia="")


# -- filtrar_criticas_abiertas (usada por Modulo 13, ver
# application.governance.verificar_documento_aprobable) --------------


def test_filtrar_criticas_abiertas_incluye_critica_abierta() -> None:
    critica = _incidencia(severidad=SeveridadIncidencia.CRITICA)
    assert filtrar_criticas_abiertas([critica]) == [critica]


def test_filtrar_criticas_abiertas_excluye_critica_cerrada() -> None:
    critica_cerrada = _incidencia(severidad=SeveridadIncidencia.CRITICA, estado=EstadoIncidencia.CERRADA)
    assert filtrar_criticas_abiertas([critica_cerrada]) == []


def test_filtrar_criticas_abiertas_excluye_no_critica_abierta() -> None:
    alta_abierta = _incidencia(severidad=SeveridadIncidencia.ALTA)
    assert filtrar_criticas_abiertas([alta_abierta]) == []


def test_filtrar_criticas_abiertas_lista_vacia_no_falla() -> None:
    assert filtrar_criticas_abiertas([]) == []


def test_esta_abierta_es_true_hasta_cerrarla() -> None:
    incidencia = _incidencia()
    assert incidencia.esta_abierta()

    ciclo_completo = (
        incidencia.asignar("ana@nexom.mx")
        .responder("Se revisa contra el original: la cifra si esta mal.")
        .decidir("Se corrige en la siguiente extraccion.", resuelta=True)
    )
    assert ciclo_completo.esta_abierta()  # RESUELTA todavia no es CERRADA

    cerrada = ciclo_completo.cerrar("Corregido y verificado en la version 2 del documento.")
    assert not cerrada.esta_abierta()


def test_ciclo_de_vida_completo_hasta_resuelta_y_cerrada() -> None:
    incidencia = _incidencia()

    asignada = incidencia.asignar("ana@nexom.mx")
    assert asignada.estado == EstadoIncidencia.ASIGNADA
    assert asignada.responsable == "ana@nexom.mx"

    respondida = asignada.responder("Se confirma la discrepancia contra el original.")
    assert respondida.estado == EstadoIncidencia.RESPONDIDA
    assert respondida.respuesta == "Se confirma la discrepancia contra el original."

    resuelta = respondida.decidir("Se corrige en la siguiente extraccion.", resuelta=True)
    assert resuelta.estado == EstadoIncidencia.RESUELTA
    assert resuelta.decision == "Se corrige en la siguiente extraccion."

    cerrada = resuelta.cerrar("Corregido y verificado.")
    assert cerrada.estado == EstadoIncidencia.CERRADA
    assert cerrada.cierre == "Corregido y verificado."


def test_ciclo_de_vida_hasta_bloqueada_tambien_se_puede_cerrar() -> None:
    incidencia = _incidencia(severidad=SeveridadIncidencia.CRITICA)
    respondida = incidencia.asignar("ana@nexom.mx").responder("Vigencia desconocida, no se puede confirmar.")

    bloqueada = respondida.decidir("No se puede avanzar sin confirmar vigencia.", resuelta=False)
    assert bloqueada.estado == EstadoIncidencia.BLOQUEADA

    cerrada = bloqueada.cerrar("Se cierra tras escalar a legal; el documento queda bloqueado aparte.")
    assert cerrada.estado == EstadoIncidencia.CERRADA


def test_no_se_puede_responder_sin_asignar_antes() -> None:
    incidencia = _incidencia()  # ABIERTA, sin asignar
    with pytest.raises(InvalidIncidentStateTransitionError):
        incidencia.responder("respuesta")


def test_no_se_puede_decidir_sin_responder_antes() -> None:
    asignada = _incidencia().asignar("ana@nexom.mx")
    with pytest.raises(InvalidIncidentStateTransitionError):
        asignada.decidir("decision", resuelta=True)


def test_no_se_puede_cerrar_sin_decidir_antes() -> None:
    respondida = _incidencia().asignar("ana@nexom.mx").responder("respuesta")
    with pytest.raises(InvalidIncidentStateTransitionError):
        respondida.cerrar("cierre")


def test_no_se_puede_asignar_dos_veces() -> None:
    asignada = _incidencia().asignar("ana@nexom.mx")
    with pytest.raises(InvalidIncidentStateTransitionError):
        asignada.asignar("luis@nexom.mx")


def test_no_se_puede_cerrar_una_incidencia_ya_cerrada() -> None:
    cerrada = (
        _incidencia()
        .asignar("ana@nexom.mx")
        .responder("respuesta")
        .decidir("decision", resuelta=True)
        .cerrar("cierre")
    )
    with pytest.raises(InvalidIncidentStateTransitionError):
        cerrada.cerrar("otro cierre")


def test_responsable_vacio_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _incidencia().asignar("   ")


def test_respuesta_vacia_es_rechazada() -> None:
    asignada = _incidencia().asignar("ana@nexom.mx")
    with pytest.raises(ValueError):
        asignada.responder("   ")


def test_decision_vacia_es_rechazada() -> None:
    respondida = _incidencia().asignar("ana@nexom.mx").responder("respuesta")
    with pytest.raises(ValueError):
        respondida.decidir("   ", resuelta=True)


def test_cierre_vacio_es_rechazado() -> None:
    resuelta = (
        _incidencia().asignar("ana@nexom.mx").responder("respuesta").decidir("decision", resuelta=True)
    )
    with pytest.raises(ValueError):
        resuelta.cerrar("   ")
