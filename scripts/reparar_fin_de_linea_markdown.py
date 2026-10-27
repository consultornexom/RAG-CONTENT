"""Repara los Markdown de entrega generados en Windows por versiones
anteriores a la correccion del 2026-09-30 (incidencia: RAG STUDIO
rechazaba el lote completo con "el archivo fue localizado, pero su
contenido no coincide con el hash declarado en el manifiesto").

Causa: el adaptador escribia el .md con `write_text` en modo texto. En
Windows eso convierte cada "\\n" en "\\r\\n", pero `hash_markdown` se
calculaba sobre el texto con "\\n". El contenido es el mismo; solo
difieren los fines de linea.

Regla de reparacion (estricta):
- Si el SHA-256 del archivo ya coincide con el hash declarado: no se toca.
- Si NO coincide, pero el SHA-256 del archivo con "\\r\\n" convertido a
  "\\n" SI coincide: se reescribe el archivo con "\\n". El hash declarado
  nunca se modifica.
- Cualquier otro caso es una diferencia real de contenido: se informa
  como NO REPARABLE y no se toca.

Solo usa la biblioteca estandar, para poder ejecutarse en el equipo que
recibio el lote aunque no tenga RAG CONTENT STUDIO instalado.

Uso:
    python reparar_fin_de_linea_markdown.py <carpeta> [--aplicar]

<carpeta> puede ser:
- una carpeta de entrega (contiene manifiesto.csv), p. ej.
  14_entrega_rag_studio/ ya copiada al equipo de RAG STUDIO; o
- la carpeta de un proyecto de RAG CONTENT STUDIO (contiene proyecto.db):
  se reparan los archivos de 07_markdown/ con el hash_markdown de cada
  documento. Cierre RAG CONTENT STUDIO antes de ejecutarlo. Despues,
  vuelva a "Preparar entrega" en la aplicacion.

Sin --aplicar solo informa (simulacion). Con --aplicar, antes de
reescribir copia los originales a una carpeta de respaldo con fecha.

Codigos de salida: 0 = al terminar, todos los archivos coinciden con su
hash; 1 = queda alguno sin coincidir (reparable pendiente en simulacion,
NO REPARABLE o faltante); 2 = error de uso."""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_SEPARADOR = re.compile(r"[\\/]+")

OK = "OK"
REPARABLE = "REPARABLE"
NO_REPARABLE = "NO REPARABLE"
FALTANTE = "FALTANTE"


@dataclass
class Revision:
    etiqueta: str
    ruta: Path
    hash_declarado: str
    estado: str = ""


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _nombre_base(ruta: str) -> str:
    segmentos = [s for s in _SEPARADOR.split(ruta.strip()) if s]
    return segmentos[-1] if segmentos else ""


def clasificar(revision: Revision) -> str:
    if not revision.ruta.is_file():
        return FALTANTE
    datos = revision.ruta.read_bytes()
    if _sha256(datos) == revision.hash_declarado:
        return OK
    if b"\r\n" in datos and _sha256(datos.replace(b"\r\n", b"\n")) == revision.hash_declarado:
        return REPARABLE
    return NO_REPARABLE


def _ruta_en_entrega(carpeta: Path, ruta_archivo: str, version: str) -> Path | None:
    """Archivo al que apunta una fila del manifiesto, con las mismas reglas
    que RAG STUDIO (contrato, seccion 5): en V2, ruta relativa POSIX dentro
    de la carpeta (nunca absoluta, con "\\" ni con ".."); en V1/legado,
    solo el nombre de archivo. Devuelve None si la ruta no es segura: este
    script escribe archivos y nunca debe salir de la carpeta indicada."""
    ruta_archivo = ruta_archivo.strip()
    if version.strip() == "2":
        if (
            not ruta_archivo
            or "\\" in ruta_archivo
            or ruta_archivo.startswith(("/", "~"))
            or (len(ruta_archivo) >= 2 and ruta_archivo[1] == ":")
            or ".." in ruta_archivo.split("/")
        ):
            return None
        candidato = carpeta / ruta_archivo
    else:
        nombre = _nombre_base(ruta_archivo)
        if not nombre:
            return None
        candidato = carpeta / nombre
    raiz = carpeta.resolve()
    resuelto = candidato.resolve()
    if raiz != resuelto and raiz not in resuelto.parents:
        return None
    return candidato


