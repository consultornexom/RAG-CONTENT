"""Caso de uso del Modulo 12: generar el manifiesto de entrega hacia
RAG STUDIO (Documento Maestro, seccion 4.6.1) a partir de los
documentos LIBERADO del proyecto -- de todos, o solo de un lote si se
indica `lote_id` (Fase 7, seccion 4.6.1: "manifiesto por lote").

Hasta la Fase 6 no existia el contexto Lotes, asi que este caso de uso
solo sabia generar el manifiesto "de todo el proyecto liberado hasta
ahora" -- con la Fase 7 (`domain.batches`, `Documento.lote_id`) ya se
puede filtrar por lote sin cambiar el resto de su forma, exactamente
como se anticipo entonces. `lote_id=None` (predeterminado) preserva el
comportamiento anterior sin cambios -- documentos sin ningun lote
asignado (`Documento.lote_id is None`) NUNCA aparecen en un manifiesto
filtrado por lote, solo en el manifiesto de "todo el proyecto".

Depende directamente de `domain.validity.ports.VigenciaRepository` (el
puerto del otro contexto, no su fachada de aplicacion) -- mismo patron
de acoplamiento cruzado ya usado por RegistrarIncidencia/
GovernanceService. No depende de FuenteRepository: ninguna columna del
manifiesto (seccion 4.6.1) proviene de Fuente -- LiberarDocumento ya
garantiza que toda Fuente existe antes de llegar a LIBERADO (Modulo 13,
tercera regla), pero su contenido (sistema_origen/autoridad/evidencia)
no se transcribe aqui.

Vuelve a generar el archivo completo cada vez que se ejecuta
(determinista, seccion 4.11.1): nunca acumula, siempre refleja el
conjunto LIBERADO actual.

Hallazgo real de la cuarta auditoria general (2026-08-01): antes de
depender de `LoteRepository`, un `lote_id` con un typo (o de un lote ya
borrado/de otro proyecto) no producia ningun aviso -- simplemente
filtraba a una lista vacia, generando en silencio un manifiesto vacio
justo en el ultimo paso antes de entregar a RAG STUDIO. Ahora se
resuelve el lote contra el repositorio antes de filtrar, igual que ya
hace `AgregarDocumentoALote` con el mismo puerto."""
from __future__ import annotations

from domain.batches.exceptions import BatchNotFoundError
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento, EstadoDocumento, FilaManifiesto
from domain.documents.ports import DocumentRepository, ManifestWriter
from domain.documents.rutas import nombre_de_archivo_multiplataforma
from domain.validity.ports import VigenciaRepository


def _nombre_de_archivo(ruta: str) -> str:
    """Ultimo segmento no vacio de `ruta`, reconociendo tanto "/" como
    "\\" como separador -- a proposito NO usa `pathlib.Path(...).name`,
    que solo reconoce el separador nativo del sistema donde corre el
    proceso. Delega en `domain.documents.rutas`, la misma funcion que usa
    `LocalEntregaRagStudioStore` para nombrar la copia del archivo, para
    que el manifiesto y la carpeta de entrega nunca difieran (auditoria
    2026-09-30). Es la misma extraccion que RAG STUDIO aplica del otro
    lado para manifiestos legado (ver
    CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md)."""
    return nombre_de_archivo_multiplataforma(ruta)


def _fila_de(documento: Documento, vigencia_repository: VigenciaRepository) -> FilaManifiesto:
    vigencia = vigencia_repository.get_by_document(documento.id)
    # hash_markdown/ruta_markdown estan garantizados por construccion en
    # cualquier documento LIBERADO (no se puede llegar ahi sin pasar por
    # generar_markdown()) -- se comprueba con un `if` normal, no con
    # `assert` (Bandit B101: se elimina con bytecode optimizado, ver el
    # mismo razonamiento en ExtraerDocumento.execute()).
    if documento.hash_markdown is None or documento.ruta_markdown is None:
        raise ValueError(
            f"El documento '{documento.id}' esta LIBERADO pero no tiene hash_markdown/ruta_markdown -- "
            "esto no deberia ser posible por el flujo normal."
        )
    return FilaManifiesto(
        titulo=documento.metadatos.get("titulo_oficial") or documento.nombre_original,
        tipo_fuente="markdown",
        # Solo el nombre de archivo (nunca la ruta absoluta interna de
        # este equipo) -- incidencia real de portabilidad 2026-09-29:
        # un lote procesado en Windows se copio a un equipo macOS y RAG
        # STUDIO no pudo resolver ningun documento porque `ruta_archivo`
        # traia la ruta completa de Windows. El nombre de archivo es lo
        # unico que sigue siendo valido en cualquier equipo: el .md
        # siempre se copia con este mismo nombre a 14_entrega_rag_studio/
        # (ver LocalEntregaRagStudioStore.preparar()), junto al propio
        # manifiesto -- ver CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md.
        ruta_archivo=_nombre_de_archivo(documento.ruta_markdown),
        area_propietaria=documento.metadatos.get("area_propietaria", ""),
        nivel_acceso=documento.metadatos.get("nivel_confidencialidad", ""),
        idioma=documento.metadatos.get("idioma", "es"),
        hash_contenido=documento.hash_markdown,
        vigente_desde=vigencia.vigente_desde.isoformat() if vigencia and vigencia.vigente_desde else None,
        vigente_hasta=vigencia.vigente_hasta.isoformat() if vigencia and vigencia.vigente_hasta else None,
        autoridad_fuente=None,
        sustituye_a=vigencia.sustituye_a if vigencia else None,
    )


class GenerarManifiesto:
    def __init__(
        self,
        repository: DocumentRepository,
        lote_repository: LoteRepository,
        vigencia_repository: VigenciaRepository,
        writer: ManifestWriter,
    ):
        self._repository = repository
        self._lote_repository = lote_repository
        self._vigencia_repository = vigencia_repository
        self._writer = writer

    def execute(self, lote_id: str | None = None) -> str:
        """Devuelve la ruta absoluta del manifiesto escrito.

        Si `lote_id` es `None` (predeterminado), incluye todo documento
        LIBERADO del proyecto, sin importar su lote (o la ausencia de
        uno) -- comportamiento sin cambios desde la Fase 5. Si se indica
        un `lote_id`, se valida primero que el lote exista (lanza
        `BatchNotFoundError` si no) y solo incluye los LIBERADO que
        ademas pertenezcan a ESE lote."""
        if lote_id is not None and self._lote_repository.get(lote_id) is None:
            raise BatchNotFoundError(lote_id)
        liberados = [d for d in self._repository.list() if d.estado == EstadoDocumento.LIBERADO]
        if lote_id is not None:
            liberados = [d for d in liberados if d.lote_id == lote_id]
        filas = [_fila_de(d, self._vigencia_repository) for d in liberados]
        return self._writer.escribir(filas)
