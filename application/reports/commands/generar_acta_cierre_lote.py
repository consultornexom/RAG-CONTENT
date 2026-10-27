"""Caso de uso de Fase 8: "Acta de cierre de lote" (Documento Maestro,
seccion 7.1: "Liberados, bloqueados, exclusiones, riesgos, aprobadores y
version"; seccion 10.1, etapa 14: "firmar acta y exportar" -- la parte
que la Fase 7 dejo explicitamente pendiente para esta fase).

Deliberadamente SEPARADO de `application.batches.commands.cerrar_lote.
CerrarLote` (que ya quedo probado y documentado en la Fase 7) en vez de
extenderlo -- mismo principio que `GenerarManifiesto` es un paso
explicito distinto de `LiberarDocumento`: cerrar un lote y generar su
acta son dos operaciones separadas, la segunda puede repetirse (por
ejemplo, para volver a exportarla) sin repetir la primera.

Depende directamente de `domain.batches.ports.LoteRepository` y de
`domain.documents.ports.AprobacionRepository` (los puertos de esos
contextos, no sus fachadas) -- mismo patron de acoplamiento cruzado ya
usado por `CerrarLote` con `GovernanceService`/`DocumentRepository`.
Desde el 2026-07-31 tambien depende de `GovernanceService` directamente
(ver `_motivo_riesgo`, corregido en la tercera auditoria general del
mismo dia)."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.batches.exceptions import BatchNotFoundError
from domain.batches.entities import EstadoLote
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento, EstadoDocumento
from domain.documents.ports import AprobacionRepository, DocumentRepository
from domain.governance.exceptions import AprobacionFaltanteError, FuenteFaltanteError
from domain.reports.entities import ActaCierreLote
from domain.reports.exceptions import LoteNoCerradoParaActaError
from domain.reports.ports import ReportWriter


class GenerarActaCierreLote:
    def __init__(
        self,
        lote_repository: LoteRepository,
        document_repository: DocumentRepository,
        aprobacion_repository: AprobacionRepository,
        governance: GovernanceService,
        writer: ReportWriter,
    ):
        self._lote_repository = lote_repository
        self._document_repository = document_repository
        self._aprobacion_repository = aprobacion_repository
        self._governance = governance
        self._writer = writer

    def execute(self, lote_id: str) -> str:
        """Devuelve la ruta absoluta del acta escrita.

        Lanza `BatchNotFoundError` si el lote no existe, o
        `LoteNoCerradoParaActaError` si todavia esta ABIERTO -- el acta
        describe como se resolvio el cierre, no tiene sentido antes de
        que ocurra."""
        lote = self._lote_repository.get(lote_id)
        if lote is None:
            raise BatchNotFoundError(lote_id)
        if lote.estado != EstadoLote.CERRADO:
            raise LoteNoCerradoParaActaError(lote_id)

        documentos_lote = [d for d in self._document_repository.list() if d.lote_id == lote_id]
        liberados = [d for d in documentos_lote if d.estado == EstadoDocumento.LIBERADO]
        bloqueados = [d for d in documentos_lote if d.estado == EstadoDocumento.BLOQUEADO]
        exclusiones = [d for d in documentos_lote if d.estado == EstadoDocumento.DESCARTADO]

        aprobadores: set[str] = set()
        for documento in liberados:
            for aprobacion in self._aprobacion_repository.list_by_document(documento.id):
                aprobadores.add(aprobacion.aprobador)

        acta = ActaCierreLote(
            lote_id=lote.id,
            nombre_lote=lote.nombre,
            fecha_cierre=lote.cerrado_en.isoformat() if lote.cerrado_en else None,
            liberados=[d.id for d in liberados],
            bloqueados=[d.id for d in bloqueados],
            exclusiones=[d.id for d in exclusiones],
            riesgos=[self._motivo_riesgo(d) for d in bloqueados],
            aprobadores=sorted(aprobadores),
        )
        return self._writer.escribir_acta_cierre_lote(acta)

    def _motivo_riesgo(self, documento: Documento) -> str:
        """Bug real encontrado en la primera auditoria 2026-07-31:
        antes, todo documento bloqueado se reportaba con el mismo
        texto ("revisar Fuente/Aprobacion"), sin importar en que etapa
        se hubiera quedado. `CerrarLote._resolver_documento()` bloquea
        por DOS motivos muy distintos: (a) llego a VALIDADO pero
        `GovernanceService.verificar_documento_liberable()` fallo por
        falta de Fuente o Aprobacion; (b) nunca llego a VALIDADO -- se
        quedo en una etapa anterior del flujo y Fuente/Aprobacion no
        tiene nada que ver.

        Version corregida en la TERCERA auditoria, mismo dia: el primer
        arreglo uso `documento.ruta_markdown is not None` como señal de
        "llego a VALIDADO", pero eso da un falso positivo real: un
        documento puede llegar a MARKDOWN_GENERADO (que ya fija
        `ruta_markdown`, via `generar_markdown()`) sin haber pasado
        todavia por `validar_markdown()` -- son dos comandos separados,
        invocados por botones distintos. Ese documento nunca entra al
        chequeo de gobernanza (que `CerrarLote` solo hace si
        `estado == VALIDADO`), asi que "ruta_markdown no nulo" NO
        implica "goberanza fallo".

        Arreglo definitivo: en vez de inferir el pasado a partir de un
        campo que no fue diseñado para eso, se pregunta por el PRESENTE,
        que si es 100% confiable: se re-ejecuta la misma verificacion de
        gobernanza que `CerrarLote` ya uso (`GovernanceService.
        verificar_documento_liberable()`, que no depende del estado del
        documento, solo mira si hay Fuente y Aprobacion registradas).
        Si de verdad falta una de las dos, ese es el motivo real, sin
        importar en que etapa haya quedado el documento. Si NINGUNA
        falta y aun asi sigue bloqueado, la unica explicacion posible
        (dada la logica de `CerrarLote`) es que nunca llego a VALIDADO."""
        try:
            self._governance.verificar_documento_liberable(documento.id)
        except FuenteFaltanteError:
            return f"{documento.id}: bloqueado al cerrar el lote -- falta registrar la Fuente"
        except AprobacionFaltanteError:
            return f"{documento.id}: bloqueado al cerrar el lote -- falta registrar la Aprobacion"
        return (
            f"{documento.id}: bloqueado al cerrar el lote -- ya tiene Fuente y Aprobacion "
            "registradas, pero no llego a completarse la validacion del Markdown antes del "
            "cierre (revisar en que etapa se quedo, seccion 4.7)"
        )
