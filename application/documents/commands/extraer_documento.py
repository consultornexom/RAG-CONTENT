"""Caso de uso: extraer el contenido de un documento ya clasificado
como extraccion directa, OCR o transcripcion (Modulos 5, 6 y 7,
Documento Maestro seccion 4.6). Mirror funcional del flujo de
extraccion de RAG STUDIO, con la diferencia de que aqui el resultado se
persiste como archivo Markdown (no en una base de fragmentos: RAG
Content Studio Desktop no fragmenta -- eso es responsabilidad de RAG
STUDIO, seccion 4.6.1 del Documento Maestro). El destino depende de la
ruta: extraccion directa/OCR van a 03_extracciones/, transcripcion va a
04_transcripciones/ -- ambas carpetas ya reservadas desde el Modulo 1
(Documento Maestro, seccion 4.5).

`on_progreso` (agregado 2026-07-31) se reenvia sin tocar hasta
`DocumentExtractor.extract()` -- ver su docstring en domain.documents.
ports para el porque (evitar que Windows detecte la interfaz como "no
responde" durante un OCR largo de un solo documento)."""
from __future__ import annotations

from collections.abc import Callable

from domain.documents.entities import Documento, EstadoDocumento, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError, UnsupportedExtractionRouteError
from domain.documents.ports import DocumentExtractor, DocumentRepository, ExtractionOutputStore
from domain.projects.ports import AuditLogger

_RUTAS_SOPORTADAS = frozenset(
    {TipoProcesamiento.EXTRACCION_DIRECTA, TipoProcesamiento.OCR, TipoProcesamiento.TRANSCRIPCION}
)


class ExtraerDocumento:
    def __init__(
        self,
        repository: DocumentRepository,
        extractor: DocumentExtractor,
        output_store: ExtractionOutputStore,
        audit: AuditLogger,
        transcription_output_store: ExtractionOutputStore | None = None,
    ):
        self._repository = repository
        self._extractor = extractor
        self._output_store = output_store
        # Por defecto reusa el mismo store que extraccion directa/OCR
        # (mantiene compatibilidad con quien construya ExtraerDocumento
        # sin pasar este parametro nuevo); app.bootstrap si pasa uno
        # distinto, apuntado a 04_transcripciones/.
        self._transcription_output_store = transcription_output_store or output_store
        self._audit = audit

    def execute(self, documento_id: str, on_progreso: Callable[[int, int], None] | None = None) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        if documento.tipo_procesamiento not in _RUTAS_SOPORTADAS:
            tipo = documento.tipo_procesamiento.value if documento.tipo_procesamiento else None
            raise UnsupportedExtractionRouteError(documento_id, tipo)
        # Se guarda antes de avanzar_a(): ese metodo devuelve un Documento
        # nuevo (mismos datos, otro estado) y mypy no puede propagar la
        # comprobacion "not in _RUTAS_SOPORTADAS" de un objeto a otro. No
        # se usa `assert` (Bandit B101: se elimina con bytecode
        # optimizado) -- este `if` si se ejecuta siempre, y nunca deberia
        # dispararse dado el chequeo anterior.
        tipo_procesamiento = documento.tipo_procesamiento
        if tipo_procesamiento is None:
            raise UnsupportedExtractionRouteError(documento_id, None)

        documento = documento.avanzar_a(EstadoDocumento.EN_EXTRACCION)
        self._repository.save(documento)

        # Bug real encontrado 2026-07-29 (usuario sin Tesseract instalado):
        # si `self._extractor.extract()` lanza una excepcion (motor externo
        # faltante, archivo corrupto, etc.), el documento ya habia quedado
        # guardado en EN_EXTRACCION unas lineas arriba -- sin este
        # try/except quedaba atascado ahi para siempre, porque ni siquiera
        # un reintento posterior podia volver a marcarlo EN_EXTRACCION (esa
        # transicion, de un estado a si mismo, tampoco es valida). Revertir
        # a CLASIFICADO en el fallo deja el documento exactamente como
        # antes de este intento, listo para reintentarse.
        try:
            resultado = self._extractor.extract(
                documento.ruta_copia_original, documento.formato, tipo_procesamiento, on_progreso
            )
            store = (
                self._transcription_output_store
                if tipo_procesamiento == TipoProcesamiento.TRANSCRIPCION
                else self._output_store
            )
            ruta_extraccion = store.guardar(documento.id, resultado.markdown)
        except Exception:
            self._repository.save(documento.marcar_extraccion_fallida())
            raise

        documento = documento.completar_extraccion(
            ruta_extraccion, resultado.advertencias, resultado.mapa_paginas, resultado.rangos_baja_confianza
        )
        self._repository.save(documento)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="extraer_documento",
            valor_anterior=None,
            valor_nuevo=resultado.metodo,
            motivo="Extraccion documental normalizada a Markdown (Documento Maestro, Modulo 5).",
        )
        return documento
