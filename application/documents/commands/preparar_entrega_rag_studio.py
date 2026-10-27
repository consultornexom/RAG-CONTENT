"""Caso de uso del Modulo 12: preparar, en UNA sola carpeta
(14_entrega_rag_studio/, Documento Maestro seccion 4.5), lo que se debe
entregar a RAG STUDIO (seccion 4.6.1) -- agregado 2026-07-31 (comentario
real del consultor: al terminar de procesar los documentos, la
herramienta debia dejar listos, en un solo lugar, los archivos que el
operador tiene que llevarse, en vez de obligarlo a ir a buscarlos por
separado a 07_markdown/ y 12_exportaciones/).

Reusa `GenerarManifiesto` (no duplica su logica de armado de filas ni
cambia el manifiesto canonico de 12_exportaciones/, que sigue siendo la
unica fuente de verdad del contenido del manifiesto, Documento Maestro
seccion 4.6.1) -- este caso de uso solo se encarga de, ADEMAS, copiar
ese manifiesto y cada Markdown LIBERADO a la carpeta consolidada.

Entregas separadas por lote, con version (2026-10-03, NEXOM,
Solicitud_Ajustes_RAG_Content_Lotes_y_Portabilidad.pdf, seccion 3):
cuando `lote_id` no es `None`, se le pasa a
`EntregaRagStudioStore.preparar()` un `identificador_entrega` derivado
del propio lote (`"<id_lote>_<nombre del lote, convertido a un nombre de
carpeta seguro>"`) para que el adaptador escriba en una subcarpeta propia
y versionada, sin tocar la entrega de ningun otro lote -- ver el
docstring de `infrastructure.filesystem.entrega_rag_studio_store.
LocalEntregaRagStudioStore.preparar`. Con `lote_id=None` (entrega de
todo el proyecto) no se pasa ningun identificador y el comportamiento es
exactamente el de antes."""
from __future__ import annotations

import re

from domain.batches.exceptions import BatchNotFoundError
from domain.batches.ports import LoteRepository
from domain.documents.entities import EstadoDocumento
from domain.documents.ports import DocumentRepository, EntregaRagStudioStore

from .generar_manifiesto import GenerarManifiesto

_PATRON_CARACTER_INSEGURO = re.compile(r"[^A-Za-z0-9]+")


def _identificador_entrega_de_lote(lote_id: str, nombre_lote: str) -> str:
    """Convierte el nombre del lote en algo seguro como nombre de
    carpeta en Windows/macOS/Linux por igual (sin espacios, acentos ni
    separadores de ruta) y lo antepone con el id del lote -- el id solo
    ya identifica de forma unica, pero el nombre lo hace legible para el
    operador que navega la carpeta a mano (pedido explicito: carpeta
    "identificada por ID unico, nombre y version de entrega")."""
    slug = _PATRON_CARACTER_INSEGURO.sub("_", nombre_lote.strip()).strip("_") or "LOTE"
    return f"{lote_id}_{slug}"


class PrepararEntregaRagStudio:
    def __init__(
        self,
        document_repository: DocumentRepository,
        generar_manifiesto: GenerarManifiesto,
        entrega_store: EntregaRagStudioStore,
        lote_repository: LoteRepository | None = None,
    ):
        self._document_repository = document_repository
        self._generar_manifiesto = generar_manifiesto
        self._entrega_store = entrega_store
        self._lote_repository = lote_repository

    def execute(self, lote_id: str | None = None) -> str:
        """Devuelve la ruta absoluta de la carpeta de entrega.

        Mismo filtro de `lote_id` que `GenerarManifiesto.execute()` (ver
        su docstring): `None` incluye todo LIBERADO del proyecto; un
        `lote_id` concreto solo los LIBERADO de ese lote -- y en ese
        caso, ADEMAS, la entrega se escribe en su propia subcarpeta
        versionada (ver docstring del modulo)."""
        ruta_manifiesto = self._generar_manifiesto.execute(lote_id)
        liberados = [d for d in self._document_repository.list() if d.estado == EstadoDocumento.LIBERADO]
        identificador_entrega: str | None = None
        if lote_id is not None:
            liberados = [d for d in liberados if d.lote_id == lote_id]
            # GenerarManifiesto.execute() ya valido que el lote exista
            # (BatchNotFoundError si no) -- aqui se repite la busqueda
            # solo para leer el nombre, no la existencia; si por una
            # condicion de carrera el lote desapareciera justo entre
            # ambas llamadas, se prefiere fallar explicito en vez de
            # entregar con un identificador generico.
            if self._lote_repository is None:
                raise RuntimeError(
                    "PrepararEntregaRagStudio necesita lote_repository para entregar un lote especifico "
                    "en su propia carpeta versionada."
                )
            lote = self._lote_repository.get(lote_id)
            if lote is None:
                raise BatchNotFoundError(lote_id)
            identificador_entrega = _identificador_entrega_de_lote(lote.id, lote.nombre)
        rutas_markdown = [d.ruta_markdown for d in liberados if d.ruta_markdown is not None]
        return self._entrega_store.preparar(ruta_manifiesto, rutas_markdown, identificador_entrega)
