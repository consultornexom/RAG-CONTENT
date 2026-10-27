"""Funcion pura del Modulo 12 (Generador de Markdown): detecta si un
Markdown tiene al menos un encabezado real (`#`, `##`, ...) o una tabla
Markdown real (fila de encabezado + fila separadora `---`) -- exactamente
la estructura que, segun el Documento Maestro (seccion 4.6.1, "contrato
de salida confirmado con RAG STUDIO"), RAG STUDIO usa para fragmentar
por encabezado o por tabla al registrar una fuente.

No es una regla bloqueante: un documento sin esa estructura sigue
pudiendo liberarse (por ejemplo, un memo de un solo parrafo), solo que
RAG STUDIO lo tratara como un unico bloque al fragmentarlo. Quien usa
esta funcion (application.documents.commands.validar_markdown.
ValidarMarkdown) decide que hacer con el resultado -- aqui solo se
detecta, igual que domain.documents.verificacion_fechas_cifras solo
detecta fechas/cifras sin validarlas."""
from __future__ import annotations

import re

_PATRON_ENCABEZADO = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_PATRON_FILA_TABLA = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_PATRON_FILA_SEPARADORA = re.compile(r"^\s*\|?[\s:-]*-[\s:-]*\|[\s:|-]*\s*$", re.MULTILINE)


def tiene_estructura_markdown(markdown: str) -> bool:
    """True si `markdown` contiene al menos un encabezado real o una
    tabla Markdown real (fila con `|` seguida de una fila separadora
    tipo `---|---`); False si no se encontro ninguna de las dos."""
    if _PATRON_ENCABEZADO.search(markdown):
        return True
    if _PATRON_FILA_TABLA.search(markdown) and _PATRON_FILA_SEPARADORA.search(markdown):
        return True
    return False
