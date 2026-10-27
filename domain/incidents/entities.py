"""Entidades del contexto Incidencias (Modulo 10, Documento Maestro
seccion 4.6: "Controlar dudas y defectos"; ADR-001, seccion 5: "Una
incidencia critica abierta bloquea el avance del documento").

Campos esenciales segun la tabla de modulos (Documento Maestro, seccion
4.6, fila 10): "ID, etapa, tipo, severidad, evidencia, impacto,
responsable, estado, respuesta, decision y cierre". El ciclo de vida
(seccion 4.11.1: "registrar, asignar, resolver o bloquear incidencias";
seccion 7.1: reporte de incidencias "abiertas, cerradas") se modela como
una cadena lineal con una unica bifurcacion (RESPONDIDA -> RESUELTA o
BLOQUEADA), igual de estricta que el flujo principal de Documento pero
mucho mas corta -- no hace falta una tabla de transiciones permitidas
por estado, cada metodo declara directamente el estado de origen que
exige.

Limite deliberado de esta version: la aplicacion real de la regla "una
incidencia critica abierta bloquea el avance del documento" (Documento
Maestro, seccion 8.2: "Incidencias criticas abiertas: 0"; ver tambien
PerfilProyecto.incidencias_criticas_permitidas) es responsabilidad del
Modulo 13 (Estados y dependencias), todavia no construido -- este
modulo solo registra, gestiona y deja consultable el estado/severidad
de cada incidencia (ver
application.incidents.service.IncidentsService.existen_criticas_abiertas()),
sin impedir por si mismo ninguna transicion de Documento.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .exceptions import InvalidIncidentStateTransitionError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EtapaIncidencia(str, Enum):
    """Etapa del pipeline documental en la que se detecto la incidencia
    (Documento Maestro, seccion 4.6, Modulo 10: campo "etapa").
    Vocabulario cerrado a las etapas que ya existen en el pipeline real
    (Modulos 3 a 9 mas vigencia/aprobacion, seccion 4.7) -- el Modulo 8
    (revision, con GUI) sera el origen mas frecuente en la practica una
    vez que exista, pero cualquier etapa puede levantar una incidencia
    desde el backend."""

    INVENTARIO = "inventario"
    CLASIFICACION = "clasificacion"
    EXTRACCION = "extraccion"
    OCR = "ocr"
    TRANSCRIPCION = "transcripcion"
    REVISION = "revision"
    NORMALIZACION = "normalizacion"
    VIGENCIA = "vigencia"
    APROBACION = "aprobacion"


class SeveridadIncidencia(str, Enum):
    """Severidad de una incidencia. CRITICA es la unica que participa
    en la regla de bloqueo de liberacion (Documento Maestro, seccion
    8.2; ADR-001 seccion 5) -- ver el limite deliberado en el docstring
    del modulo: la aplicacion real de esa regla queda para el Modulo
    13."""

    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class EstadoIncidencia(str, Enum):
    """Ciclo de vida de una incidencia (Documento Maestro, seccion
    4.11.1: "registrar, asignar, resolver o bloquear incidencias";
    seccion 7.1: reporte de incidencias "abiertas, cerradas, criticas,
    vencidas..."). RESUELTA y BLOQUEADA son las dos decisiones posibles
    tras responder -- ambas son "cerrables", una incidencia bloqueada no
    es una incidencia sin resolver: es una decision explicita de no
    avanzar (Documento Maestro, seccion 4.7: "Bloquear documentos
    criticos...")."""

    ABIERTA = "abierta"
    ASIGNADA = "asignada"
    RESPONDIDA = "respondida"
    RESUELTA = "resuelta"
    BLOQUEADA = "bloqueada"
    CERRADA = "cerrada"


class Incidencia(BaseModel):
    """Entidad raiz del Modulo 10. Cada Incidencia vive en la base de
    un unico proyecto (proyecto.db, igual que Documento) y referencia un
    `documento_id` de ese mismo proyecto -- quien la crea
    (application.incidents.commands.registrar_incidencia.RegistrarIncidencia)
    valida que ese documento exista antes de registrarla."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proyecto_id: str
    documento_id: str
    etapa: EtapaIncidencia
    tipo: str
    """Categoria libre de la incidencia (por ejemplo, 'cifra_dudosa',
    'contenido_faltante', 'contradiccion') -- sin catalogo cerrado en
    esta version: la tabla de modulos (seccion 4.6) no define uno, a
    diferencia de `tipo_regla` en ReglaNormalizacion, que si tiene un
    motor que lo interpreta. Aqui es solo informativo/de reporte."""
    severidad: SeveridadIncidencia
    evidencia: str
    """Descripcion o cita textual de donde se detecto la incidencia
    (por ejemplo, un fragmento del Markdown o una referencia a una
    pagina del original) -- texto libre, sin adjuntos en esta version."""
    impacto: str
    responsable: Optional[str] = None
    """Fijado por `asignar()`; `None` hasta entonces."""
    estado: EstadoIncidencia = EstadoIncidencia.ABIERTA
    respuesta: Optional[str] = None
    """Fijado por `responder()`; `None` hasta entonces."""
    decision: Optional[str] = None
    """Fijado por `decidir()`; `None` hasta entonces."""
    cierre: Optional[str] = None
    """Fijado por `cerrar()`; `None` hasta entonces."""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("tipo")
    @classmethod
    def _tipo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El tipo de la incidencia no puede estar vacio")
        return v

    @field_validator("evidencia")
    @classmethod
    def _evidencia_no_vacia(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La evidencia de la incidencia no puede estar vacia -- sin evidencia no es verificable")
        return v

    def asignar(self, responsable: str) -> "Incidencia":
        """ABIERTA -> ASIGNADA. Fija el responsable de analizarla."""
        if self.estado != EstadoIncidencia.ABIERTA:
            raise InvalidIncidentStateTransitionError(self.estado.value, EstadoIncidencia.ASIGNADA.value)
        responsable = responsable.strip()
        if not responsable:
            raise ValueError("El responsable no puede estar vacio")
        data = self.model_dump()
        data["responsable"] = responsable
        data["estado"] = EstadoIncidencia.ASIGNADA
        data["updated_at"] = _utcnow()
        return Incidencia(**data)

    def responder(self, respuesta: str) -> "Incidencia":
        """ASIGNADA -> RESPONDIDA. Registra el analisis del responsable."""
        if self.estado != EstadoIncidencia.ASIGNADA:
            raise InvalidIncidentStateTransitionError(self.estado.value, EstadoIncidencia.RESPONDIDA.value)
        respuesta = respuesta.strip()
        if not respuesta:
            raise ValueError("La respuesta no puede estar vacia")
        data = self.model_dump()
        data["respuesta"] = respuesta
        data["estado"] = EstadoIncidencia.RESPONDIDA
        data["updated_at"] = _utcnow()
        return Incidencia(**data)

    def decidir(self, decision: str, resuelta: bool) -> "Incidencia":
        """RESPONDIDA -> RESUELTA (si `resuelta=True`) o BLOQUEADA (si
        `resuelta=False`). `decision` es el texto que justifica la
        salida elegida -- por ejemplo, "se corrige en la siguiente
        extraccion" (resuelta) o "vigencia desconocida, no se puede
        avanzar" (bloqueada)."""
        if self.estado != EstadoIncidencia.RESPONDIDA:
            raise InvalidIncidentStateTransitionError(self.estado.value, "resuelta_o_bloqueada")
        decision = decision.strip()
        if not decision:
            raise ValueError("La decision no puede estar vacia")
        data = self.model_dump()
        data["decision"] = decision
        data["estado"] = EstadoIncidencia.RESUELTA if resuelta else EstadoIncidencia.BLOQUEADA
        data["updated_at"] = _utcnow()
        return Incidencia(**data)

    def cerrar(self, cierre: str) -> "Incidencia":
        """RESUELTA o BLOQUEADA -> CERRADA. `cierre` es la nota final de
        cierre (Documento Maestro, seccion 4.6, campo "cierre")."""
        if self.estado not in (EstadoIncidencia.RESUELTA, EstadoIncidencia.BLOQUEADA):
            raise InvalidIncidentStateTransitionError(self.estado.value, EstadoIncidencia.CERRADA.value)
        cierre = cierre.strip()
        if not cierre:
            raise ValueError("El cierre no puede estar vacio")
        data = self.model_dump()
        data["cierre"] = cierre
        data["estado"] = EstadoIncidencia.CERRADA
        data["updated_at"] = _utcnow()
        return Incidencia(**data)

    def esta_abierta(self) -> bool:
        """True si la incidencia todavia no llego a CERRADA -- criterio
        usado por el reporte de incidencias (Documento Maestro, seccion
        7.1: "abiertas, cerradas") y por la regla de bloqueo de
        liberacion (seccion 8.2), aplicada por el Modulo 13."""
        return self.estado != EstadoIncidencia.CERRADA


def filtrar_criticas_abiertas(incidencias: list[Incidencia]) -> list[Incidencia]:
    """Subconjunto de `incidencias` con severidad CRITICA y todavia
    abiertas -- criterio exacto de la regla de bloqueo de liberacion
    (Documento Maestro, seccion 8.2: "Incidencias criticas abiertas:
    0"). Funcion pura, sin acceso a repositorio, para que el criterio
    se defina una sola vez y lo reutilicen tanto
    application.incidents.service.IncidentsService.existen_criticas_abiertas()
    como application.governance.verificar_documento_aprobable
    (Modulo 13) sin duplicarlo ni arriesgar que se desincronicen."""
    return [i for i in incidencias if i.severidad == SeveridadIncidencia.CRITICA and i.esta_abierta()]
