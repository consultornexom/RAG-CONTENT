"""Entidades del contexto Trabajos (Fase 6 del orden aprobado 2026-07-28;
ADR-001 seccion 3 "vista de capas" y seccion 10 "Concurrencia y gestion
de trabajos"; Documento Maestro secciones 4.1 ("procesos pesados en
segundo plano con pausa, reanudacion, cancelacion, reintentos y
recuperacion"), 4.8 ("procesamiento paralelo y control de recursos") y
4.10 (entidad "TrabajoProcesamiento" del modelo de datos minimo).

`domain.jobs` no importa `domain.documents` en absoluto (regla de
aislamiento entre dominios ya establecida por `domain.incidents`,
`domain.validity` y `domain.governance`): `Trabajo.documento_id` es una
referencia por id, sin tipo ni validacion cruzada aqui -- quien resuelve
que el documento referenciado exista de verdad es
`application.jobs.commands.encolar_trabajo.EncolarTrabajo`, mismo
reparto de responsabilidades que `RegistrarIncidencia`.

`Prioridad` se redefine aqui (mismos cuatro valores que
`domain.documents.entities.Prioridad`) en vez de reutilizar esa clase --
duplicacion deliberada, no descuido: importar el enum de otro contexto
violaria la regla de dependencia entre capas (ADR-001, seccion 4:
"domain: nada externo... prohibido: application, infrastructure, ui,
cualquier biblioteca... de otro dominio")."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .exceptions import InvalidJobStateTransitionError, ReintentosAgotadosError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TipoTrabajo(str, Enum):
    """Que caso de uso pesado ejecuta este trabajo (Documento Maestro,
    seccion 4.8: "apto para paralelizar"). Deliberadamente acotado a los
    tres pasos del flujo de `DocumentsService` que ya existen como
    operaciones unicas y pesadas -- EXTRACCION cubre extraccion directa,
    OCR y transcripcion en un solo tipo porque
    `DocumentsService.extraer_documento()` ya decide internamente cual
    de las tres aplicar segun `Documento.tipo_procesamiento` (Modulo 4);
    no existe hoy un caso de uso separado para "solo OCR" o "solo
    transcripcion" que un trabajo pudiera encolar de forma distinta."""

    EXTRACCION = "extraccion"
    NORMALIZACION = "normalizacion"
    GENERACION_MARKDOWN = "generacion_markdown"


class Prioridad(str, Enum):
    """Prioridad de un trabajo dentro de la cola (ADR-001, seccion 10:
    "control... de prioridad"). Ver nota del modulo sobre por que no se
    reutiliza `domain.documents.entities.Prioridad`."""

    BAJA = "baja"
    NORMAL = "normal"
    ALTA = "alta"
    URGENTE = "urgente"


_ORDEN_PRIORIDAD: dict[Prioridad, int] = {
    Prioridad.URGENTE: 0,
    Prioridad.ALTA: 1,
    Prioridad.NORMAL: 2,
    Prioridad.BAJA: 3,
}


def orden_prioridad(prioridad: Prioridad) -> int:
    """Menor valor = se atiende primero. Funcion pura reutilizada tanto
    por `infrastructure.database.job_repository.SqlAlchemyTrabajoRepository.
    list_pendientes_por_prioridad()` (orden en SQL) como por cualquier
    ordenamiento en memoria -- mismo principio que
    `domain.validity.entities.vigencia_desconocida()`: el criterio vive
    una sola vez en domain, nunca se duplica en infrastructure."""
    return _ORDEN_PRIORIDAD[prioridad]


class EstadoTrabajo(str, Enum):
    """Estados de trabajo exactos de ADR-001, seccion 10: "pendiente,
    preparando, ejecutando, pausado, completado, fallido, cancelado"."""

    PENDIENTE = "pendiente"
    PREPARANDO = "preparando"
    EJECUTANDO = "ejecutando"
    PAUSADO = "pausado"
    COMPLETADO = "completado"
    FALLIDO = "fallido"
    CANCELADO = "cancelado"


