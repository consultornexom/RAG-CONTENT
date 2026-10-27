"""JSON: no existe en RAG STUDIO (todavia sin extractor de texto propio
alli -- ver Documento Maestro, seccion 4.6.1), asi que este adaptador
es propio de RAG Content Studio Desktop. JSON no tiene una nocion
natural de encabezados/tablas, asi que se reporta como un bloque de
codigo bajo un encabezado con el nombre del archivo -- decision simple
y reversible, marcada para revisarse si algun perfil necesita mapear
claves especificas a estructura Markdown real."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.exceptions import ExtractionFailedError
from domain.documents.ports import DocumentExtractor


class JsonExtractor(DocumentExtractor):
    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # JSON siempre es EXTRACCION_DIRECTA -- el parametro se ignora.
        return formato == FormatoDocumento.JSON

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        # on_progreso se ignora: parsear JSON es inmediato.
        path = Path(ruta)
        # "utf-8-sig": un JSON guardado con BOM (frecuente en Windows) hacia
        # fallar json.loads con "Unexpected UTF-8 BOM" y el documento se
        # rechazaba como "JSON invalido" aunque fuera correcto (auditoria
        # 2026-09-30).
        texto_original = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            datos = json.loads(texto_original)
        except json.JSONDecodeError as exc:
            raise ExtractionFailedError(ruta, f"JSON invalido: {exc}") from exc

        bonito = json.dumps(datos, indent=2, ensure_ascii=False, sort_keys=False)
        markdown = f"## {path.stem}\n\n```json\n{bonito}\n```"
        esta_vacio = datos is None or (isinstance(datos, (dict, list)) and len(datos) == 0)
        advertencias = ["El archivo JSON esta vacio (null, {} o [])."] if esta_vacio else []
        return ResultadoExtraccion(markdown=markdown, metodo="json", advertencias=advertencias)