def revisiones_de_entrega(carpeta: Path) -> list[Revision]:
    revisiones = []
    # "utf-8-sig": tolera el BOM que agrega Excel si alguien abrio y guardo el manifiesto.
    with (carpeta / "manifiesto.csv").open("r", encoding="utf-8-sig", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            hash_declarado = (fila.get("hash_contenido") or "").strip().lower()
            ruta_archivo = fila.get("ruta_archivo") or ""
            if not hash_declarado or not ruta_archivo.strip():
                continue
            etiqueta = (fila.get("titulo") or "").strip() or ruta_archivo.strip()
            ruta = _ruta_en_entrega(carpeta, ruta_archivo, fila.get("manifest_schema_version") or "")
            if ruta is None:
                revisiones.append(Revision(etiqueta, carpeta / "(ruta no segura)", hash_declarado, NO_REPARABLE))
                continue
            revisiones.append(Revision(etiqueta, ruta, hash_declarado))
    return revisiones


def revisiones_de_proyecto(carpeta: Path) -> list[Revision]:
    uri = (carpeta / "proyecto.db").resolve().as_uri() + "?mode=ro"
    conexion = sqlite3.connect(uri, uri=True)
    try:
        filas = conexion.execute(
            "SELECT nombre_original, ruta_markdown, hash_markdown FROM documentos "
            "WHERE ruta_markdown IS NOT NULL AND hash_markdown IS NOT NULL"
        ).fetchall()
    finally:
        conexion.close()
    revisiones = []
    for nombre_original, ruta_markdown, hash_markdown in filas:
        nombre = _nombre_base(ruta_markdown)
        if nombre:
            revisiones.append(Revision(nombre_original, carpeta / "07_markdown" / nombre, hash_markdown.lower()))
    return revisiones


def _reescribir_con_lf(ruta: Path) -> None:
    datos = ruta.read_bytes().replace(b"\r\n", b"\n")
    temporal = ruta.with_name(ruta.name + ".tmp_reparacion")
    temporal.write_bytes(datos)
    os.replace(temporal, ruta)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("carpeta", help="carpeta de entrega (con manifiesto.csv) o carpeta de proyecto (con proyecto.db)")
    parser.add_argument("--aplicar", action="store_true", help="reescribe los archivos reparables (sin esto, solo simula)")
    args = parser.parse_args(argv)
    # En consolas de Windows con codificacion antigua, un titulo con un
    # caracter no representable no debe abortar el informe.
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar is not None:
        reconfigurar(errors="replace")

    carpeta = Path(args.carpeta)
    if (carpeta / "manifiesto.csv").is_file():
        modo = "entrega"
        revisiones = revisiones_de_entrega(carpeta)
        carpeta_base = carpeta
        carpeta_respaldo = carpeta.parent / f"{carpeta.name}_respaldo_crlf_{datetime.now():%Y%m%d_%H%M%S_%f}"
    elif (carpeta / "proyecto.db").is_file():
        modo = "proyecto"
        revisiones = revisiones_de_proyecto(carpeta)
        carpeta_base = carpeta / "07_markdown"
        carpeta_respaldo = carpeta / f"_respaldo_crlf_{datetime.now():%Y%m%d_%H%M%S_%f}" / "07_markdown"
    else:
        print(f"ERROR: '{carpeta}' no contiene manifiesto.csv ni proyecto.db.", file=sys.stderr)
        return 2

    for revision in revisiones:
        if not revision.estado:
            revision.estado = clasificar(revision)

    # Dos filas que apuntan al mismo archivo con hashes declarados distintos:
    # RAG STUDIO rechaza ambas como ambiguas y reparar a favor de una
    # cambiaria lo que describe la otra. No se toca ninguna.
    hashes_por_ruta: dict[Path, set[str]] = {}
    for revision in revisiones:
        hashes_por_ruta.setdefault(revision.ruta.resolve(), set()).add(revision.hash_declarado)
    for revision in revisiones:
        if len(hashes_por_ruta[revision.ruta.resolve()]) > 1:
            revision.estado = NO_REPARABLE

    print(f"Modo: {modo} -- {carpeta}")
    print(f"{'Aplicando cambios' if args.aplicar else 'SIMULACION (use --aplicar para reparar)'}\n")
    for revision in revisiones:
        print(f"  [{revision.estado:<12}] {revision.etiqueta} ({revision.ruta.name})")

    # Un archivo se repara y respalda una sola vez aunque lo citen varias
    # filas: si no, la segunda copia de respaldo pisaria el original con
    # la version ya reparada.
    reparables_por_ruta: dict[Path, Revision] = {}
    for revision in revisiones:
        if revision.estado == REPARABLE:
            reparables_por_ruta.setdefault(revision.ruta.resolve(), revision)
    reparables = list(reparables_por_ruta.values())

    if args.aplicar and reparables:
        carpeta_respaldo.mkdir(parents=True, exist_ok=False)
        for revision in reparables:
            destino_respaldo = carpeta_respaldo / revision.ruta.relative_to(carpeta_base)
            destino_respaldo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(revision.ruta, destino_respaldo)
            _reescribir_con_lf(revision.ruta)
        # Verificacion posterior de TODAS las filas: nunca se da por
        # reparado sin comprobarlo.
        for revision in revisiones:
            if revision.estado in (REPARABLE, OK):
                revision.estado = clasificar(revision)
        print(f"\nRespaldo de los originales: {carpeta_respaldo}")

    total_ok = sum(r.estado == OK for r in revisiones)
    print(
        f"\nResumen: {len(revisiones)} archivo(s) | coinciden {total_ok} | "
        f"reparables pendientes {sum(r.estado == REPARABLE for r in revisiones)} | "
        f"no reparables {sum(r.estado == NO_REPARABLE for r in revisiones)} | "
        f"faltantes {sum(r.estado == FALTANTE for r in revisiones)}"
    )
    if modo == "proyecto" and args.aplicar and reparables:
        print("Siguiente paso: abra el proyecto en RAG CONTENT STUDIO y vuelva a preparar la entrega a RAG STUDIO.")
    return 0 if total_ok == len(revisiones) else 1


if __name__ == "__main__":
    sys.exit(main())
