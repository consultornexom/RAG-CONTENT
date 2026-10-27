"""Caso de uso: cerrar un lote (Fase 7, Documento Maestro seccion 10.1,
etapa 14: "Liberar aprobados, bloquear pendientes, firmar acta y
exportar" -> "Lote cerrado"). "Firmar acta y exportar" queda para la
Fase 8 (Reportes y documentacion automatica, seccion 7.1) -- este caso
de uso solo resuelve el estado de cada documento del lote, que es la
parte que de verdad bloquea avanzar a la Fase 8 (un acta de cierre no
tiene sentido sobre documentos que todavia no se resolvieron).

Por cada documento del lote:
  - Si ya esta LIBERADO, BLOQUEADO, DESCARTADO u OBSOLETO: no se toca
    (ya tiene una resolucion final o casi final).
  - Si esta VALIDADO: se intenta liberar de verdad, reutilizando la
    MISMA verificacion de `GovernanceService.verificar_documento_liberable()`
    que usa `application.documents.commands.liberar_documento.
    LiberarDocumento` -- nunca se duplica la regla, solo su invocacion
    (se evita instanciar aqui el caso de uso `LiberarDocumento` completo
    de otro contexto para no acoplar `application.batches` a los
    detalles de construccion de `application.documents`; mismo tipo de
    duplicacion pequena y documentada que `domain.jobs.entities.
    Prioridad`). Si la liberacion falla (falta Fuente o Aprobacion), el
    documento sigue VALIDADO y cae en la regla de abajo.
  - Cualquier otro caso (todavia no VALIDADO, o VALIDADO sin poderse
    liberar): se bloquea (`Documento.avanzar_a(BLOQUEADO)`) -- "bloquear
    pendientes".

Nota sobre "no cerrar un lote con documentos sin estado" (Documento
Maestro, seccion 4.7): `Documento.estado` es un campo obligatorio de
`EstadoDocumento`, nunca `None` -- esta regla ya esta garantizada por
construccion desde que existe un `Documento`, igual que el hallazgo
sobre el hash en la tercera regla del Modulo 13 (Fase 5). El unico
guardia real que este caso de uso necesita agregar es
`LoteVacioError`: cerrar un lote sin ningun documento asociado no tiene
nada que liberar ni que bloquear."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.batches.entities import Lote
from domain.batches.exceptions import BatchNotFoundError, LoteVacioError
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento, EstadoDocumento
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger

from .._resolucion import clasificar_para_cierre


class CerrarLote:
    def __init__(
        self,
        lote_repository: LoteRepository,
        document_repository: DocumentRepository,
        governance: GovernanceService,
        audit: AuditLogger,
    ):
        self._lote_repository = lote_repository
        self._document_repository = document_repository
        self._governance = governance
        self._audit = audit

    def _resolver_documento(self, documento: Documento) -> Documento:
        # Delega la CLASIFICACION a `clasificar_para_cierre` (compartida
        # con `PrevisualizarSeleccionLote`, agregado 2026-10-03) y solo
        # aplica aqui la mutacion de verdad -- misma regla, un unico
        # lugar que decide "libera o bloquea", para que la vista previa
        # de la seleccion nunca pueda mostrar algo distinto de lo que
        # este metodo termina haciendo.
        resolucion = clasificar_para_cierre(documento, self._governance)
        if resolucion.estado_previsto == documento.estado:
            return documento  # ya resuelto antes (LIBERADO/BLOQUEADO/DESCARTADO/OBSOLETO) -- sin cambios.
        if resolucion.estado_previsto == EstadoDocumento.LIBERADO:
            return documento.liberar()
        return documento.avanzar_a(EstadoDocumento.BLOQUEADO)

    def execute(self, lote_id: str) -> Lote:
        lote = self._lote_repository.get(lote_id)
        if lote is None:
            raise BatchNotFoundError(lote_id)

        documentos_del_lote = [d for d in self._document_repository.list() if d.lote_id == lote_id]
        if not documentos_del_lote:
            raise LoteVacioError(lote_id)

        liberados = 0
        bloqueados = 0
        for documento in documentos_del_lote:
            estado_original = documento.estado
            documento = self._resolver_documento(documento)
            if documento.estado != estado_original:
                self._document_repository.save(documento)
                # Bug real encontrado en la segunda auditoria 2026-07-31:
                # antes, este caso de uso solo dejaba un resumen agregado
                # en la auditoria al final de execute() -- si save() (o
                # cualquier paso posterior) fallaba a mitad del lote, los
                # documentos que ya cambiaron de estado en esa corrida
                # quedaban sin ningun rastro individual en la auditoria,
                # a diferencia de RecuperarDocumentosInterrumpidos (mismo
                # patron de "loop + guardar + auditar") que si audita cada
                # elemento dentro del ciclo. El Documento Maestro (seccion
                # 4.1) exige que la auditoria sea completa, no solo un
                # resumen final -- se agrega aqui, por documento, sin
                # quitar el resumen agregado de mas abajo (ese sigue
                # siendo util para leer de un vistazo cuantos de cada
                # tipo hubo).
                self._audit.record(
                    proyecto_id=documento.proyecto_id,
                    accion="cerrar_lote_documento",
                    valor_anterior=estado_original.value,
                    valor_nuevo=documento.estado.value,
                    motivo=f"Resolucion individual al cerrar el lote '{lote.nombre}' "
                    "(Documento Maestro, seccion 10.1, etapa 14).",
                )
                if documento.estado == EstadoDocumento.LIBERADO:
                    liberados += 1
                elif documento.estado == EstadoDocumento.BLOQUEADO:
                    bloqueados += 1

        lote = lote.cerrar()
        self._lote_repository.save(lote)
        self._audit.record(
            proyecto_id=lote.proyecto_id,
            accion="cerrar_lote",
            valor_anterior=None,
            valor_nuevo=f"{len(documentos_del_lote)} documentos ({liberados} liberados, {bloqueados} bloqueados)",
            motivo="Cierre de lote: libera los documentos aprobados y bloquea los pendientes "
            "(Documento Maestro, seccion 10.1, etapa 14).",
        )
        return lote
