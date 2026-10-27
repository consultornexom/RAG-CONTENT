"""Casos de uso simples del ciclo de vida de un Trabajo (Fase 6):
IniciarPreparacion, IniciarEjecucion, CompletarTrabajo, FallarTrabajo,
PausarTrabajo, ReanudarTrabajo, CancelarTrabajo, ReintentarTrabajo y
RecuperarTrabajosInterrumpidos. Se agrupan en un solo archivo porque
cada uno es un envoltorio delgado sobre un metodo de dominio (obtener,
transicionar, guardar, auditar) -- mismo criterio de agrupacion que
tests/unit/domain/test_entities_documento.py usa para varios metodos de
una misma entidad."""
from __future__ import annotations

import pytest

from application.jobs.commands.cancelar_trabajo import CancelarTrabajo
from application.jobs.commands.completar_trabajo import CompletarTrabajo
from application.jobs.commands.fallar_trabajo import FallarTrabajo
from application.jobs.commands.iniciar_ejecucion import IniciarEjecucion
from application.jobs.commands.iniciar_preparacion import IniciarPreparacion
from application.jobs.commands.pausar_trabajo import PausarTrabajo
from application.jobs.commands.reanudar_trabajo import ReanudarTrabajo
from application.jobs.commands.recuperar_trabajos_interrumpidos import RecuperarTrabajosInterrumpidos
from application.jobs.commands.reintentar_trabajo import ReintentarTrabajo
from domain.jobs.entities import EstadoTrabajo, Trabajo, TipoTrabajo
from domain.jobs.exceptions import JobNotFoundError, ReintentosAgotadosError
from domain.jobs.ports import TrabajoRepository
from tests.unit.application._fakes import _FakeAuditLogger


class _FakeTrabajoRepository(TrabajoRepository):
    def __init__(self, trabajos: list[Trabajo] | None = None) -> None:
        self._por_id: dict[str, Trabajo] = {t.id: t for t in (trabajos or [])}

    def save(self, trabajo: Trabajo) -> None:
        self._por_id[trabajo.id] = trabajo

    def get(self, trabajo_id: str):
        return self._por_id.get(trabajo_id)

    def list(self):
        return list(self._por_id.values())

    def list_by_estado(self, estado: EstadoTrabajo):
        return [t for t in self._por_id.values() if t.estado == estado]

    def list_by_document(self, documento_id: str):
        return [t for t in self._por_id.values() if t.documento_id == documento_id]

    def list_pendientes_por_prioridad(self):
        return self.list_by_estado(EstadoTrabajo.PENDIENTE)


def _trabajo(**overrides) -> Trabajo:
    datos = {"proyecto_id": "PROY-0001", "tipo": TipoTrabajo.EXTRACCION, "documento_id": "doc-1"}
    datos.update(overrides)
    return Trabajo(**datos)


def test_iniciar_preparacion_sobre_trabajo_inexistente_falla() -> None:
    caso_de_uso = IniciarPreparacion(_FakeTrabajoRepository(), _FakeAuditLogger())
    with pytest.raises(JobNotFoundError):
        caso_de_uso.execute("no-existe")


def test_iniciar_preparacion_exitoso() -> None:
    trabajo = _trabajo()
    repo = _FakeTrabajoRepository([trabajo])
    audit = _FakeAuditLogger()
    resultado = IniciarPreparacion(repo, audit).execute(trabajo.id)

    assert resultado.estado == EstadoTrabajo.PREPARANDO
    assert repo.get(trabajo.id).estado == EstadoTrabajo.PREPARANDO
    assert [e.accion for e in audit.eventos] == ["iniciar_preparacion_trabajo"]


def test_iniciar_ejecucion_exitoso() -> None:
    trabajo = _trabajo().iniciar_preparacion()
    repo = _FakeTrabajoRepository([trabajo])
    resultado = IniciarEjecucion(repo, _FakeAuditLogger()).execute(trabajo.id)

    assert resultado.estado == EstadoTrabajo.EJECUTANDO
    assert resultado.iniciado_en is not None


