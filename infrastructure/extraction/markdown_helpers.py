"""Utilidades de normalizacion a Markdown compartidas por varios
extractores (Modulo 5). Adaptadas de RAG STUDIO
(infrastructure/extraction/text_extractors.py: `repair_letter_spaced_text`,
`rows_to_markdown_table`) -- copiadas y ajustadas como codigo propio de
RAG Content Studio Desktop, no importadas en vivo desde el repositorio
de RAG STUDIO (ADR-001, seccion 8: "Nota sobre reutilizacion de codigo
de RAG STUDIO" -- un cambio futuro en RAG STUDIO no debe poder romper
esta herramienta sin relacion causal visible).
"""
from __future__ import annotations

import re

_MIN_LETTER_SPACED_RUN = 4
_MIN_SHORT_RUN_BEFORE_WIDE_GAP = 2
# Puntuacion, no una contrasena -- falso positivo de Bandit (B105).
_LETTER_TOKEN_TRAILING_PUNCTUATION = ".,;:)"  # nosec B105
_UPPERCASE_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9.,])(?=[A-ZÁÉÍÓÚÑ])")


def _is_single_letter_token(token: str) -> bool:
    if len(token) == 1:
        return True
    return len(token) == 2 and token[1] in _LETTER_TOKEN_TRAILING_PUNCTUATION


def repair_letter_spaced_text(text: str, min_run: int = _MIN_LETTER_SPACED_RUN) -> str:
    """Corrige un artefacto real de extraccion de PDFs con pypdf: en
    ciertas fuentes con tracking/justificado amplio, `extract_text()`
    devuelve cada caracter como una "palabra" separada por un espacio
    simple (p. ej. "3 e r . C u a t r i m e s t r e" en vez de "3er.
    Cuatrimestre"). Se detecta como una corrida de `min_run` o mas
    "palabras" de un solo caracter separadas por espacios simples, y se
    unen quitando esos espacios internos; luego se reinserta un espacio
    donde una mayuscula sigue a una minuscula/digito/puntuacion (limite
    de palabra frecuente en Title Case) para recuperar algunos cortes
    de palabra. Mismo criterio que RAG STUDIO -- ver su docstring
    original para el detalle completo de casos limite."""
    lines_out: list[str] = []
    for line in text.split("\n"):
        tokens = line.split(" ")
        repaired: list[str] = []
        i, n = 0, len(tokens)
        while i < n:
            j = i
            while j < n and _is_single_letter_token(tokens[j]):
                j += 1
            run_len = j - i
            followed_by_wide_gap = j < n and tokens[j] == ""
            if run_len >= min_run or (run_len >= _MIN_SHORT_RUN_BEFORE_WIDE_GAP and followed_by_wide_gap):
                joined = "".join(tokens[i:j])
                repaired.append(_UPPERCASE_WORD_BOUNDARY.sub(" ", joined))
            else:
                repaired.extend(tokens[i:j])
            if j < n:
                repaired.append(tokens[j])
                j += 1
            i = j
        lines_out.append(" ".join(repaired))
    return "\n".join(lines_out)


def _escape_cell(value: str) -> str:
    return value.strip().replace("|", "\\|").replace("\n", " ")


def rows_to_markdown_table(rows: list[list[str]]) -> str:
    """Convierte filas de texto plano (encabezado + datos) en una tabla
    Markdown real -- mismo formato exigido por el Modulo 12 (Documento
    Maestro, seccion 4.6.1: "tablas Markdown con | y ---"). Compartida
    por DOCX, XLSX y CSV: las tres fuentes producen "filas de celdas de
    texto", solo cambia de donde vienen."""
    if not rows:
        return ""
    header_cells = [_escape_cell(c) for c in rows[0]]
    lines = ["| " + " | ".join(header_cells) + " |", "|" + "|".join(" --- " for _ in header_cells) + "|"]
    for row in rows[1:]:
        lines.append("| " + " | ".join(_escape_cell(c) for c in row) + " |")
    return "\n".join(lines)
