"""Entidades del contexto Lotes (Fase 7 del orden aprobado 2026-07-28;
Documento Maestro seccion 4.10, entidad "Lote" del modelo de datos
minimo: "un Proyecto contiene Lotes y Documentos"; seccion 10.1, "Flujo
operativo completo por lote", etapa 14: "Liberar aprobados, bloquear
pendientes, firmar acta y exportar" -> "Lote cerrado").

`domain.batches` no importa `domain.documents` en absoluto -- mismo
aislamiento estricto que el resto de contextos (`domain.incidents`,
`domain.validity`, `domain.governance`, `domain.jobs`). La relacion
Lote-Documento vive del lado de `Documento` (campo `lote_id`, ver
`domain.documents.entities.Documento.asignar_a_lote()`), no como una
lista de ids dentro de `Lote` -- mismo criterio de "referencia por id
plano, sin coleccion embebida" que ya usa `Incidencia.documento_id` en
sentido inverso."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .exceptions import InvalidBatchStateTransitionError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EstadoLote(str, Enum):
    """Un lote no tiene un flujo de etapas propio (esas ya las modela
    `EstadoDocumento` para cada documento que contiene) -- solo si sigue
    abierto para seguir agregando documentos, o si ya se cerro
    (Documento Maestro, seccion 10.1, etapa 14)."""

    ABIERTO = "abierto"
    CERRADO = "cerrado"


_TRANSICIONES: dict[EstadoLote, frozenset[EstadoLote]] = {
    EstadoLote.ABIERTO: frozenset({EstadoLote.CERRADO}),
    EstadoLote.CERRADO: frozenset(),
}
"""CERRADO es terminal -- no existe hoy un caso de uso para reabrir un
lote ya cerrado (Documento Maestro, seccion 10.1: cerrar un lote ya
libero lo aprobado y bloqueo lo pendiente; reabrirlo no tiene un
significado operativo claro sin una decision de negocio nueva que este
documento no describe)."""


class Lote(BaseModel):
    """Entidad "Lote" del modelo de datos minimo (Documento Maestro,
    seccion 4.10). Vive en la base de un unico proyecto (proyecto.db),
    igual que `Documento`."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proyecto_id: str
    nombre: str
    estado: EstadoLote = EstadoLote.ABIERTO
    creado_en: datetime = Field(default_factory=_utcnow)
    actualizado_en: datetime = Field(default_factory=_utcnow)
    cerrado_en: Optional[datetime] = None

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre del lote no puede estar vacio")
        return v

    def cerrar(self) -> "Lote":
        """ABIERTO -> CERRADO. Quien llama
        (application.batches.commands.cerrar_lote.CerrarLote) debe
        haber resuelto antes el estado de cada documento del lote
        (liberar los aprobados, bloquear los pendientes) -- este metodo
        solo mueve el estado del propio Lote, mismo reparto de
        responsabilidades que `Documento.liberar()` con
        `GovernanceService`."""
        target = EstadoLote.CERRADO
        permitidos = _TRANSICIONES[self.estado]
        if target not in permitidos:
            raise InvalidBatchStateTransitionError(self.estado.value, target.value)
        data = self.model_dump()
        data["estado"] = target
        data["actualizado_en"] = _utcnow()
        data["cerrado_en"] = _utcnow()
        return Lote(**data)
