"""Adaptador de ExtractionOutputStore sobre el sistema de archivos
local (ADR-001, seccion 4). Escribe el Markdown del Modulo 5 dentro de
03_extracciones/ del proyecto (Documento Maestro, seccion 4.5).
"""
from __future__ import annotations

from pathlib import Path

from domain.documents.ports import ExtractionOutputStore


class LocalExtractionOutputStore(ExtractionOutputStore):
    def __init__(self, carpeta_extracciones: Path):
        self._carpeta_extracciones = carpeta_extracciones

    def guardar(self, documento_id: str, markdown: str) -> str:
        self._carpeta_extracciones.mkdir(parents=True, exist_ok=True)
        ruta = self._carpeta_extracciones / f"{documento_id}.md"
        # Bytes exactos, nunca `write_text()` en modo texto: en Windows,
        # con newline=None, Python traduce cada "\n" a "\r\n" al escribir.
        # Incidencia real (2026-09-30): un lote generado en Windows se
        # rechazo entero en RAG STUDIO ("su contenido no coincide con el
        # hash declarado") porque `hash_markdown` se calculaba sobre el
        # texto con "\n" y el archivo en disco tenia "\r\n". Escribir
        # bytes hace que el archivo sea identico en cualquier sistema
        # operativo.
        ruta.write_bytes(markdown.encode("utf-8"))
        return str(ruta)