_TRANSICIONES: dict[EstadoTrabajo, frozenset[EstadoTrabajo]] = {
    EstadoTrabajo.PENDIENTE: frozenset({EstadoTrabajo.PREPARANDO, EstadoTrabajo.PAUSADO, EstadoTrabajo.CANCELADO}),
    EstadoTrabajo.PREPARANDO: frozenset({EstadoTrabajo.EJECUTANDO, EstadoTrabajo.FALLIDO, EstadoTrabajo.CANCELADO}),
    EstadoTrabajo.EJECUTANDO: frozenset({EstadoTrabajo.COMPLETADO, EstadoTrabajo.FALLIDO}),
    EstadoTrabajo.PAUSADO: frozenset({EstadoTrabajo.PENDIENTE, EstadoTrabajo.CANCELADO}),
    EstadoTrabajo.FALLIDO: frozenset({EstadoTrabajo.PENDIENTE}),
    EstadoTrabajo.COMPLETADO: frozenset(),
    EstadoTrabajo.CANCELADO: frozenset(),
}
"""Tabla de transiciones completa (Documento Maestro, seccion 4.1:
"pausa, reanudacion, cancelacion, reintentos y recuperacion").

Decision deliberada, documentada aqui porque no es obvia: EJECUTANDO NO
admite CANCELADO ni PAUSADO. Los casos de uso reales que un Trabajo
ejecuta (`DocumentsService.extraer_documento()`/
`normalizar_documento()`/`generar_markdown()`) son llamadas sincronas
atomicas, sin punto de control interno donde interrumpirse a la mitad
-- para cuando `workers.cola_de_trabajos.ColaDeTrabajos` podria observar
una senal de pausa/cancelacion, el caso de uso ya termino (con exito o
con excepcion) y ya persistio su propio efecto sobre el `Documento`.
Fingir una "cancelacion segura" de un trabajo EJECUTANDO seria
exactamente ese fallo silencioso que el Documento Maestro (seccion 4.1)
prohibe. La cancelacion real y segura (sin ningun efecto secundario
posible) solo se garantiza para PENDIENTE/PREPARANDO/PAUSADO -- ningun
caso de uso se invoco todavia. Ver `Trabajo.marcar_interrumpido()` para
la "recuperacion" de un trabajo que quedo huerfano en PREPARANDO o
EJECUTANDO tras un cierre no controlado de la aplicacion."""


