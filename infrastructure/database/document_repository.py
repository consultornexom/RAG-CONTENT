"""Adaptador de DocumentRepository sobre SQLAlchemy sobre proyecto.db
(ADR-001, seccion 4). domain.documents.ports.DocumentRepository no sabe
que existe SQLAlchemy; esta clase es la unica que lo importa.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.documents.entities import (
    Criticidad,
    Documento,
    EstadoDocumento,
    FormatoDocumento,
    Prioridad,
    TipoProcesamiento,
)
from domain.documents.ocr_table_reconstruction import RangoBajaConfianza
from domain.documents.ports import DocumentRepository

from .project_models import DocumentoModel


def _to_entity(row: DocumentoModel) -> Documento:
    return Documento(
        id=row.id,
        proyecto_id=row.proyecto_id,
        nombre_original=row.nombre_original,
        formato=FormatoDocumento(row.formato),
        ruta_origen=row.ruta_origen,
        ruta_copia_original=row.ruta_copia_original,
        hash_sha256=row.hash_sha256,
        tamano_bytes=row.tamano_bytes,
        estado=EstadoDocumento(row.estado),
        prioridad=Prioridad(row.prioridad),
        criticidad=Criticidad(row.criticidad),
        metadatos=json.loads(row.metadatos_json),
        tipo_procesamiento=TipoProcesamiento(row.tipo_procesamiento) if row.tipo_procesamiento else None,
        ruta_extraccion=row.ruta_extraccion,
        advertencias_extraccion=json.loads(row.advertencias_extraccion_json),
        mapa_paginas=json.loads(row.mapa_paginas_json),
        rangos_baja_confianza=[RangoBajaConfianza(**r) for r in json.loads(row.rangos_baja_confianza_json)],
        ruta_revisado=row.ruta_revisado,
        ruta_normalizado=row.ruta_normalizado,
        cambios_normalizacion=json.loads(row.cambios_normalizacion_json),
        ruta_markdown=row.ruta_markdown,
        hash_markdown=row.hash_markdown,
        advertencias_markdown=json.loads(row.advertencias_markdown_json),
        lote_id=row.lote_id,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_row(documento: Documento, existing: Optional[DocumentoModel] = None) -> DocumentoModel:
    row = existing or DocumentoModel(id=documento.id)
    row.proyecto_id = documento.proyecto_id
    row.nombre_original = documento.nombre_original
    row.formato = documento.formato.value
    row.ruta_origen = documento.ruta_origen
    row.ruta_copia_original = documento.ruta_copia_original
    row.hash_sha256 = documento.hash_sha256
    row.tamano_bytes = documento.tamano_bytes
    row.estado = documento.estado.value
    row.prioridad = documento.prioridad.value
    row.criticidad = documento.criticidad.value
    row.metadatos_json = json.dumps(documento.metadatos, ensure_ascii=False)
    row.tipo_procesamiento = documento.tipo_procesamiento.value if documento.tipo_procesamiento else None
    row.ruta_extraccion = documento.ruta_extraccion
    row.advertencias_extraccion_json = json.dumps(documento.advertencias_extraccion, ensure_ascii=False)
    row.mapa_paginas_json = json.dumps(documento.mapa_paginas, ensure_ascii=False)
    row.rangos_baja_confianza_json = json.dumps(
        [r.model_dump() for r in documento.rangos_baja_confianza], ensure_ascii=False
    )
    row.ruta_revisado = documento.ruta_revisado
    row.ruta_normalizado = documento.ruta_normalizado
    row.cambios_normalizacion_json = json.dumps(documento.cambios_normalizacion, ensure_ascii=False)
    row.ruta_markdown = documento.ruta_markdown
    row.hash_markdown = documento.hash_markdown
    row.advertencias_markdown_json = json.dumps(documento.advertencias_markdown, ensure_ascii=False)
    row.lote_id = documento.lote_id
    row.version = documento.version
    row.created_at = documento.created_at
    row.updated_at = documento.updated_at
    return row


class SqlAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, documento: Documento) -> None:
        existing = self._session.get(DocumentoModel, documento.id)
        row = _to_row(documento, existing)
        if existing is None:
            self._session.add(row)
        self._session.commit()

    def get(self, documento_id: str) -> Optional[Documento]:
        row = self._session.get(DocumentoModel, documento_id)
        return _to_entity(row) if row else None

    def get_by_hash(self, hash_sha256: str) -> Optional[Documento]:
        stmt = select(DocumentoModel).where(DocumentoModel.hash_sha256 == hash_sha256)
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_entity(row) if row else None

    def list_by_estado(self, estado: EstadoDocumento) -> list[Documento]:
        stmt = select(DocumentoModel).where(DocumentoModel.estado == estado.value)
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]

    def list(self) -> list[Documento]:
        rows = self._session.execute(select(DocumentoModel)).scalars().all()
        return [_to_entity(r) for r in rows]
