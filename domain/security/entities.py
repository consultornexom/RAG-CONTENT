"""Entidades del contexto Seguridad (Fase 10 del orden aprobado
2026-07-28; Documento Maestro, seccion 9 "Riesgos, restricciones y
cumplimiento" -- plan de mitigacion: "Respaldos cifrados y pruebas de
restauracion"; ADR-001, seccion 14.3 "Politica de seguridad").

Como el resto de contextos de esta capa (`domain.reports`,
`domain.acceptance`, `domain.batches`...), `domain.security` no importa
ningun otro paquete `domain.*` -- mismo aislamiento estricto. Las dos
clases de aqui son value objects puros que describen un HECHO ya
ocurrido (un respaldo creado, una restauracion intentada), sin logica de
negocio propia -- misma filosofia que `domain.reports.entities.
ActaCierreLote`.

Nota sobre "niveles de acceso" (ADR-001, seccion 14.3, fila "Niveles de
acceso"): ese catalogo (publico/interno/confidencial/restringido) ya
existe como `domain.projects.entities.NivelConfidencialidad` desde la
Fase 1 -- no se duplica aqui. `domain.security` no importa
`domain.projects` (aislamiento entre contextos); es `application.security`
quien recibe el `proyecto_id`/carpeta ya resueltos por quien lo llame,
igual que `application.reports`/`application.acceptance` reciben sus
identificadores sin importar `domain.projects` tampoco."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RespaldoProyecto(BaseModel):
    """Un respaldo cifrado ya creado con exito (Documento Maestro,
    seccion 9: "Respaldos cifrados..."). `hash_sha256` es el hash del
    archivo CIFRADO tal como quedo en `13_respaldos/` -- permite
    verificar despues que el archivo no se corrompio ni fue alterado,
    sin necesitar la clave de cifrado para esa verificacion (mismo
    principio de integridad por hash que `domain.documents.entities.
    Documento.hash_sha256`, aplicado aqui al respaldo completo en vez de
    a un documento individual)."""

    proyecto_id: str
    ruta_archivo: str
    hash_sha256: str
    tamano_bytes: int
    fecha: str = Field(default_factory=_utcnow_iso)


class RestauracionRespaldo(BaseModel):
    """Resultado de una "prueba de restauracion" (Documento Maestro,
    seccion 9: "...y pruebas de restauracion" no es un adjetivo suelto:
    un respaldo que nunca se probo restaurar no esta realmente
    verificado, solo se asume integro por existir). `exitosa=False` es un
    resultado ESPERADO y valido (clave incorrecta, archivo corrupto o
    alterado) -- no una excepcion de programacion; mismo criterio de
    "pendiente/fallido no es lo mismo que error de codigo" que
    `domain.acceptance.entities.CriterioDominio`."""

    ruta_archivo: str
    ruta_destino: str
    exitosa: bool
    detalle: str = ""
    fecha: str = Field(default_factory=_utcnow_iso)
