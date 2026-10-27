"""Clasificacion compartida de que le pasaria (o ya le paso) a un
documento al cerrar un lote (Fase 7, Documento Maestro seccion 10.1,
etapa 14). La usan DOS lugares: `commands.cerrar_lote.CerrarLote`
(aplica la resolucion de verdad) y `queries.previsualizar_seleccion_lote.
PrevisualizarSeleccionLote` (solo la muestra, sin tocar nada) --
agregado 2026-10-03 a pedido de NEXOM (Solicitud_Ajustes_RAG_Content_
Lotes_y_Portabilidad.pdf, seccion 2: "antes de confirmar, mostrar...
documentos que cumplen requisitos o presentan bloqueos").

Se extrajo a un modulo propio, en vez de duplicar la logica en ambos
lugares, precisamente para que la vista previa NUNCA pueda divergir de
lo que `CerrarLote` resuelve de verdad -- mismo criterio que el propio
`CerrarLote` ya aplicaba al reusar `GovernanceService.
verificar_documento_liberable()` en vez de reimplementar la regla."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from application.governance.service import GovernanceService
from domain.documents.entities import Documento, EstadoDocumento
from domain.governance.exceptions import AprobacionFaltanteError, FuenteFaltanteError

ESTADOS_YA_RESUELTOS = frozenset(
    {EstadoDocumento.LIBERADO, EstadoDocumento.BLOQUEADO, EstadoDocumento.DESCARTADO, EstadoDocumento.OBSOLETO}
)


@dataclass(frozen=True)
class ResolucionPrevista:
    """`estado_previsto` es el estado que el documento TENDRIA (si
    todavia no se resolvio) o YA TIENE (si ya estaba en
    `ESTADOS_YA_RESUELTOS`) al cerrar el lote ahora mismo.
    `cumple_requisitos` es `True` solo si ese estado es LIBERADO;
    `motivo` explica por que no, o es `None` si cumple."""

    documento: Documento
    estado_previsto: EstadoDocumento
    cumple_requisitos: bool
    motivo: Optional[str]


def clasificar_para_cierre(documento: Documento, governance: GovernanceService) -> ResolucionPrevista:
    """Puro en el sentido de que no guarda nada -- `GovernanceService.
    verificar_documento_liberable()` solo lee (Fuente/Aprobacion ya
    registradas), nunca escribe. Quien llama decide que hacer con el
    resultado: `CerrarLote` lo usa para mutar de verdad; la
    previsualizacion solo lo muestra."""
    if documento.estado in ESTADOS_YA_RESUELTOS:
        ya_liberado = documento.estado == EstadoDocumento.LIBERADO
        motivo = None if ya_liberado else f"Ya quedo resuelto antes como '{documento.estado.value}'."
        return ResolucionPrevista(documento, documento.estado, ya_liberado, motivo)

    if documento.estado == EstadoDocumento.VALIDADO:
        try:
            governance.verificar_documento_liberable(documento.id)
            return ResolucionPrevista(documento, EstadoDocumento.LIBERADO, True, None)
        except FuenteFaltanteError:
            return ResolucionPrevista(
                documento, EstadoDocumento.BLOQUEADO, False, "Falta registrar una fuente para este documento."
            )
        except AprobacionFaltanteError:
            return ResolucionPrevista(
                documento, EstadoDocumento.BLOQUEADO, False, "Falta aprobar este documento para generar Markdown."
            )

    return ResolucionPrevista(
        documento,
        EstadoDocumento.BLOQUEADO,
        False,
        f"Estado actual '{documento.estado.value}' -- todavia no esta VALIDADO para poder liberarse.",
    )
