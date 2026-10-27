"""Entidades del contexto Proyectos (ADR-001, seccion 5).

Formuladas de forma generica: ningun campo propio de un tipo de agente
(por ejemplo "plantel" o "expediente clinico") aparece aqui. Esos campos
viven como valores dentro de un perfil (domain.profiles.entities.
PerfilProyecto.campos_metadato), nunca como atributos fijos de Proyecto --
mismo principio que MetadataSchema/FieldDefinition en RAG STUDIO (ver
ADR-001, seccion 5). El perfil se movio a su propio contexto acotado
(domain/profiles/) porque el Modulo 2 (administrador de perfiles) lo
trata como una entidad de primera clase con su propio ciclo de vida
(version, publicacion, comparacion), no como un detalle interno de
Proyecto.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from .exceptions import ProjectAlreadyArchivedError

_ID_PATTERN = re.compile(r"^PROY-\d{4}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NivelConfidencialidad(str, Enum):
    """Mismo catalogo que access_level en RAG STUDIO (Documento Maestro,
    seccion 4.6.1): publico / interno / confidencial / restringido."""

    PUBLICO = "publico"
    INTERNO = "interno"
    CONFIDENCIAL = "confidencial"
    RESTRINGIDO = "restringido"


class EstadoProyecto(str, Enum):
    ACTIVO = "activo"
    ARCHIVADO = "archivado"


class Proyecto(BaseModel):
    """Raiz de todo lo demas (ADR-001, seccion 5). Vive en su propia
    carpeta bajo /proyectos/ (Documento Maestro, seccion 4.5); esta
    entidad es el registro en la base global (aplicacion.db), no la
    carpeta en si (ver infrastructure.filesystem.project_structure)."""

    id: str = Field(default_factory=lambda: f"PROY-{uuid.uuid4().int % 10000:04d}")
    nombre: str
    perfil_id: str
    objetivo: str = ""
    usuarios_objetivo: list[str] = Field(default_factory=list)
    alcance: str = ""
    jurisdiccion: str = ""
    idioma: str = "es"
    confidencialidad: NivelConfidencialidad = NivelConfidencialidad.INTERNO
    responsables: list[str] = Field(default_factory=list)
    estado: EstadoProyecto = EstadoProyecto.ACTIVO
    ruta_carpeta: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("id")
    @classmethod
    def _id_formato_valido(cls, v: str) -> str:
        if not _ID_PATTERN.match(v):
            raise ValueError(f"El id de proyecto debe seguir el formato PROY-0000, recibido: {v!r}")
        return v

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre del proyecto no puede estar vacio")
        return v

    def archivar(self) -> "Proyecto":
        """Auditoria 2026-09-02 (hallazgo real del consultor,
        RAG_CONTENT_01: "tratamiento a proyecto que no proceden, como
        eliminarlos" -- ver evidencias pruebas): antes de esto
        `EstadoProyecto.ARCHIVADO` existia en el enum y en
        `ProjectRepository.list(incluir_archivados=...)`, pero ningun
        caso de uso ni la interfaz sabian llegar a el -- un proyecto
        creado por error, de prueba, o que simplemente ya no procede se
        quedaba para siempre en la lista de proyectos activos, sin
        forma de sacarlo de en medio. Archivar es la operacion segura y
        siempre disponible (a diferencia de `EliminarProyecto`, que
        exige que el proyecto no tenga documentos registrados): no
        borra nada, solo dejar de mostrarlo en el selector de "abrir
        proyecto" -- reversible por quien administre la base
        directamente si hiciera falta, mismo principio de "no
        sobrescribir/perder trabajo real" que rige el resto del
        dominio (Documento Maestro, seccion 4.1)."""
        if self.estado == EstadoProyecto.ARCHIVADO:
            raise ProjectAlreadyArchivedError(self.id)
        data = self.model_dump()
        data["estado"] = EstadoProyecto.ARCHIVADO
        data["updated_at"] = _utcnow()
        return Proyecto(**data)

    def carpeta_normalizada(self) -> str:
        """Nombre de carpeta segun el Documento Maestro, seccion 4.5:
        PROY-0001_nombre_proyecto. No decide la ruta raiz -- eso es
        responsabilidad de infrastructure.filesystem (Documento Maestro,
        seccion 4.1: ruta raiz unica).

        Bug encontrado en verificacion real contra /proyectos (2026-07-29):
        sin la normalizacion Unicode de abajo, letras acentuadas (comunes
        en nombres de proyecto en espanol: "Area", "Configuracion",
        "Ano") no caian en [a-zA-Z0-9] ni en el separador -- quedaban
        eliminadas en silencio en vez de conservar la letra base, dejando
        carpetas con nombres corrompidos (ej. "Area Legal" -> "rea_legal",
        perdiendo la "A"). NFKD + encode/decode ascii separa cada letra
        acentuada en su base ASCII (a, e, i, o, u, n...) mas un signo
        diacritico aparte, y el encode lo descarta -- asi "Area" queda
        "area" en vez de "rea". Cubierto por
        test_crear_proyecto_extremo_a_extremo.py."""
        nombre_ascii = unicodedata.normalize("NFKD", self.nombre.strip().lower())
        nombre_ascii = nombre_ascii.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", nombre_ascii).strip("_")
        return f"{self.id}_{slug}"
