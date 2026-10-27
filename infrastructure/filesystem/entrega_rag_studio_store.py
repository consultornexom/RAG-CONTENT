"""Adaptador de EntregaRagStudioStore sobre el sistema de archivos local
(ADR-001, seccion 4). Consolida en 14_entrega_rag_studio/ del proyecto
(Documento Maestro, seccion 4.5) una copia del manifiesto de entrega y
de cada Markdown LIBERADO que referencia -- agregado 2026-07-31
(comentario real del consultor: evitar que el operador tenga que ir a
buscar los archivos a 07_markdown/ y 12_exportaciones/ por separado).

Entregas separadas por lote, con version (2026-10-03, NEXOM,
Solicitud_Ajustes_RAG_Content_Lotes_y_Portabilidad.pdf, seccion 3):
hasta esta fecha, `preparar()` escribia SIEMPRE en la misma carpeta raiz
fija, borrandola por completo en cada corrida -- cerrar un lote nuevo
eliminaba sin aviso la entrega de cualquier lote cerrado antes (el caso
real reportado: licenciaturas ya entregadas desaparecian al exportar un
lote nuevo de diplomados). Cuando `preparar()` recibe
`identificador_entrega`, ya no toca la carpeta raiz en absoluto: crea
`<identificador_entrega>/vN/` (N = siguiente version libre para ESE
identificador) y escribe solo ahi. Sin `identificador_entrega` (entrega
de todo el proyecto, `lote_id=None`), el comportamiento es exactamente
el de antes -- compatibilidad hacia atras completa."""
from __future__ import annotations

import csv
import hashlib
import re
import shutil
from pathlib import Path

from domain.documents.exceptions import EntregaIntegridadError
from domain.documents.ports import EntregaRagStudioStore
from domain.documents.rutas import nombre_de_archivo_multiplataforma

_PATRON_VERSION = re.compile(r"^v(\d+)$")


def _siguiente_version(carpeta_identificador: Path) -> str:
    """Escanea las subcarpetas `v1`, `v2`, ... ya presentes (de corridas
    anteriores de ESTE MISMO identificador de entrega) y devuelve la
    siguiente libre. Puramente de lectura del sistema de archivos -- no
    hay ningun contador persistido aparte, igual que el resto de este
    adaptador no lleva ningun registro propio en base de datos."""
    numeros = [
        int(coincidencia.group(1))
        for item in carpeta_identificador.iterdir()
        if item.is_dir() and (coincidencia := _PATRON_VERSION.match(item.name))
    ]
    return f"v{max(numeros, default=0) + 1}"


def _verificar_integridad(carpeta_entrega: Path, nombre_manifiesto: str) -> list[str]:
    """Aplica a la carpeta recien preparada la MISMA verificacion que
    hace RAG STUDIO al importar (contrato de intercambio, seccion 6):
    para cada fila con `hash_contenido`, el SHA-256 de los bytes del
    archivo debe coincidir. Devuelve la lista de hallazgos (vacia si
    todo coincide)."""
    hallazgos: list[str] = []
    with (carpeta_entrega / nombre_manifiesto).open("r", encoding="utf-8-sig", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            esperado = (fila.get("hash_contenido") or "").strip()
            nombre = (fila.get("ruta_archivo") or "").strip()
            titulo = (fila.get("titulo") or "").strip() or nombre
            if not esperado or not nombre:
                continue
            ruta = carpeta_entrega / nombre
            if not ruta.is_file():
                hallazgos.append(f"{titulo}: falta '{nombre}' en la carpeta de entrega")
                continue
            real = hashlib.sha256(ruta.read_bytes()).hexdigest()
            if real != esperado:
                hallazgos.append(f"{titulo} ('{nombre}'): SHA-256 {real[:12]}... distinto del declarado {esperado[:12]}...")
    return hallazgos


class LocalEntregaRagStudioStore(EntregaRagStudioStore):
    def __init__(self, carpeta_entrega: Path):
        self._carpeta_entrega = carpeta_entrega

    def preparar(
        self, ruta_manifiesto: str, rutas_markdown: list[str], identificador_entrega: str | None = None
    ) -> str:
        if identificador_entrega is None:
            # Entrega de TODO el proyecto: la carpeta raiz se mantiene
            # determinista (nunca acumula archivos sueltos de una
            # corrida anterior, mismo criterio que ManifestWriter.
            # escribir()) -- PERO, a diferencia del comportamiento
            # anterior a 2026-10-03, ya NO se borra la carpeta raiz
            # COMPLETA con `rmtree`: eso tambien eliminaba cualquier
            # subcarpeta de entrega por lote que viviera junto a ella
            # (el bug real que motivo este cambio -- exportar la entrega
            # del proyecto completo, o cerrar cualquier lote nuevo,
            # borraba sin aviso la entrega ya hecha de otro lote). Ahora
            # solo se eliminan los ARCHIVOS sueltos de la raiz; las
            # subcarpetas (entregas por lote) nunca se tocan desde esta
            # rama.
            carpeta_destino = self._carpeta_entrega
            if carpeta_destino.exists():
                for item in carpeta_destino.iterdir():
                    if item.is_file() or item.is_symlink():
                        item.unlink()
            carpeta_destino.mkdir(parents=True, exist_ok=True)
        else:
            # Entrega de un lote especifico (2026-10-03): nunca se toca
            # la carpeta raiz ni las entregas de otros lotes/versiones ya
            # existentes -- solo se agrega una subcarpeta de version
            # nueva dentro de <identificador_entrega>/.
            carpeta_identificador = self._carpeta_entrega / identificador_entrega
            carpeta_identificador.mkdir(parents=True, exist_ok=True)
            carpeta_destino = carpeta_identificador / _siguiente_version(carpeta_identificador)
            carpeta_destino.mkdir(parents=True, exist_ok=False)  # nunca sobrescribe una version ya calculada

        shutil.copy2(ruta_manifiesto, carpeta_destino / Path(ruta_manifiesto).name)
        for ruta in rutas_markdown:
            # Mismo nombre que GenerarManifiesto escribe en `ruta_archivo`
            # (antes `Path(ruta).name`, que en macOS/Linux no separa una
            # ruta de Windows y producia otro nombre; auditoria 2026-09-30).
            shutil.copy2(ruta, carpeta_destino / nombre_de_archivo_multiplataforma(ruta))

        # Verificacion del productor (incidencia 2026-09-30): nunca dejar
        # una entrega que RAG STUDIO vaya a rechazar. Si algo no
        # coincide, se elimina la carpeta incompleta (solo ESA version o
        # la raiz, segun el modo) para que el operador no pueda llevarse
        # un lote invalido por error.
        hallazgos = _verificar_integridad(carpeta_destino, Path(ruta_manifiesto).name)
        if hallazgos:
            shutil.rmtree(carpeta_destino, ignore_errors=True)
            raise EntregaIntegridadError(hallazgos)
        return str(carpeta_destino)
