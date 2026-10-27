"""ColaDeTrabajos (Fase 6): modo sincrono deterministico + modo en
segundo plano con ThreadPoolExecutor real. Usa un JobsService real
(sobre repositorios falsos en memoria) y un DocumentsService FALSO --
no se necesita ejercitar extraccion/normalizacion/Markdown reales aqui,
eso ya lo cubren las pruebas de application.documents; esta prueba solo
verifica que ColaDeTrabajos invoca el metodo correcto de
DocumentsService por cada TipoTrabajo y que el ciclo de vida del
Trabajo (PREPARANDO -> EJECUTANDO -> COMPLETADO/FALLIDO) queda bien
registrado."""
from __future__ import annotations

import threading
import time

import pytest

from application.jobs.service import JobsService
from domain.audit.entities import EventoAuditoria
from domain.documents.entities import Documento, FormatoDocumento
from domain.documents.ports import DocumentRepository
from domain.jobs.entities import EstadoTrabajo, Prioridad, Trabajo, TipoTrabajo
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger
from workers import cola_de_trabajos as modulo_cola
from workers.cola_de_trabajos import ColaDeTrabajos

_HASH_VALIDO = "9" * 64


class _FakeDocumentRepository(DocumentRepository):
    def __init__(self, documentos: list[Documento] | None = None) -> None:
        self._por_id = {d.id: d for d in (documentos or [])}

    def save(self, documento):
        self._por_id[documento.id] = documento

    def get(self, documento_id):
        return self._por_id.get(documento_id)

    def get_by_hash(self, hash_sha256):
        return next((d for d in self._por_id.values() if d.hash_sha256 == hash_sha256), None)

    def list_by_estado(self, estado):
        return [d for d in self._por_id.values() if d.estado == estado]

    def list(self):
        return list(self._por_id.values())


class _FakeTrabajoRepository(TrabajoRepository):
    def __init__(self) -> None:
        self._por_id: dict[str, Trabajo] = {}
        self._lock = threading.Lock()

    def save(self, trabajo: Trabajo) -> None:
        with self._lock:
            self._por_id[trabajo.id] = trabajo

    def get(self, trabajo_id: str):
        with self._lock:
            return self._por_id.get(trabajo_id)

    def list(self):
        with self._lock:
            return list(self._por_id.values())

    def list_by_estado(self, estado: EstadoTrabajo):
        with self._lock:
            return [t for t in self._por_id.values() if t.estado == estado]

    def list_by_document(self, documento_id: str):
        with self._lock:
            return [t for t in self._por_id.values() if t.documento_id == documento_id]

    def list_pendientes_por_prioridad(self):
        pendientes = self.list_by_estado(EstadoTrabajo.PENDIENTE)
        from domain.jobs.entities import orden_prioridad

        return sorted(pendientes, key=lambda t: (orden_prioridad(t.prioridad), t.creado_en))


class _FakeAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []
        self._lock = threading.Lock()

    def record(self, proyecto_id, accion, valor_anterior, valor_nuevo, motivo):
        with self._lock:
            self.eventos.append(
                EventoAuditoria(
                    proyecto_id=proyecto_id,
                    accion=accion,
                    valor_anterior=valor_anterior,
                    valor_nuevo=valor_nuevo,
                    motivo=motivo,
                )
            )

    def list_by_project(self, proyecto_id):
        return [e for e in self.eventos if e.proyecto_id == proyecto_id]