def test_completar_trabajo_exitoso() -> None:
    trabajo = _trabajo().iniciar_preparacion().iniciar_ejecucion()
    repo = _FakeTrabajoRepository([trabajo])
    audit = _FakeAuditLogger()
    resultado = CompletarTrabajo(repo, audit).execute(trabajo.id)

    assert resultado.estado == EstadoTrabajo.COMPLETADO
    assert [e.accion for e in audit.eventos] == ["completar_trabajo"]


def test_fallar_trabajo_registra_mensaje_de_error() -> None:
    trabajo = _trabajo().iniciar_preparacion().iniciar_ejecucion()
    repo = _FakeTrabajoRepository([trabajo])
    audit = _FakeAuditLogger()
    resultado = FallarTrabajo(repo, audit).execute(trabajo.id, "el motor OCR no esta disponible")

    assert resultado.estado == EstadoTrabajo.FALLIDO
    assert resultado.mensaje_error == "el motor OCR no esta disponible"
    assert resultado.intentos == 1
    assert "el motor OCR no esta disponible" in audit.eventos[0].valor_nuevo


def test_pausar_y_reanudar() -> None:
    trabajo = _trabajo()
    repo = _FakeTrabajoRepository([trabajo])

    pausado = PausarTrabajo(repo, _FakeAuditLogger()).execute(trabajo.id)
    assert pausado.estado == EstadoTrabajo.PAUSADO

    reanudado = ReanudarTrabajo(repo, _FakeAuditLogger()).execute(trabajo.id)
    assert reanudado.estado == EstadoTrabajo.PENDIENTE


def test_cancelar_trabajo_pendiente() -> None:
    trabajo = _trabajo()
    repo = _FakeTrabajoRepository([trabajo])
    audit = _FakeAuditLogger()
    resultado = CancelarTrabajo(repo, audit).execute(trabajo.id)

    assert resultado.estado == EstadoTrabajo.CANCELADO
    assert [e.accion for e in audit.eventos] == ["cancelar_trabajo"]


def test_reintentar_trabajo_fallido() -> None:
    trabajo = _trabajo(max_intentos=3).iniciar_preparacion().iniciar_ejecucion().fallar("fallo transitorio")
    repo = _FakeTrabajoRepository([trabajo])
    audit = _FakeAuditLogger()
    resultado = ReintentarTrabajo(repo, audit).execute(trabajo.id)

    assert resultado.estado == EstadoTrabajo.PENDIENTE
    assert [e.accion for e in audit.eventos] == ["reintentar_trabajo"]


def test_reintentar_agotados_los_intentos_propaga_el_error_de_dominio() -> None:
    trabajo = _trabajo(max_intentos=1).iniciar_preparacion().iniciar_ejecucion().fallar("fallo persistente")
    repo = _FakeTrabajoRepository([trabajo])

    with pytest.raises(ReintentosAgotadosError):
        ReintentarTrabajo(repo, _FakeAuditLogger()).execute(trabajo.id)

    # El trabajo sigue FALLIDO -- el intento fallido de reintentar no debe mutar nada.
    assert repo.get(trabajo.id).estado == EstadoTrabajo.FALLIDO


def test_recuperar_trabajos_interrumpidos_marca_preparando_y_ejecutando_como_fallidos() -> None:
    huerfano_preparando = _trabajo(documento_id="doc-1").iniciar_preparacion()
    huerfano_ejecutando = _trabajo(documento_id="doc-2").iniciar_preparacion().iniciar_ejecucion()
    pendiente = _trabajo(documento_id="doc-3")
    repo = _FakeTrabajoRepository([huerfano_preparando, huerfano_ejecutando, pendiente])
    audit = _FakeAuditLogger()

    recuperados = RecuperarTrabajosInterrumpidos(repo, audit).execute()

    assert {t.id for t in recuperados} == {huerfano_preparando.id, huerfano_ejecutando.id}
    assert all(t.estado == EstadoTrabajo.FALLIDO for t in recuperados)
    assert repo.get(pendiente.id).estado == EstadoTrabajo.PENDIENTE  # no se toca
    assert len(audit.eventos) == 2


def test_recuperar_trabajos_interrumpidos_no_hace_nada_si_no_hay_huerfanos() -> None:
    pendiente = _trabajo()
    repo = _FakeTrabajoRepository([pendiente])

    recuperados = RecuperarTrabajosInterrumpidos(repo, _FakeAuditLogger()).execute()

    assert recuperados == []
