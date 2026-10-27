"""Modelos SQLAlchemy para la base por proyecto (proyecto.db).

`BaseProyecto` es una jerarquia declarativa separada de `Base`
(infrastructure.database.models, usada por aplicacion.db) a proposito:
si compartieran la misma `DeclarativeBase`, `metadata.create_all()`
crearia tambien las tablas de proyectos/perfiles/auditoria global dentro
de cada proyecto.db, mezclando los dos esquemas que el ADR-001 (seccion
9) exige mantener independientes.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import UTCDateTime


class BaseProyecto(DeclarativeBase):
    pass


class DocumentoModel(BaseProyecto):
    __tablename__ = "documentos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proyecto_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    nombre_original: Mapped[str] = mapped_column(Text, nullable=False)
    formato: Mapped[str] = mapped_column(String(20), nullable=False)
    ruta_origen: Mapped[str] = mapped_column(Text, nullable=False)
    ruta_copia_original: Mapped[str] = mapped_column(Text, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    prioridad: Mapped[str] = mapped_column(String(20), nullable=False)
    criticidad: Mapped[str] = mapped_column(String(20), nullable=False)
    metadatos_json: Mapped[str] = mapped_column(Text, default="{}")
    tipo_procesamiento: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    """Modulo 4 (clasificacion). Nulo hasta que el documento se
    clasifica -- ver domain.documents.entities.Documento.clasificar()."""
    ruta_extraccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Modulo 5 (extraccion). Nulo hasta que se completa la extraccion
    -- ver Documento.completar_extraccion()."""
    advertencias_extraccion_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    mapa_paginas_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    """Modulo 8 (navegacion sincronizada real). Lista de desplazamientos
    en caracteres, uno por pagina del original, dentro del Markdown de
    ruta_extraccion -- solo lo llenan PdfExtractor/PdfOcrExtractor (ver
    Documento.mapa_paginas)."""
    rangos_baja_confianza_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    """Modulo 8 (agregado 2026-08-01). Lista de objetos
    {inicio, fin, confianza, texto} -- tramos del Markdown de
    ruta_extraccion que Tesseract reconocio con baja confianza, solo
    lo llenan PdfOcrExtractor/ImageOcrExtractor (ver
    Documento.rangos_baja_confianza)."""
    ruta_revisado: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Modulo 8 (correccion). Nulo hasta que el revisor guarda una
    correccion humana del Markdown extraido -- ver Documento.corregir()."""
    ruta_normalizado: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Modulo 9 (normalizacion). Nulo hasta que se completa la
    normalizacion -- ver Documento.completar_normalizacion()."""
    cambios_normalizacion_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ruta_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Modulo 12 (Generador de Markdown). Nulo hasta MARKDOWN_GENERADO
    -- ver Documento.generar_markdown()."""
    hash_markdown: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    advertencias_markdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    lote_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    """Fase 7 (Lotes). Nulo si el documento todavia no se agrego a
    ningun lote -- ver Documento.asignar_a_lote()/quitar_de_lote()."""
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class RevisionModel(BaseProyecto):
    """Historial de revisiones humanas (Modulo 8, ADR-001 seccion 5) --
    a diferencia de 'documentos', cada fila es un registro inmutable
    nuevo (RevisionRepository.save() nunca actualiza una fila
    existente, solo inserta) -- ver domain.documents.entities.Revision
    y domain.documents.ports.RevisionRepository."""

    __tablename__ = "revisiones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    documento_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revisor: Mapped[str] = mapped_column(Text, nullable=False)
    comentario: Mapped[str] = mapped_column(Text, nullable=False, default="")
    incidencias_detectadas_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    fecha: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class AprobacionModel(BaseProyecto):
    """Historial de aprobaciones para generar Markdown (Modulo 12/13,
    ADR-001 seccion 5) -- mismo criterio que RevisionModel: cada fila es
    un registro inmutable nuevo (AprobacionRepository.save() nunca
    actualiza una fila existente, solo inserta) -- ver
    domain.documents.entities.Aprobacion y
    domain.documents.ports.AprobacionRepository."""

    __tablename__ = "aprobaciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    documento_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    aprobador: Mapped[str] = mapped_column(Text, nullable=False)
    comentario: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fecha: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class IncidenciaModel(BaseProyecto):
    """Modulo 10 (gestion de incidencias) -- tabla propia dentro de
    proyecto.db, separada de 'documentos' (una incidencia referencia un
    documento por id, sin clave foranea declarada: mismo criterio ya
    usado entre documentos y proyectos, sin FK entre bases distintas ni
    entre tablas de este proyecto)."""

    __tablename__ = "incidencias"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proyecto_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    documento_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    etapa: Mapped[str] = mapped_column(String(30), nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False)
    evidencia: Mapped[str] = mapped_column(Text, nullable=False)
    impacto: Mapped[str] = mapped_column(Text, nullable=False)
    responsable: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    respuesta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cierre: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class FuenteModel(BaseProyecto):
    """Modulo 11 (Vigencias y fuentes) -- a lo sumo una fila por
    documento (ver domain.validity.entities.Fuente): `documento_id` es
    la clave primaria en si, sin un `id` sintetico adicional (a
    diferencia de 'incidencias'/'revisiones', que si acumulan varias
    filas por documento)."""

    __tablename__ = "fuentes"

    documento_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sistema_origen: Mapped[str] = mapped_column(Text, nullable=False)
    autoridad: Mapped[str] = mapped_column(Text, nullable=False)
    evidencia_consulta: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class TrabajoModel(BaseProyecto):
    """Fase 6 (Colas de trabajo y workers aislados) -- entidad
    'TrabajoProcesamiento' del modelo de datos minimo (Documento
    Maestro, seccion 4.10). Mismo criterio de clave primaria que
    DocumentoModel (un `id` sintetico propio: a diferencia de
    FuenteModel/VigenciaModel, un documento puede tener varios trabajos
    a lo largo de su vida, incluso varios a la vez de tipos distintos).
    `estado` e `documento_id` llevan indice porque
    SqlAlchemyTrabajoRepository los filtra directamente
    (list_by_estado/list_by_document/list_pendientes_por_prioridad) --
    ver domain.jobs.ports.TrabajoRepository."""

    __tablename__ = "trabajos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proyecto_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    documento_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    prioridad: Mapped[str] = mapped_column(String(20), nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    mensaje_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    iniciado_en: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    finalizado_en: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


class LoteModel(BaseProyecto):
    """Fase 7 (Lotes) -- entidad 'Lote' del modelo de datos minimo
    (Documento Maestro, seccion 4.10). La relacion con 'documentos' vive
    del lado de DocumentoModel.lote_id (ver mas arriba), no aqui -- este
    modelo no tiene ninguna columna de coleccion."""

    __tablename__ = "lotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proyecto_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    cerrado_en: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


class VigenciaModel(BaseProyecto):
    """Modulo 11 (Vigencias y fuentes) -- mismo criterio de clave
    primaria que FuenteModel (ver domain.validity.entities.Vigencia).
    `sin_vencimiento` distingue "vigente sin fecha de vencimiento
    conocida" de "vigencia desconocida" (ver
    domain.validity.entities.vigencia_desconocida)."""

    __tablename__ = "vigencias"

    documento_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fecha_emision: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    vigente_desde: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sin_vencimiento: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    autoridad: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sustituye_a: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
