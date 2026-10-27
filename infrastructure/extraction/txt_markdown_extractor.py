"""TXT y Markdown: se leen directamente, sin transformacion -- el
Modulo 12 exige exactamente este comportamiento para la entrega final
(Documento Maestro, seccion 4.6.1: "RAG STUDIO no interpreta
encabezados YAML... los tipos TXT y Markdown se leen como texto
literal completo"), y aplicarlo tambien aqui, desde el Modulo 5, evita
tener que "deshacer" cualquier transformacion mas adelante.

Nota sobre lectura completa en memoria, aclarada 2026-07-31 (segunda
auditoria general): a diferencia de
`infrastructure.filesystem.original_file_store._hash_sha256_de()` (que
si lee por bloques de 1 MiB), aqui se usa `Path.read_text()` de un solo
golpe -- es una decision DELIBERADA, no un descuido que rompe la
uniformidad de criterio del proyecto: calcular un hash es incremental
por naturaleza (cada bloque actualiza el digest y se puede descartar),
pero `ResultadoExtraccion.markdown` exige el contenido COMPLETO como un
solo string (el contrato del Modulo 12 de arriba); leer por bloques y
concatenarlos no ahorraria memoria, terminaria igual con el archivo
entero materializado antes de poder devolverlo. Sin limite de tamano
por diseño (alcance del proyecto: documentos para RAG, no volcados de
GB) -- si algun dia se necesita procesar archivos de texto
excepcionalmente grandes, la solucion real seria un
`ResultadoExtraccion` que acepte streaming, no leer este archivo en
bloques.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.ports import DocumentExtractor

_SOPORTADOS = {FormatoDocumento.TXT, FormatoDocumento.MARKDOWN}


class TxtMarkdownExtractor(DocumentExtractor):
    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # TXT/Markdown siempre son EXTRACCION_DIRECTA (Modulo 4) -- no hay
        # ambiguedad de ruta, el parametro se ignora.
        return formato in _SOPORTADOS

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        # on_progreso se ignora: leer un archivo de texto es inmediato.
        # "utf-8-sig" descarta la marca BOM que agregan muchos editores de
        # Windows (p. ej. el Bloc de notas). Con "utf-8" el BOM quedaba como
        # caracter U+FEFF al inicio del Markdown entregado: un "# Titulo"
        # inicial dejaba de reconocerse como encabezado y viajaba a RAG
        # STUDIO dentro del primer fragmento (auditoria 2026-09-30).
        texto = Path(ruta).read_text(encoding="utf-8-sig", errors="replace")
        metodo = "texto_plano" if formato == FormatoDocumento.TXT else "markdown"
        advertencias = [] if texto.strip() else ["El archivo esta vacio."]
        return ResultadoExtraccion(markdown=texto, metodo=metodo, advertencias=advertencias)