class Trabajo(BaseModel):
    """Entidad `TrabajoProcesamiento` del modelo de datos minimo
    (Documento Maestro, seccion 4.10). Vive en la base de un unico
    proyecto (proyecto.db), igual que `Documento` -- nunca en la base
    global."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proyecto_id: str
    tipo: TipoTrabajo
    documento_id: str
    estado: EstadoTrabajo = EstadoTrabajo.PENDIENTE
    prioridad: Prioridad = Prioridad.NORMAL
    intentos: int = 0
    max_intentos: int = 3
    mensaje_error: Optional[str] = None
    creado_en: datetime = Field(default_factory=_utcnow)
    actualizado_en: datetime = Field(default_factory=_utcnow)
    iniciado_en: Optional[datetime] = None
    """Cuando el trabajo entro por primera vez a EJECUTANDO -- `None`
    mientras siga PENDIENTE/PREPARANDO/PAUSADO."""
    finalizado_en: Optional[datetime] = None
    """Cuando el trabajo llego a un estado terminal (COMPLETADO o
    CANCELADO) -- `None` en cualquier otro estado, incluido FALLIDO (un
    trabajo fallido todavia puede reintentarse, no es terminal)."""

    @field_validator("documento_id")
    @classmethod
    def _documento_id_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("documento_id no puede estar vacio")
        return v

    @field_validator("max_intentos")
    @classmethod
    def _max_intentos_positivo(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_intentos debe ser al menos 1")
        return v

    def avanzar_a(self, target: EstadoTrabajo) -> "Trabajo":
        target = EstadoTrabajo(target)
        permitidos = _TRANSICIONES[self.estado]
        if target not in permitidos:
            raise InvalidJobStateTransitionError(self.estado.value, target.value)
        data = self.model_dump()
        data["estado"] = target
        data["actualizado_en"] = _utcnow()
        return Trabajo(**data)

    def iniciar_preparacion(self) -> "Trabajo":
        """PENDIENTE -> PREPARANDO: el despachador de la cola
        (`workers.cola_de_trabajos.ColaDeTrabajos`) tomo este trabajo y
        va a resolver sus dependencias (por ejemplo, cargar el documento
        real) antes de invocar el caso de uso pesado."""
        return self.avanzar_a(EstadoTrabajo.PREPARANDO)

    def iniciar_ejecucion(self) -> "Trabajo":
        """PREPARANDO -> EJECUTANDO: el caso de uso pesado esta a punto
        de invocarse de verdad. Separado de `iniciar_preparacion()`
        (en vez de colapsarlos en un solo paso, a diferencia de
        `Documento.aprobar_para_markdown()`) porque ADR-001 seccion 10
        exige que ambos sean estados observables por separado -- un
        futuro panel de monitoreo (Fase 11) debe poder mostrar
        "preparando" mientras dura, por ejemplo, cargar un modelo de
        transcripcion."""
        trabajo = self.avanzar_a(EstadoTrabajo.EJECUTANDO)
        data = trabajo.model_dump()
        data["iniciado_en"] = data["iniciado_en"] or _utcnow()
        return Trabajo(**data)

    def completar(self) -> "Trabajo":
        """EJECUTANDO -> COMPLETADO: el caso de uso pesado devolvio sin
        lanzar ninguna excepcion."""
        trabajo = self.avanzar_a(EstadoTrabajo.COMPLETADO)
        data = trabajo.model_dump()
        data["finalizado_en"] = _utcnow()
        data["mensaje_error"] = None
        return Trabajo(**data)

    def fallar(self, mensaje_error: str) -> "Trabajo":
        """PREPARANDO o EJECUTANDO -> FALLIDO: el caso de uso pesado (o
        la preparacion previa) lanzo una excepcion. Incrementa
        `intentos` -- `reintentar()` decide despues, con ese contador,
        si todavia hay margen (Documento Maestro, seccion 4.1:
        "reintentos"). No es terminal: `finalizado_en` se deja en
        `None` porque un trabajo fallido todavia puede volver a
        PENDIENTE."""
        trabajo = self.avanzar_a(EstadoTrabajo.FALLIDO)
        data = trabajo.model_dump()
        data["mensaje_error"] = mensaje_error
        data["intentos"] = self.intentos + 1
        return Trabajo(**data)

    def marcar_interrumpido(self) -> "Trabajo":
        """PREPARANDO o EJECUTANDO -> FALLIDO, con un mensaje fijo de
        recuperacion (Documento Maestro, seccion 4.1: "recuperacion").
        Se usa exclusivamente al reabrir un proyecto
        (`application.jobs.commands.recuperar_trabajos_interrumpidos.
        RecuperarTrabajosInterrumpidos`, llamado una sola vez desde
        `app.bootstrap.abrir_proyecto()`) para los trabajos que quedaron
        huerfanos porque la aplicacion se cerro (o fallo) mientras
        corrian -- ya no existe ningun hilo real ejecutandolos. Reutiliza
        FALLIDO en vez de crear un estado nuevo: el mismo mecanismo de
        `reintentar()` (con su limite de `max_intentos`) decide despues
        si vale la pena volver a intentarlo, sin duplicar esa logica."""
        return self.fallar(
            "Trabajo interrumpido por un cierre no controlado de la aplicacion -- "
            "requiere revision manual antes de reintentar (no se puede confirmar si el "
            "caso de uso subyacente llego a completarse)."
        )

    def pausar(self) -> "Trabajo":
        """PENDIENTE -> PAUSADO: retiene el trabajo fuera de la cola sin
        cancelarlo. Solo aplicable mientras siga PENDIENTE -- ver el
        docstring de `_TRANSICIONES` sobre por que EJECUTANDO no admite
        pausa real."""
        return self.avanzar_a(EstadoTrabajo.PAUSADO)

    def reanudar(self) -> "Trabajo":
        """PAUSADO -> PENDIENTE: vuelve a hacerlo elegible para que el
        despachador de la cola lo tome segun su prioridad."""
        return self.avanzar_a(EstadoTrabajo.PENDIENTE)

    def cancelar(self) -> "Trabajo":
        """PENDIENTE, PREPARANDO o PAUSADO -> CANCELADO: "cancelacion
        segura" (ADR-001, seccion 10) porque en ninguno de esos tres
        estados se invoco todavia el caso de uso pesado -- cancelar
        nunca deja un efecto secundario a medias."""
        trabajo = self.avanzar_a(EstadoTrabajo.CANCELADO)
        data = trabajo.model_dump()
        data["finalizado_en"] = _utcnow()
        return Trabajo(**data)

    def reintentar(self) -> "Trabajo":
        """FALLIDO -> PENDIENTE, solo si `intentos < max_intentos`
        (Documento Maestro, seccion 4.1: "reintentos"). Agotado el
        limite, lanza `ReintentosAgotadosError` en vez de reintentar en
        silencio -- un trabajo que ya fallo `max_intentos` veces necesita
        intervencion humana, no otro intento automatico identico."""
        if self.intentos >= self.max_intentos:
            raise ReintentosAgotadosError(self.id, self.intentos, self.max_intentos)
        trabajo = self.avanzar_a(EstadoTrabajo.PENDIENTE)
        data = trabajo.model_dump()
        data["mensaje_error"] = None
        return Trabajo(**data)
