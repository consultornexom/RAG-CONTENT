"""Entidades del contexto Perfiles (ADR-001, seccion 5 y Anexo B del
Documento Maestro: "Primer perfil de proyecto"). Un perfil es un paquete
portable (YAML) que enriquece el nucleo comun sin modificarlo -- principio
de diseno no negociable "nucleo comun + perfil configurable".

Patron tomado de RAG STUDIO (domain/metadata/entities.py: FieldDataType,
MetadataSchema, FieldDefinition, Catalog, CatalogEntry) pero adaptado: en
RAG STUDIO estos objetos viven en un esquema de base de datos activo; aqui
son objetos de valor incrustados dentro de un paquete YAML versionado e
inmutable (Documento Maestro, seccion 4.3: los perfiles se versionan, no
se sobrescriben).
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum

from .exceptions import VersionDePerfilInvalidaError

_FIELD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")


def clave_version(version: str) -> tuple[int, int]:
    """Convierte una version 'N.N' en una clave de comparacion semantica
    (no alfabetica -- '0.10' es posterior a '0.9'), usada para ordenar
    versiones de perfil (`YamlProfileRepository.list_versions()`) y para
    decidir si una version nueva es posterior a la vigente
    (`PublicarNuevaVersionPerfil`). Unico lugar que hace esta conversion
    (hallazgo real de la cuarta auditoria general, 2026-08-01: antes
    estaba duplicada en application e infrastructure, cada una con su
    propio `ValueError` nativo sin traducir ante un formato invalido).
    Lanza `VersionDePerfilInvalidaError` (no un `ValueError` crudo de
    Python) si `version` no sigue el formato 'N.N' -- mismo patron
    `_VERSION_PATTERN` que ya valida `PerfilProyecto.version` al
    construir el objeto, reutilizado aqui para el caso en que la version
    llega como texto plano desde un nombre de archivo, sin pasar por esa
    validacion de Pydantic."""
    if not _VERSION_PATTERN.match(version):
        raise VersionDePerfilInvalidaError(version)
    mayor, menor = version.split(".")
    return (int(mayor), int(menor))


class TipoDato(str, Enum):
    """Tipos de dato admitidos para un campo de metadato de perfil."""

    TEXTO = "texto"
    TEXTO_LARGO = "texto_largo"
    NUMERO = "numero"
    FECHA = "fecha"
    BOOLEANO = "booleano"
    CATALOGO = "catalogo"
    CATALOGO_MULTIPLE = "catalogo_multiple"


CATALOGO_TIPOS = {TipoDato.CATALOGO, TipoDato.CATALOGO_MULTIPLE}


class EntradaCatalogo(BaseModel):
    """Un valor permitido dentro de un catalogo cerrado del perfil."""

    codigo: str
    etiqueta: str
    entrada_padre: Optional[str] = None

    @field_validator("codigo")
    @classmethod
    def _codigo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El codigo de la entrada de catalogo no puede estar vacio")
        return v


class Catalogo(BaseModel):
    """Catalogo cerrado incrustado en el paquete de perfil (por ejemplo,
    areas propietarias, jurisdicciones o tipos documentales admitidos).
    """

    nombre: str
    entradas: list[EntradaCatalogo] = Field(default_factory=list)

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre del catalogo no puede estar vacio")
        return v

    def contiene(self, codigo: str) -> bool:
        return any(e.codigo == codigo for e in self.entradas)


class ReglaValidacion(BaseModel):
    """Regla adicional de validacion aplicable a un campo de metadato
    (por ejemplo, expresion regular, rango numerico o fecha maxima).
    Los parametros son de texto libre para mantener el paquete de perfil
    serializable sin depender de tipos de dominio en el YAML.
    """

    field_id: str
    tipo_regla: str
    parametros: dict[str, str] = Field(default_factory=dict)


class ReglaNormalizacion(BaseModel):
    """Regla de normalizacion aplicable al Markdown ya extraido/revisado
    de un documento (Modulo 9, Documento Maestro seccion 4.6: "Aplicar
    reglas sin alterar silenciosamente"). Mismo criterio que
    ReglaValidacion: parametros de texto libre, sin tipos de dominio en
    el YAML, para que el paquete de perfil siga siendo serializable e
    inmutable por version.

    A diferencia de ReglaValidacion (que vive dentro del contexto
    Perfiles y se aplica solo a metadatos), esta regla la consume
    domain.documents.ports.NormalizationEngine (contexto Documentos) --
    primera referencia cruzada deliberada entre ambos contextos
    acotados: los perfiles son quienes definen las reglas ("reglas en
    YAML por perfil", ADR-001 seccion 8), pero quien las ejecuta es el
    Modulo 9 sobre el documento. Ver domain.documents.ports.
    NormalizationEngine.normalizar() para el catalogo de tipo_regla
    reconocidos."""

    tipo_regla: str
    parametros: dict[str, str] = Field(default_factory=dict)


class CampoMetadato(BaseModel):
    """Definicion de un campo de metadato requerido u opcional por el
    perfil (Documento Maestro, seccion 4.3: "metadatos obligatorios por
    tipo de proyecto"). Sustituye a la lista plana `metadatos_requeridos`
    de la version inicial del nucleo.
    """

    field_id: str
    nombre_visible: str
    tipo_dato: TipoDato
    obligatorio: bool = True
    heredado_a_markdown: bool = True
    catalogo: Optional[str] = None
    descripcion: str = ""

    @field_validator("field_id")
    @classmethod
    def _field_id_formato_valido(cls, v: str) -> str:
        if not _FIELD_ID_PATTERN.match(v):
            raise ValueError(
                f"field_id debe ser snake_case (ej. 'area_propietaria'), recibido: {v!r}"
            )
        return v

    @field_validator("nombre_visible")
    @classmethod
    def _nombre_visible_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre visible del campo no puede estar vacio")
        return v

    @model_validator(mode="after")
    def _catalogo_requerido_si_tipo_catalogo(self) -> "CampoMetadato":
        if self.tipo_dato in CATALOGO_TIPOS and not self.catalogo:
            raise ValueError(
                f"El campo '{self.field_id}' es de tipo {self.tipo_dato.value}: "
                "debe declarar el nombre del catalogo del que toma sus valores"
            )
        return self


class PerfilProyecto(BaseModel):
    """Paquete de perfil versionado e inmutable. Cada version publicada
    se almacena en `perfiles/<id>/<version>.yaml` y nunca se sobrescribe
    (Documento Maestro, seccion 4.3; ADR-001, seccion 8: "paquetes
    firmables").
    """

    id: str
    version: str
    descripcion: str = ""
    campos_metadato: list[CampoMetadato] = Field(default_factory=list)
    catalogos: list[Catalogo] = Field(default_factory=list)
    reglas_validacion: list[ReglaValidacion] = Field(default_factory=list)
    reglas_normalizacion: list[ReglaNormalizacion] = Field(default_factory=list)
    tipos_documentales_criticos: list[str] = Field(default_factory=list)
    plantilla_markdown: Optional[str] = None
    incidencias_criticas_permitidas: int = 0
    revision_obligatoria: bool = True
    confirmacion_vigencia_obligatoria: bool = True

    @field_validator("id")
    @classmethod
    def _id_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El id del perfil no puede estar vacio")
        return v

    @field_validator("version")
    @classmethod
    def _version_formato_valido(cls, v: str) -> str:
        if not _VERSION_PATTERN.match(v):
            raise ValueError(f"La version del perfil debe seguir el formato 'N.N', recibido: {v!r}")
        return v

    @model_validator(mode="after")
    def _catalogos_referenciados_existen(self) -> "PerfilProyecto":
        nombres_catalogo = {c.nombre for c in self.catalogos}
        for campo in self.campos_metadato:
            if campo.catalogo and campo.catalogo not in nombres_catalogo:
                raise ValueError(
                    f"El campo '{campo.field_id}' referencia el catalogo "
                    f"'{campo.catalogo}', que no esta definido en el perfil"
                )
        for regla in self.reglas_validacion:
            field_ids = {c.field_id for c in self.campos_metadato}
            if regla.field_id not in field_ids:
                raise ValueError(
                    f"La regla de validacion referencia field_id '{regla.field_id}', "
                    "que no existe en campos_metadato"
                )
        return self

    def campos_obligatorios(self) -> list[CampoMetadato]:
        return [c for c in self.campos_metadato if c.obligatorio]

    def firma_sha256(self) -> str:
        """Huella del paquete de perfil para el requisito de "paquetes
        firmables" (ADR-001, seccion 8). No es una firma criptografica de
        clave publica -- es un hash de integridad del contenido
        canonico, suficiente para detectar cualquier alteracion del
        paquete YAML publicado.
        """
        canonico = self.model_dump_json(exclude_none=False)
        return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
