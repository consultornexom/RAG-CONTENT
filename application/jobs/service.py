"""Fachada del contexto Trabajos (ADR-001, seccion 4: ui solo depende de
application; workers puede depender de application directamente --
ambos importan solo esta clase, nunca ensamblan los casos de uso por su
cuenta)."""
from __future__ import annotations

from domain.documents.ports import DocumentRepository
from domain.jobs.entities import EstadoTrabajo, Prioridad, Trabajo, TipoTrabajo
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger

from .commands.cancelar_trabajo import CancelarTrabajo
from .commands.completar_trabajo import CompletarTrabajo
from .commands.encolar_trabajo import EncolarTrabajo
from .commands.fallar_trabajo import FallarTrabajo
from .commands.iniciar_ejecucion import IniciarEjecucion
from .commands.iniciar_preparacion import IniciarPreparacion
from .commands.pausar_trabajo import PausarTrabajo
from .commands.reanudar_trabajo import ReanudarTrabajo
from .commands.recuperar_trabajos_interrumpidos import RecuperarTrabajosInterrumpidos
from .commands.reintentar_trabajo import ReintentarTrabajo


class JobsService:
    def __init__(
        self,
        repository: TrabajoRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._encolar = EncolarTrabajo(repository, document_repository, audit)
        self._iniciar_preparacion = IniciarPreparacion(repository, audit)
        self._iniciar_ejecucion = IniciarEjecucion(repository, audit)
        self._completar = CompletarTrabajo(repository, audit)
        self._fallar = FallarTrabajo(repository, audit)
        self._pausar = PausarTrabajo(repository, audit)
        self._reanudar = ReanudarTrabajo(repository, audit)
        self._cancelar = CancelarTrabajo(repository, audit)
        self._reintentar = ReintentarTrabajo(repository, audit)
        self._recuperar_interrumpidos = RecuperarTrabajosInterrumpidos(repository, audit)

    def encolar_trabajo(
        self,
        proyecto_id: str,
        tipo: TipoTrabajo,
        documento_id: str,
        prioridad: Prioridad = Prioridad.NORMAL,
        max_intentos: int = 3,
    ) -> Trabajo:
        return self._encolar.execute(proyecto_id, tipo, documento_id, prioridad, max_intentos)

    def iniciar_preparacion(self, trabajo_id: str) -> Trabajo:
        return self._iniciar_preparacion.execute(trabajo_id)

    def iniciar_ejecucion(self, trabajo_id: str) -> Trabajo:
        return self._iniciar_ejecucion.execute(trabajo_id)

    def completar_trabajo(self, trabajo_id: str) -> Trabajo:
        return self._completar.execute(trabajo_id)

    def fallar_trabajo(self, trabajo_id: str, mensaje_error: str) -> Trabajo:
        return self._fallar.execute(trabajo_id, mensaje_error)

    def pausar_trabajo(self, trabajo_id: str) -> Trabajo:
        return self._pausar.execute(trabajo_id)

    def reanudar_trabajo(self, trabajo_id: str) -> Trabajo:
        return self._reanudar.execute(trabajo_id)

    def cancelar_trabajo(self, trabajo_id: str) -> Trabajo:
        return self._cancelar.execute(trabajo_id)

    def reintentar_trabajo(self, trabajo_id: str) -> Trabajo:
        return self._reintentar.execute(trabajo_id)

    def recuperar_trabajos_interrumpidos(self) -> list[Trabajo]:
        return self._recuperar_interrumpidos.execute()

    def obtener_trabajo(self, trabajo_id: str) -> Trabajo | None:
        return self._repository.get(trabajo_id)

    def listar_trabajos(self) -> list[Trabajo]:
        return self._repository.list()

    def listar_trabajos_por_estado(self, estado: EstadoTrabajo) -> list[Trabajo]:
        return self._repository.list_by_estado(estado)

    def listar_trabajos_de_documento(self, documento_id: str) -> list[Trabajo]:
        return self._repository.list_by_document(documento_id)

    def siguiente_trabajo_pendiente(self) -> Trabajo | None:
        """El trabajo PENDIENTE de mayor prioridad (y mas antiguo dentro
        de la misma prioridad) -- el que
        `workers.cola_de_trabajos.ColaDeTrabajos` debe despachar a
        continuacion. `None` si no hay ningun trabajo pendiente."""
        pendientes = self._repository.list_pendientes_por_prioridad()
        return pendientes[0] if pendientes else None
