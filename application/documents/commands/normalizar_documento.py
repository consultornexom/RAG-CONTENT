"""Caso de uso: normalizar el Markdown ya revisado de un documento
(Modulo 9, Documento Maestro seccion 4.6). Las reglas las define el
perfil del proyecto ("reglas en YAML por perfil", ADR-001 seccion 8) y
se resuelven una sola vez al abrir el proyecto (ver
app.bootstrap.abrir_proyecto) -- este caso de uso no conoce
domain.profiles en absoluto, solo recibe la lista ya resuelta.

Requiere que el documento ya este REVISADO (Modulo 8): `avanzar_a()`
rechaza la transicion EN_NORMALIZACION si el documento no viene de ahi,
con el mismo InvalidDocumentStateTransitionError que ya usa el resto
del flujo principal -- no hace falta una excepcion nueva.
"""
from __future__ import annotations

from pathlib import Path

from domain.documents.entities import Documento, EstadoDocumento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository, ExtractionOutputStore, NormalizationEngine
from domain.profiles.entities import ReglaNormalizacion
from domain.projects.ports import AuditLogger


class NormalizarDocumento:
    def __init__(
        self,
        repository: DocumentRepository,
        engine: NormalizationEngine,
        reglas: list[ReglaNormalizacion],
        output_store: ExtractionOutputStore,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._engine = engine
        self._reglas = reglas
        self._output_store = output_store
        self._audit = audit

    def execute(self, documento_id: str) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        # Guardado antes de avanzar_a(): ver el mismo razonamiento en
        # ExtraerDocumento.execute() -- se necesita la ruta del Markdown
        # ya revisado antes de que avanzar_a() devuelva un Documento
        # nuevo. ruta_markdown_vigente() prefiere la correccion humana
        # (Modulo 8, ruta_revisado) sobre la extraccion en crudo, si el
        # revisor guardo alguna -- ver su docstring en domain.documents.
        ruta_markdown_revisado = documento.ruta_markdown_vigente()
        if ruta_markdown_revisado is None:
            # Solo alcanzable si alguien fuerza el estado a mano
            # (avanzar_a no permite llegar a REVISADO sin haber pasado
            # antes por EXTRAIDO, que es quien fija ruta_extraccion) --
            # de todos modos se falla explicito, nunca en silencio. No
            # es DocumentNotFoundError (el documento si existe) ni un
            # error de dominio de este contexto -- es una invariante
            # violada que solo pasaria por manipulacion directa del
            # repositorio.
            raise ValueError(
                f"El documento '{documento_id}' esta en estado '{documento.estado.value}' pero no tiene "
                "ruta_extraccion -- no se puede normalizar sin el Markdown ya revisado."
            )

        documento = documento.avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        self._repository.save(documento)

        # Mismo bug y mismo criterio que ExtraerDocumento.execute() (ver su
        # comentario, encontrado 2026-07-29): sin este try/except, un fallo
        # del motor de normalizacion dejaba el documento atascado en
        # EN_NORMALIZACION sin ninguna forma de reintentarlo.
        try:
            markdown = Path(ruta_markdown_revisado).read_text(encoding="utf-8")
            resultado = self._engine.normalizar(markdown, self._reglas)
            ruta_normalizado = self._output_store.guardar(documento.id, resultado.markdown_normalizado)
        except Exception:
            self._repository.save(documento.marcar_normalizacion_fallida())
            raise

        documento = documento.completar_normalizacion(ruta_normalizado, resultado.cambios)
        self._repository.save(documento)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="normalizar_documento",
            valor_anterior=None,
            valor_nuevo=f"{len(resultado.cambios)} cambio(s) aplicado(s)",
            motivo="Normalizacion de Markdown aplicando reglas del perfil (Documento Maestro, Modulo 9).",
        )
        return documento
