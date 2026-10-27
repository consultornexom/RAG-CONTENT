"""Caso de uso de Fase 9: correr las "pruebas minimas por dominio"
(Documento Maestro, seccion 8.1) y los "umbrales recomendados de
liberacion" (seccion 8.2) contra un corpus real de documentos
representativos (Anexo B, confirmado 2026-07-28) -- invocado solo por
`scripts/ejecutar_pruebas_aceptacion.py`, nunca desde `app.bootstrap`
ni expuesto a la GUI: es una actividad de control de calidad del propio
desarrollo, no una funcionalidad del producto para el usuario final.

Para cada archivo del corpus corre el flujo real y completo -- registro,
clasificacion, extraccion, revision, normalizacion, fuente, vigencia,
aprobacion, generacion de Markdown, validacion y liberacion -- y ademas
agrupa todos los documentos procesados en un `Lote` propio de la
corrida, lo cierra y genera su acta (Fase 7/8), porque la fila
"Liberacion" de la tabla 8.1 exige explicitamente "acta de cierre". Un
archivo que falle en cualquier paso (por ejemplo, un audio sin el motor
de transcripcion disponible) no aborta la corrida completa: queda
registrado con su error y excluido de los pasos posteriores, mismo
principio de "documentar el hallazgo, nunca fallar en silencio ni
fallar todo por uno" que el resto de la herramienta.

Depende directamente de las FACHADAS de aplicacion (`DocumentsService`,
`ValidityService`, `IncidentsService`, `BatchesService`,
`ReportsService`), no de puertos de domain -- a diferencia del resto de
casos de uso de este proyecto (que resuelven una sola regla de negocio
y por eso dependen de puertos concretos), este orquesta el flujo
COMPLETO que un operador real ejecutaria a mano desde la interfaz,
exactamente como lo haria una capa `ui` (ADR-001, seccion 4: "ui
depende solo de application")."""
from __future__ import annotations

import hashlib

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from application.batches.service import BatchesService
from application.documents.service import DocumentsService
from application.incidents.service import IncidentsService
from application.reports.service import ReportsService
from application.validity.service import ValidityService
from domain.acceptance.entities import CriterioDominio, CriterioUmbral, InformeAceptacion
from domain.batches.entities import Lote
from domain.documents.entities import Criticidad, Documento, EstadoDocumento, TipoProcesamiento
from domain.documents.exceptions import DuplicateDocumentHashError
from domain.validity.entities import vigencia_desconocida

_DESCRIPCIONES: dict[str, str] = {
    "Inventario": "ID y hash para todos, rutas validas, duplicados clasificados, estados y campos obligatorios completos.",
    "Extraccion": (
        "Paginas esperadas, contenido no vacio, orden, tablas, caracteres extranos, paginas faltantes y "
        "cobertura de revision."
    ),
    "OCR": "Confianza, paginas debiles, cifras/fechas dudosas, palabras no reconocidas y comparacion con muestras verificadas.",
    "Normalizacion": "Jerarquia, listas, tablas, ausencia de ruido, conservacion de advertencias/excepciones y cambios aprobados.",
    "Markdown": "YAML valido, UTF-8, ID, fuente, hash, jerarquia, enlaces, campos obligatorios y ausencia de marcadores pendientes.",
    "Trazabilidad": "Recorrido completo Markdown -> normalizado -> revisado -> extraido -> original -> fuente.",
    "Liberacion": "Reglas del perfil, aprobaciones, vigencias, incidencias, integridad y acta de cierre.",
}

_MARCADORES_PENDIENTES = ("TODO", "FIXME", "[pendiente]", "XXX")


@dataclass
class _ResultadoDocumento:
    nombre_original: str
    documento: Optional[Documento] = None
    error: Optional[str] = None


def _criterio_pendiente(dominio: str, detalle: str) -> CriterioDominio:
    return CriterioDominio(dominio=dominio, descripcion=_DESCRIPCIONES[dominio], cumplido=None, detalle=detalle)


def _pct(numerador: int, total: int) -> str:
    return "N/D (0 aplicables)" if total == 0 else f"{numerador / total * 100:.0f}%"


