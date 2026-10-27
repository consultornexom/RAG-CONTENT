"""Caso de uso: crear un lote con una SELECCION explicita de documentos
y cerrarlo de inmediato -- agregado 2026-10-03 a pedido de NEXOM
(Solicitud_Ajustes_RAG_Content_Lotes_y_Portabilidad.pdf, seccion 2).

Antes de este ajuste, la unica forma de cerrar un lote desde el
Asistente era `EtapaCerrarLote._on_cerrar_lote()` iterando TODOS los
documentos del proyecto -- sin selección real: un documento ya resuelto
en un lote CERRADO anterior quedaba protegido solo de forma incidental
(`AgregarDocumentoALote` rechaza reasignarlo y la etapa ignoraba ese
error en silencio), pero cualquier documento nuevo, todavia sin lote
asignado, se arrastraba igual al lote nuevo aunque el operador no
quisiera tocarlo todavia.

Este caso de uso NO agrega ninguna regla de negocio nueva -- compone,
en orden, tres casos de uso que ya existian: `CrearLote`,
`AgregarDocumentoALote` (una vez por cada documento seleccionado) y
`CerrarLote`. La unica regla nueva es la guardia de seleccion vacia
(`SeleccionLoteVaciaError`), que se verifica ANTES de crear el lote
para no dejar un lote huerfano sin miembros.

Nota sobre fallos a mitad de camino: si `AgregarDocumentoALote` falla
para alguno de los documentos seleccionados (por ejemplo, un id que ya
no existe), el lote ya creado y los documentos ya agregados hasta ese
punto quedan tal cual (cada paso ya se audita por separado, mismo
criterio que el resto de `application.batches` y `application.documents`
-- no hay una transaccion que cubra los tres pasos como una sola
unidad). Quien llama ve la excepcion y puede decidir: reintentar sobre
el mismo lote (ya quedo ABIERTO, con los documentos que si se
agregaron) usando `AgregarDocumentoALote`/`CerrarLote` directamente, o
abandonarlo."""
from __future__ import annotations

from domain.batches.entities import Lote
from domain.batches.exceptions import SeleccionLoteVaciaError

from .agregar_documento_a_lote import AgregarDocumentoALote
from .cerrar_lote import CerrarLote
from .crear_lote import CrearLote


class CrearLoteConSeleccionYCerrar:
    def __init__(
        self,
        crear_lote: CrearLote,
        agregar_documento_a_lote: AgregarDocumentoALote,
        cerrar_lote: CerrarLote,
    ):
        self._crear_lote = crear_lote
        self._agregar_documento_a_lote = agregar_documento_a_lote
        self._cerrar_lote = cerrar_lote

    def execute(self, proyecto_id: str, nombre_lote: str, documento_ids: list[str]) -> Lote:
        # dict.fromkeys conserva el orden y quita duplicados -- un mismo
        # id marcado dos veces en la seleccion (no deberia pasar desde
        # una tabla de casillas, pero esto no depende de que la UI lo
        # evite) no debe generar dos entradas de auditoria identicas.
        ids_unicos = list(dict.fromkeys(documento_ids))
        if not ids_unicos:
            raise SeleccionLoteVaciaError(nombre_lote)

        lote = self._crear_lote.execute(proyecto_id, nombre_lote)
        for documento_id in ids_unicos:
            self._agregar_documento_a_lote.execute(lote.id, documento_id)
        return self._cerrar_lote.execute(lote.id)