class _FakeDocumentsService:
    """No hereda de DocumentsService (no es una implementacion de un
    puerto de domain -- es la propia fachada de application, una clase
    concreta) -- ColaDeTrabajos solo la llama por duck typing a traves
    de _EJECUTORES, igual que en produccion."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, str]] = []
        self.falla_con: Exception | None = None
        self.demora_segundos: float = 0.0
        self._en_curso = 0
        self._max_en_curso = 0
        self._lock = threading.Lock()

    def _ejecutar(self, metodo: str, documento_id: str) -> Documento:
        with self._lock:
            self.llamadas.append((metodo, documento_id))
            self._en_curso += 1
            self._max_en_curso = max(self._max_en_curso, self._en_curso)
        try:
            if self.demora_segundos:
                time.sleep(self.demora_segundos)
            if self.falla_con is not None:
                raise self.falla_con
            return _documento(documento_id)
        finally:
            with self._lock:
                self._en_curso -= 1

    def extraer_documento(self, documento_id: str) -> Documento:
        return self._ejecutar("extraer_documento", documento_id)

    def normalizar_documento(self, documento_id: str) -> Documento:
        return self._ejecutar("normalizar_documento", documento_id)

    def generar_markdown(self, documento_id: str) -> Documento:
        return self._ejecutar("generar_markdown", documento_id)


def _documento(documento_id: str = "doc-1") -> Documento:
    return Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
    )


def _construir(
    documentos: list[Documento] | None = None,
    max_trabajos_concurrentes: int = 2,
    permitir_segundo_plano: bool = False,
):
    document_repo = _FakeDocumentRepository(documentos or [_documento()])
    trabajo_repo = _FakeTrabajoRepository()
    audit = _FakeAuditLogger()
    jobs = JobsService(trabajo_repo, document_repo, audit)
    documents = _FakeDocumentsService()
    cola = ColaDeTrabajos(
        jobs,
        documents,
        max_trabajos_concurrentes=max_trabajos_concurrentes,
        # Agregado 2026-07-31 (tercera auditoria general): iniciar() ya
        # exige este flag explicito -- aqui es seguro pasarlo en True
        # porque los fakes de este archivo (_FakeTrabajoRepository, etc.)
        # ya son thread-safe por construccion (threading.Lock).
        permitir_segundo_plano=permitir_segundo_plano,
    )
    return cola, jobs, documents, trabajo_repo, audit


def test_max_trabajos_concurrentes_invalido_es_rechazado() -> None:
    with pytest.raises(ValueError):
        ColaDeTrabajos(None, None, max_trabajos_concurrentes=0)  # type: ignore[arg-type]


def test_procesar_siguiente_sin_pendientes_devuelve_none() -> None:
    cola, *_ = _construir()
    assert cola.procesar_siguiente() is None


def test_encolar_crea_el_trabajo_a_traves_de_jobs_service() -> None:
    """ColaDeTrabajos.encolar() (a diferencia de JobsService.encolar_trabajo(),
    ya probado en test_encolar_trabajo.py) ademas intenta despachar de
    inmediato -- sin un despachador en segundo plano corriendo
    (`iniciar()` nunca se llamo), _despachar() no hace nada (ver
    test_despachar_sin_executor_activo_no_hace_nada)."""
    cola, jobs, documents, repo, _audit = _construir()

    trabajo = cola.encolar("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1")

    assert trabajo.estado == EstadoTrabajo.PENDIENTE
    assert repo.get(trabajo.id) == trabajo
    assert documents.llamadas == []  # sin iniciar() no se despacha solo


def test_despachar_sin_executor_activo_no_hace_nada() -> None:
    cola, jobs, documents, _repo, _audit = _construir()
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1")

    cola._despachar()  # nunca se llamo a iniciar() -- self._executor es None

    assert documents.llamadas == []
    assert jobs.siguiente_trabajo_pendiente() is not None


def test_procesar_siguiente_ejecuta_el_metodo_correcto_por_tipo() -> None:
    cola, jobs, documents, _repo, _audit = _construir()
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1")

    resultado = cola.procesar_siguiente()

    assert resultado.estado == EstadoTrabajo.COMPLETADO
    assert documents.llamadas == [("extraer_documento", "doc-1")]


def test_procesar_siguiente_respeta_prioridad() -> None:
    cola, jobs, documents, _repo, _audit = _construir()
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1", Prioridad.BAJA)
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.NORMALIZACION, "doc-1", Prioridad.URGENTE)

    resultado = cola.procesar_siguiente()

    assert documents.llamadas == [("normalizar_documento", "doc-1")]
    assert resultado.tipo == TipoTrabajo.NORMALIZACION


def test_procesar_todos_los_pendientes_los_agota_en_orden() -> None:
    cola, jobs, documents, _repo, _audit = _construir()
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1", Prioridad.NORMAL)
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.NORMALIZACION, "doc-1", Prioridad.ALTA)
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.GENERACION_MARKDOWN, "doc-1", Prioridad.URGENTE)

    resultados = cola.procesar_todos_los_pendientes()

    assert [t.tipo for t in resultados] == [
        TipoTrabajo.GENERACION_MARKDOWN,
        TipoTrabajo.NORMALIZACION,
        TipoTrabajo.EXTRACCION,
    ]
    assert all(t.estado == EstadoTrabajo.COMPLETADO for t in resultados)
    assert jobs.siguiente_trabajo_pendiente() is None


def test_fallo_del_caso_de_uso_marca_el_trabajo_fallido_con_el_mensaje() -> None:
    cola, jobs, documents, repo, _audit = _construir()
    documents.falla_con = RuntimeError("el motor OCR no esta disponible")
    trabajo = jobs.encolar_trabajo("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1")

    resultado = cola.procesar_siguiente()

    assert resultado.estado == EstadoTrabajo.FALLIDO
    assert resultado.mensaje_error == "el motor OCR no esta disponible"
    assert repo.get(trabajo.id).estado == EstadoTrabajo.FALLIDO


def test_tipo_sin_ejecutor_registrado_falla_el_trabajo(monkeypatch) -> None:
    cola, jobs, documents, _repo, _audit = _construir()
    jobs.encolar_trabajo("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1")
    monkeypatch.delitem(modulo_cola._EJECUTORES, TipoTrabajo.EXTRACCION)

    resultado = cola.procesar_siguiente()

    assert resultado.estado == EstadoTrabajo.FALLIDO
    assert "sin ejecutor registrado" in resultado.mensaje_error


def test_iniciar_sin_permitir_segundo_plano_falla_claro() -> None:
    """Riesgo real encontrado en la tercera auditoria general
    2026-07-31: la sesion de SQLAlchemy real (infrastructure.database.
    engine) no es segura para usarse desde los hilos de un
    ThreadPoolExecutor -- iniciar() ahora exige permitir_segundo_plano=
    True explicito para evitar activar este modo por accidente contra
    un ColaDeTrabajos real (ver app/bootstrap.py, que la construye con
    el valor por defecto, False)."""
    cola, *_ = _construir(permitir_segundo_plano=False)
    with pytest.raises(RuntimeError, match="permitir_segundo_plano"):
        cola.iniciar()


def test_modo_en_segundo_plano_completa_los_trabajos_encolados() -> None:
    cola, jobs, documents, repo, _audit = _construir(max_trabajos_concurrentes=2, permitir_segundo_plano=True)
    documents.demora_segundos = 0.05
    for _ in range(3):
        jobs.encolar_trabajo("PROY-0001", TipoTrabajo.EXTRACCION, "doc-1")

    cola.iniciar()
    limite = time.monotonic() + 5
    while time.monotonic() < limite:
        pendientes = jobs.listar_trabajos_por_estado(EstadoTrabajo.PENDIENTE)
        if not pendientes and cola.trabajos_en_ejecucion() == 0:
            break
        time.sleep(0.02)
    cola.detener()

    completados = jobs.listar_trabajos_por_estado(EstadoTrabajo.COMPLETADO)
    assert len(completados) == 3
    # Control de recursos (Documento Maestro, seccion 4.8): nunca deben
    # correr mas de max_trabajos_concurrentes a la vez.
    assert documents._max_en_curso <= 2
    assert documents._max_en_curso >= 2  # con 3 trabajos y cupo para 2, en algun momento debieron solaparse


def test_iniciar_dos_veces_no_crea_un_segundo_executor() -> None:
    cola, jobs, documents, _repo, _audit = _construir(permitir_segundo_plano=True)
    cola.iniciar()
    try:
        primero = cola._executor
        cola.iniciar()
        assert cola._executor is primero
    finally:
        cola.detener()
