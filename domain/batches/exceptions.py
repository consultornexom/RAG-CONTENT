"""Excepciones del contexto Lotes."""
from __future__ import annotations


class BatchDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class InvalidBatchStateTransitionError(BatchDomainError):
    def __init__(self, origen: str, destino: str):
        super().__init__(
            f"No se permite pasar el lote de '{origen}' a '{destino}' -- ver "
            "domain.batches.entities._TRANSICIONES."
        )
        self.origen = origen
        self.destino = destino


class BatchNotFoundError(BatchDomainError):
    def __init__(self, lote_id: str):
        super().__init__(f"No se encontro el lote '{lote_id}' en el proyecto.")
        self.lote_id = lote_id


class LoteCerradoError(BatchDomainError):
    """No se puede agregar ni quitar documentos de un lote que ya se
    cerro (Documento Maestro, seccion 10.1, etapa 14: cerrar un lote ya
    resolvio el estado de cada documento que contenia en ese momento --
    modificar su composicion despues dejaria esa resolucion
    incompleta)."""

    def __init__(self, lote_id: str):
        super().__init__(f"El lote '{lote_id}' ya esta cerrado -- no admite mas documentos.")
        self.lote_id = lote_id


class LoteVacioError(BatchDomainError):
    """No se puede cerrar un lote sin ningun documento asociado -- no
    hay nada que liberar ni que bloquear (Documento Maestro, seccion
    10.1, etapa 14)."""

    def __init__(self, lote_id: str):
        super().__init__(f"El lote '{lote_id}' no tiene ningun documento asociado -- no se puede cerrar.")
        self.lote_id = lote_id


class SeleccionLoteVaciaError(BatchDomainError):
    """Ajuste NEXOM 2026-10-03 (Solicitud_Ajustes_RAG_Content_Lotes_y_
    Portabilidad.pdf, seccion 2: "Impedir el cierre de una seleccion
    vacia"). Distinto de `LoteVacioError`: ese aplica a un lote que YA
    existe y quedo sin documentos; este se lanza ANTES de crear ninguna
    fila de lote, cuando quien cierra no selecciono ningun documento --
    para no dejar un lote vacio huerfano (ABIERTO, sin miembros, que
    nadie podria cerrar despues sin toparse con `LoteVacioError`)."""

    def __init__(self, nombre_lote: str):
        super().__init__(f"No se puede crear el lote '{nombre_lote}' sin ningun documento seleccionado.")
        self.nombre_lote = nombre_lote
