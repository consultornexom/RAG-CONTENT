"""Entidades del contexto Vigencias y fuentes (Modulo 11).

Cada documento tiene a lo sumo una Fuente y a lo sumo una Vigencia --a
diferencia de Incidencia/Revision, que acumulan varios registros por
documento-- asi que `documento_id` es la clave natural de ambas, sin un
`id` sintetico adicional (ver domain.validity.ports y los adaptadores
de infrastructure, que usan `documento_id` como clave primaria de sus
tablas).

Igual que domain.incidents, este contexto no importa domain.documents:
la validacion de que el documento referenciado exista antes de
registrar una Fuente/Vigencia vive en application (ver
application.validity.commands), mismo patron ya usado por
RegistrarIncidencia con DocumentRepository.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Fuente(BaseModel):
    """Modulo 11 (ADR-001, seccion 5): "documento_id, sistema/area de
    origen, autoridad, evidencia de consulta". Responde de donde viene
    el documento y quien lo emite -- no dice nada sobre si sigue
    vigente (eso es responsabilidad exclusiva de `Vigencia`, a
    proposito: "no deben confundirse")."""

    documento_id: str
    sistema_origen: str
    """Sistema, area o repositorio de origen del documento (por
    ejemplo, "portal de normatividad interna", "SharePoint de RH") --
    texto libre: el Documento Maestro no define un catalogo cerrado
    para este campo."""
    autoridad: str
    """Quien emite o autoriza formalmente el documento."""
    evidencia_consulta: str
    """Como y donde se verifico la fuente (por ejemplo, una URL, una
    referencia de expediente, o una nota de "confirmado con..." ) --
    sin evidencia, la fuente no es verificable."""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("sistema_origen", "autoridad", "evidencia_consulta")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Los campos de la fuente no pueden estar vacios")
        return v

    def actualizar(self, sistema_origen: str, autoridad: str, evidencia_consulta: str) -> "Fuente":
        """Reemplaza los tres campos de contenido -- se usa cuando ya
        existia una Fuente para este documento y el operador confirma
        o corrige los datos (Documento Maestro, seccion 4.11: paso 9,
        "confirmar propietario, version, vigencia y evidencia")."""
        data = self.model_dump()
        data["sistema_origen"] = sistema_origen
        data["autoridad"] = autoridad
        data["evidencia_consulta"] = evidencia_consulta
        data["updated_at"] = _utcnow()
        return Fuente(**data)


class Vigencia(BaseModel):
    """Modulo 11 (ADR-001, seccion 5): "documento_id, emision,
    vigente_desde/hasta, autoridad, sustituye_a". A diferencia de
    Fuente, los campos de Vigencia se dejan deliberadamente sin
    validadores de "no vacio": el flujo real es confirmarla
    progresivamente (puede registrarse solo parcialmente conocida y
    completarse despues), y la funcion `vigencia_desconocida()` de mas
    abajo es justamente el criterio que distingue "todavia incompleta"
    de "ya lista"."""

    documento_id: str
    fecha_emision: Optional[date] = None
    vigente_desde: Optional[date] = None
    vigente_hasta: Optional[date] = None
    """`None` puede significar dos cosas muy distintas: "vigente sin
    fecha de vencimiento, hasta nueva disposicion" (legitimo) o
    "todavia no se investigo" (vigencia desconocida). `sin_vencimiento`
    distingue explicitamente la primera de la segunda -- sin este
    campo, el Modulo 13 (segunda regla, bloqueo por vigencia
    desconocida) no podria diferenciarlas sin arriesgarse a bloquear un
    documento legitimamente vigente."""
    sin_vencimiento: bool = False
    autoridad: str = ""
    sustituye_a: Optional[str] = None
    """documento_id de un documento anterior que este sustituye, si
    aplica (Documento Maestro, seccion 4.6, fila 11: "sustituciones").
    Sin validar contra el inventario aqui en domain -- lo valida
    application, igual que documento_id (ver
    application.validity.commands.registrar_vigencia)."""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def esta_completa(self) -> bool:
        """True si hay suficiente informacion para considerar la
        vigencia "conocida": se sabe desde cuando es valida, quien la
        autoriza, y -- si no es de vigencia indefinida -- hasta
        cuando."""
        return (
            bool(self.vigente_desde)
            and bool(self.autoridad.strip())
            and (self.sin_vencimiento or self.vigente_hasta is not None)
        )

    def esta_vigente_en(self, fecha: date) -> bool:
        """True si `fecha` cae dentro de la ventana de vigencia
        registrada. No tiene sentido llamarlo si `esta_completa()` es
        False -- una vigencia incompleta no permite responder esta
        pregunta con certeza, pero el metodo no lo impide (deteccion,
        no bloqueo: eso es responsabilidad de quien lo llama)."""
        if self.vigente_desde is not None and fecha < self.vigente_desde:
            return False
        if not self.sin_vencimiento and self.vigente_hasta is not None and fecha > self.vigente_hasta:
            return False
        return True

    def actualizar(
        self,
        fecha_emision: Optional[date],
        vigente_desde: Optional[date],
        vigente_hasta: Optional[date],
        sin_vencimiento: bool,
        autoridad: str,
        sustituye_a: Optional[str],
    ) -> "Vigencia":
        data = self.model_dump()
        data["fecha_emision"] = fecha_emision
        data["vigente_desde"] = vigente_desde
        data["vigente_hasta"] = vigente_hasta
        data["sin_vencimiento"] = sin_vencimiento
        data["autoridad"] = autoridad
        data["sustituye_a"] = sustituye_a
        data["updated_at"] = _utcnow()
        return Vigencia(**data)


def vigencia_desconocida(vigencia: Optional[Vigencia]) -> bool:
    """True si `vigencia` es None (nunca se registro) o esta
    incompleta -- criterio exacto que el Modulo 13 (segunda regla,
    Documento Maestro secciones 4.7 y 8.2: "Documentos criticos con
    vigencia desconocida: 0") necesita para bloquear. Funcion pura, sin
    acceso a repositorio, mismo principio que
    domain.incidents.entities.filtrar_criticas_abiertas()."""
    return vigencia is None or not vigencia.esta_completa()
