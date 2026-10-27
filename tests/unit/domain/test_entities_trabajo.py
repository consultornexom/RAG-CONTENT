from __future__ import annotations

import pytest

from domain.jobs.entities import EstadoTrabajo, Prioridad, Trabajo, TipoTrabajo, orden_prioridad
from domain.jobs.exceptions import InvalidJobStateTransitionError, ReintentosAgotadosError


def _trabajo(**overrides) -> Trabajo:
    datos = {
        "proyecto_id": "PROY-0001",
        "tipo": TipoTrabajo.EXTRACCION,
        "documento_id": "doc-1",
    }
    datos.update(overrides)
    return Trabajo(**datos)


def test_trabajo_nace_en_estado_pendiente() -> None:
    trabajo = _trabajo()
    assert trabajo.estado == EstadoTrabajo.PENDIENTE
    assert trabajo.intentos == 0
    assert trabajo.iniciado_en is None
    assert trabajo.finalizado_en is None


def test_documento_id_vacio_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _trabajo(documento_id="   ")


def test_max_intentos_no_positivo_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _trabajo(max_intentos=0)


def test_orden_prioridad_urgente_primero() -> None:
    assert orden_prioridad(Prioridad.URGENTE) < orden_prioridad(Prioridad.ALTA)
    assert orden_prioridad(Prioridad.ALTA) < orden_prioridad(Prioridad.NORMAL)
    assert orden_prioridad(Prioridad.NORMAL) < orden_prioridad(Prioridad.BAJA)


def test_flujo_completo_hasta_completado() -> None:
    trabajo = _trabajo()
    trabajo = trabajo.iniciar_preparacion()
    assert trabajo.estado == EstadoTrabajo.PREPARANDO

    trabajo = trabajo.iniciar_ejecucion()
    assert trabajo.estado == EstadoTrabajo.EJECUTANDO
    assert trabajo.iniciado_en is not None

    trabajo = trabajo.completar()
    assert trabajo.estado == EstadoTrabajo.COMPLETADO
    assert trabajo.finalizado_en is not None
    assert trabajo.mensaje_error is None


def test_no_se_puede_saltar_de_pendiente_a_ejecutando() -> None:
    trabajo = _trabajo()
    with pytest.raises(InvalidJobStateTransitionError):
        trabajo.iniciar_ejecucion()


def test_fallar_incrementa_intentos_y_guarda_mensaje() -> None:
    trabajo = _trabajo().iniciar_preparacion().iniciar_ejecucion()
    fallido = trabajo.fallar("el motor OCR no esta disponible")
    assert fallido.estado == EstadoTrabajo.FALLIDO
    assert fallido.intentos == 1
    assert fallido.mensaje_error == "el motor OCR no esta disponible"
    assert fallido.finalizado_en is None  # FALLIDO no es terminal -- todavia puede reintentarse


def test_fallar_desde_preparando_tambien_es_valido() -> None:
    trabajo = _trabajo().iniciar_preparacion()
    fallido = trabajo.fallar("no se pudo resolver el documento")
    assert fallido.estado == EstadoTrabajo.FALLIDO


def test_completado_es_terminal() -> None:
    trabajo = _trabajo().iniciar_preparacion().iniciar_ejecucion().completar()
    with pytest.raises(InvalidJobStateTransitionError):
        trabajo.avanzar_a(EstadoTrabajo.PENDIENTE)


def test_ejecutando_no_admite_pausa_ni_cancelacion() -> None:
    """Decision deliberada (ver domain.jobs.entities._TRANSICIONES): un
    trabajo EJECUTANDO ya invoco el caso de uso pesado -- no hay forma
    segura de pausarlo o cancelarlo a la mitad."""
    trabajo = _trabajo().iniciar_preparacion().iniciar_ejecucion()
    with pytest.raises(InvalidJobStateTransitionError):
        trabajo.pausar()
    with pytest.raises(InvalidJobStateTransitionError):
        trabajo.cancelar()


def test_pausar_y_reanudar_desde_pendiente() -> None:
    trabajo = _trabajo()
    pausado = trabajo.pausar()
    assert pausado.estado == EstadoTrabajo.PAUSADO

    reanudado = pausado.reanudar()
    assert reanudado.estado == EstadoTrabajo.PENDIENTE


def test_cancelar_desde_pendiente_preparando_o_pausado_es_seguro() -> None:
    for construir in (
        lambda: _trabajo(),
        lambda: _trabajo().iniciar_preparacion(),
        lambda: _trabajo().pausar(),
    ):
        trabajo = construir()
        cancelado = trabajo.cancelar()
        assert cancelado.estado == EstadoTrabajo.CANCELADO
        assert cancelado.finalizado_en is not None


def test_reintentar_vuelve_a_pendiente_sin_agotar_intentos() -> None:
    fallido = _trabajo(max_intentos=3).iniciar_preparacion().iniciar_ejecucion().fallar("fallo transitorio")
    assert fallido.intentos == 1

    reintentado = fallido.reintentar()
    assert reintentado.estado == EstadoTrabajo.PENDIENTE
    assert reintentado.mensaje_error is None
    assert reintentado.intentos == 1  # reintentar() no incrementa -- solo fallar() lo hace


def test_reintentar_agotados_los_intentos_lanza_error() -> None:
    trabajo = _trabajo(max_intentos=1).iniciar_preparacion().iniciar_ejecucion().fallar("fallo persistente")
    assert trabajo.intentos == 1

    with pytest.raises(ReintentosAgotadosError):
        trabajo.reintentar()


def test_marcar_interrumpido_desde_preparando() -> None:
    trabajo = _trabajo().iniciar_preparacion()
    interrumpido = trabajo.marcar_interrumpido()
    assert interrumpido.estado == EstadoTrabajo.FALLIDO
    assert "interrumpido" in interrumpido.mensaje_error.lower()


def test_marcar_interrumpido_desde_ejecutando() -> None:
    trabajo = _trabajo().iniciar_preparacion().iniciar_ejecucion()
    interrumpido = trabajo.marcar_interrumpido()
    assert interrumpido.estado == EstadoTrabajo.FALLIDO
    assert interrumpido.intentos == 1
