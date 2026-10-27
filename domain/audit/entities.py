"""Entidad EventoAuditoria (Documento Maestro, secciones 4.1 y 4.10).

No modificable desde la interfaz ordinaria: esta clase no expone ningun
metodo de edicion a proposito -- un evento de auditoria se crea una vez
y no se actualiza nunca.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventoAuditoria(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proyecto_id: Optional[str] = None
    accion: str
    valor_anterior: Optional[str] = None
    valor_nuevo: Optional[str] = None
    motivo: str
    fecha: datetime = Field(default_factory=_utcnow)