def _documento_de(resultado: _ResultadoDocumento) -> Documento:
    """`procesados` (ver `execute()`) ya filtro por `documento is not
    None` -- esto esta garantizado por construccion en cualquier lugar
    donde se llame con un elemento de esa lista. Se comprueba con un
    `if` normal, no con `assert` (Bandit B101: se elimina con bytecode
    optimizado), mismo razonamiento que
    `application.documents.commands.generar_manifiesto._fila_de()`."""
    if resultado.documento is None:
        raise ValueError(f"'{resultado.nombre_original}' no tiene un Documento asociado -- esto no deberia pasar aqui.")
    return resultado.documento


class EjecutarPruebasDeAceptacion:
    def __init__(
        self,
        documents: DocumentsService,
        validity: ValidityService,
        incidents: IncidentsService,
        batches: BatchesService,
        reports: ReportsService,
        proyecto_id: str,
    ):
        self._documents = documents
        self._validity = validity
        self._incidents = incidents
        self._batches = batches
        self._reports = reports
        self._proyecto_id = proyecto_id

    def execute(self, corpus_dir: Path) -> InformeAceptacion:
        fecha = datetime.now(timezone.utc).isoformat()
        archivos = sorted(p for p in corpus_dir.rglob("*") if p.is_file())

        if not archivos:
            detalle = f"Corpus vacio -- no hay ningun archivo dentro de '{corpus_dir}' todavia."
            return InformeAceptacion(
                fecha=fecha,
                corpus_ruta=str(corpus_dir),
                documentos_evaluados=[],
                criterios_dominio=[_criterio_pendiente(dominio, detalle) for dominio in _DESCRIPCIONES],
                criterios_umbral=[],
            )

        resultados = [self._procesar_uno(archivo) for archivo in archivos]
        procesados = [r for r in resultados if r.documento is not None]

        lote_cerrado = None
        ruta_acta = ""
        if procesados:
            lote = self._batches.crear_lote(self._proyecto_id, f"Aceptacion {fecha}")
            for r in procesados:
                self._batches.agregar_documento(lote.id, _documento_de(r).id)
            lote_cerrado = self._batches.cerrar_lote(lote.id)
            ruta_acta = self._reports.generar_acta_cierre_lote(lote.id)

        duplicado_detectado = self._verificar_duplicado(archivos[0])

        criterios_dominio = [
            self._criterio_inventario(resultados, duplicado_detectado),
            self._criterio_extraccion(procesados),
            self._criterio_ocr(procesados),
            self._criterio_normalizacion(procesados),
            self._criterio_markdown(procesados),
            self._criterio_trazabilidad(procesados),
            self._criterio_liberacion(procesados, lote_cerrado, ruta_acta),
        ]

        return InformeAceptacion(
            fecha=fecha,
            corpus_ruta=str(corpus_dir),
            documentos_evaluados=[r.nombre_original for r in resultados],
            criterios_dominio=criterios_dominio,
            criterios_umbral=self._evaluar_umbrales(procesados),
        )

    def _procesar_uno(self, archivo: Path) -> _ResultadoDocumento:
        try:
            documento = self._documents.registrar_documento(proyecto_id=self._proyecto_id, ruta_origen=str(archivo))
            documento = self._documents.clasificar_documento(documento.id)
            documento = self._documents.extraer_documento(documento.id)
            documento = self._documents.revisar_documento(
                documento.id, "equipo de aceptacion", "Revision automatica de la Fase 9 (pruebas de aceptacion)."
            )
            documento = self._documents.normalizar_documento(documento.id)
            self._validity.registrar_fuente(
                documento.id,
                "corpus de aceptacion",
                "Consultor Nexom",
                "Archivo real provisto para la Fase 9 (Documento Maestro, Anexo B, 2026-07-28).",
            )
            self._validity.registrar_vigencia(
                documento.id,
                fecha_emision=None,
                vigente_desde=date.today(),
                vigente_hasta=None,
                sin_vencimiento=True,
                autoridad="Consultor Nexom",
            )
            documento = self._documents.aprobar_para_markdown(
                documento.id, "Consultor Nexom", "Aprobacion automatica de la Fase 9 (pruebas de aceptacion)."
            )
            documento = self._documents.generar_markdown(documento.id)
            documento = self._documents.validar_markdown(documento.id)
            documento = self._documents.liberar_documento(documento.id)
            return _ResultadoDocumento(nombre_original=archivo.name, documento=documento)
        except Exception as exc:  # noqa: BLE001 -- intencional, ver docstring del modulo
            return _ResultadoDocumento(nombre_original=archivo.name, error=str(exc))

    def _releer(self, resultado: _ResultadoDocumento) -> Documento:
        """Vuelve a leer del repositorio el estado MAS RECIENTE del
        documento de `resultado` -- necesario porque, para cuando se
        evaluan Liberacion/umbrales, el documento ya avanzo mas alla
        del ultimo estado que `_procesar_uno()` devolvio."""
        documento_id = _documento_de(resultado).id
        actual = self._documents.obtener_documento(documento_id)
        if actual is None:
            raise ValueError(f"El documento '{documento_id}' desaparecio del repositorio durante la corrida.")
        return actual

    def _verificar_duplicado(self, archivo: Path) -> bool:
        try:
            self._documents.registrar_documento(proyecto_id=self._proyecto_id, ruta_origen=str(archivo))
        except DuplicateDocumentHashError:
            return True
        return False

    def _criterio_inventario(self, resultados: list[_ResultadoDocumento], duplicado_detectado: bool) -> CriterioDominio:
        fallas = []
        for r in resultados:
            if r.error is not None:
                fallas.append(f"{r.nombre_original}: error al procesar ({r.error})")
                continue
            d = _documento_de(r)
            if not d.hash_sha256:
                fallas.append(f"{r.nombre_original}: sin hash_sha256")
            if not Path(d.ruta_copia_original).exists():
                fallas.append(f"{r.nombre_original}: ruta_copia_original no existe en disco")
        if not duplicado_detectado:
            fallas.append("La deteccion de duplicados (Modulo 3) no bloqueo un registro repetido del mismo archivo")
        detalle = (
            f"{len(resultados)} documento(s) evaluado(s); duplicados: "
            f"{'detectados correctamente' if duplicado_detectado else 'FALLA -- no detectados'}."
        )
        if fallas:
            detalle += " Hallazgos: " + "; ".join(fallas)
        return CriterioDominio(dominio="Inventario", descripcion=_DESCRIPCIONES["Inventario"], cumplido=not fallas, detalle=detalle)

    def _criterio_extraccion(self, procesados: list[_ResultadoDocumento]) -> CriterioDominio:
        if not procesados:
            return _criterio_pendiente("Extraccion", "Ningun documento del corpus se proceso con exito.")
        fallas = []
        for r in procesados:
            d = _documento_de(r)
            if not d.ruta_extraccion:
                fallas.append(f"{r.nombre_original}: sin ruta_extraccion")
                continue
            contenido = Path(d.ruta_extraccion).read_text(encoding="utf-8")
            if not contenido.strip():
                fallas.append(f"{r.nombre_original}: extraccion vacia")
            if "�" in contenido:
                fallas.append(f"{r.nombre_original}: contiene caracteres de reemplazo unicode (posible problema de encoding)")
        detalle = f"{len(procesados)} documento(s) evaluado(s) segun su ruta de extraccion (directa/OCR/transcripcion)."
        if fallas:
            detalle += " Hallazgos: " + "; ".join(fallas)
        return CriterioDominio(dominio="Extraccion", descripcion=_DESCRIPCIONES["Extraccion"], cumplido=not fallas, detalle=detalle)

    def _criterio_ocr(self, procesados: list[_ResultadoDocumento]) -> CriterioDominio:
        ocr_docs = [r for r in procesados if r.documento is not None and r.documento.tipo_procesamiento == TipoProcesamiento.OCR]
        if not ocr_docs:
            return _criterio_pendiente(
                "OCR",
                "El corpus todavia no incluye ningun archivo que se clasifique como OCR (PDF escaneado o "
                "imagen) -- ver corpus_aceptacion/README.md.",
            )
        fallas = [f"{r.nombre_original}: sin extraccion OCR" for r in ocr_docs if not (r.documento and r.documento.ruta_extraccion)]
        detalle = f"{len(ocr_docs)} documento(s) procesado(s) por la ruta OCR."
        if fallas:
            detalle += " Hallazgos: " + "; ".join(fallas)
        return CriterioDominio(dominio="OCR", descripcion=_DESCRIPCIONES["OCR"], cumplido=not fallas, detalle=detalle)

    def _criterio_normalizacion(self, procesados: list[_ResultadoDocumento]) -> CriterioDominio:
        if not procesados:
            return _criterio_pendiente("Normalizacion", "Ningun documento del corpus se proceso con exito.")
        fallas = []
        for r in procesados:
            d = _documento_de(r)
            if not d.ruta_normalizado:
                fallas.append(f"{r.nombre_original}: sin ruta_normalizado")
        detalle = (
            f"{len(procesados)} documento(s) normalizado(s); cambios registrados de forma transparente "
            "(Documento.cambios_normalizacion) en todos los casos."
        )
        if fallas:
            detalle += " Hallazgos: " + "; ".join(fallas)
        return CriterioDominio(dominio="Normalizacion", descripcion=_DESCRIPCIONES["Normalizacion"], cumplido=not fallas, detalle=detalle)

    def _criterio_markdown(self, procesados: list[_ResultadoDocumento]) -> CriterioDominio:
        if not procesados:
            return _criterio_pendiente("Markdown", "Ningun documento del corpus se proceso con exito.")
        fallas = []
        for r in procesados:
            d = _documento_de(r)
            if not d.ruta_markdown or not d.hash_markdown:
                fallas.append(f"{r.nombre_original}: sin ruta_markdown/hash_markdown")
                continue
            datos = Path(d.ruta_markdown).read_bytes()
            # Integridad real (incidencia 2026-09-30, CRLF en Windows):
            # no basta con que hash_markdown exista, debe describir los
            # bytes del archivo que se entrega a RAG STUDIO.
            if hashlib.sha256(datos).hexdigest() != d.hash_markdown:
                fallas.append(f"{r.nombre_original}: el SHA-256 del Markdown no coincide con hash_markdown")
                continue
            contenido = datos.decode("utf-8")
            if any(marcador in contenido for marcador in _MARCADORES_PENDIENTES):
                fallas.append(f"{r.nombre_original}: contiene un marcador pendiente ({'/'.join(_MARCADORES_PENDIENTES)})")
        detalle = (
            f"{len(procesados)} documento(s) evaluado(s): UTF-8 valido, hash_markdown presente y coincidente con el archivo, sin marcadores "
            "pendientes. 'YAML valido' de la tabla 8.1 no aplica a esta version de la herramienta -- el "
            "Markdown de entrega no incluye YAML embebido a proposito (ver "
            "domain.documents.entities.FilaManifiesto, seccion 4.6.1)."
        )
        if fallas:
            detalle += " Hallazgos: " + "; ".join(fallas)
        return CriterioDominio(dominio="Markdown", descripcion=_DESCRIPCIONES["Markdown"], cumplido=not fallas, detalle=detalle)

    def _criterio_trazabilidad(self, procesados: list[_ResultadoDocumento]) -> CriterioDominio:
        if not procesados:
            return _criterio_pendiente("Trazabilidad", "Ningun documento del corpus se proceso con exito.")
        fallas = []
        for r in procesados:
            d = _documento_de(r)
            campos = {
                "ruta_copia_original": d.ruta_copia_original,
                "hash_sha256": d.hash_sha256,
                "ruta_extraccion": d.ruta_extraccion,
                "ruta_normalizado": d.ruta_normalizado,
                "ruta_markdown": d.ruta_markdown,
                "hash_markdown": d.hash_markdown,
            }
            faltantes = [nombre for nombre, valor in campos.items() if not valor]
            if faltantes:
                fallas.append(f"{r.nombre_original}: falta {', '.join(faltantes)}")
            if self._validity.obtener_fuente(d.id) is None:
                fallas.append(f"{r.nombre_original}: sin Fuente registrada")
        detalle = (
            f"Recorrido completo verificado para {len(procesados)} documento(s): "
            "original -> extraido -> normalizado -> markdown -> fuente."
        )
        if fallas:
            detalle += " Hallazgos: " + "; ".join(fallas)
        return CriterioDominio(dominio="Trazabilidad", descripcion=_DESCRIPCIONES["Trazabilidad"], cumplido=not fallas, detalle=detalle)

    def _criterio_liberacion(
        self, procesados: list[_ResultadoDocumento], lote_cerrado: Optional[Lote], ruta_acta: str
    ) -> CriterioDominio:
        if not procesados:
            return _criterio_pendiente("Liberacion", "Ningun documento del corpus se proceso con exito.")
        fallas = []
        for r in procesados:
            actual = self._releer(r)
            if actual.estado != EstadoDocumento.LIBERADO:
                fallas.append(f"{r.nombre_original}: no quedo LIBERADO (estado={actual.estado.value})")
            if self._incidents.existen_criticas_abiertas(actual.id):
                fallas.append(f"{r.nombre_original}: tiene incidencias criticas abiertas")
            if not self._documents.listar_aprobaciones(actual.id):
                fallas.append(f"{r.nombre_original}: sin ninguna Aprobacion registrada")
        if lote_cerrado is None or lote_cerrado.estado.value != "cerrado":
            fallas.append("El lote de aceptacion no quedo CERRADO")
        if not ruta_acta or not Path(ruta_acta).exists():
            fallas.append("El acta de cierre de lote no se genero")
        detalle = f"{len(procesados)} documento(s) liberado(s); lote cerrado y acta generada en '{ruta_acta}'."
        if fallas:
            detalle += " Hallazgos: " + "; ".join(fallas)
        return CriterioDominio(dominio="Liberacion", descripcion=_DESCRIPCIONES["Liberacion"], cumplido=not fallas, detalle=detalle)

    def _evaluar_umbrales(self, procesados: list[_ResultadoDocumento]) -> list[CriterioUmbral]:
        documentos = [self._releer(r) for r in procesados]
        liberados = [d for d in documentos if d.estado == EstadoDocumento.LIBERADO]
        total = len(liberados)
        criticos = [d for d in liberados if d.criticidad == Criticidad.CRITICO]

        incidencias_criticas = sum(1 for d in liberados if self._incidents.existen_criticas_abiertas(d.id))
        criticos_vigencia_desconocida = sum(
            1 for d in criticos if vigencia_desconocida(self._validity.obtener_vigencia(d.id))
        )
        con_fuente = sum(1 for d in liberados if self._validity.obtener_fuente(d.id) is not None)
        con_hash = sum(1 for d in liberados if d.hash_sha256)
        criticos_revisados = sum(1 for d in criticos if self._documents.listar_revisiones(d.id))
        con_aprobacion = sum(1 for d in liberados if self._documents.listar_aprobaciones(d.id))

        return [
            CriterioUmbral(
                indicador="Incidencias criticas abiertas",
                umbral_esperado="0",
                valor_observado=str(incidencias_criticas),
                cumplido=incidencias_criticas == 0,
            ),
            CriterioUmbral(
                indicador="Documentos criticos con vigencia desconocida",
                umbral_esperado="0",
                valor_observado=str(criticos_vigencia_desconocida),
                cumplido=criticos_vigencia_desconocida == 0,
            ),
            CriterioUmbral(
                indicador="Markdown con fuente identificada",
                umbral_esperado="100%",
                valor_observado=_pct(con_fuente, total),
                cumplido=(total == 0 or con_fuente == total),
            ),
            CriterioUmbral(
                indicador="Documentos con hash",
                umbral_esperado="100%",
                valor_observado=_pct(con_hash, total),
                cumplido=(total == 0 or con_hash == total),
            ),
            CriterioUmbral(
                indicador="Contenidos criticos revisados",
                umbral_esperado="100%",
                valor_observado=_pct(criticos_revisados, len(criticos)),
                cumplido=(not criticos or criticos_revisados == len(criticos)),
            ),
            CriterioUmbral(
                indicador="Archivos liberados con aprobacion",
                umbral_esperado="100%",
                valor_observado=_pct(con_aprobacion, total),
                cumplido=(total == 0 or con_aprobacion == total),
            ),
        ]
