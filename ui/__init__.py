"""Interfaz grafica (PySide6, ADR-001 seccion 7: paquete `ui/` de nivel
superior, "se incorpora incremental cuando exista" -- ver pyproject.toml).

Primer prototipo (2026-07-28): Modulo 8 (revision contra originales) y
un panel minimo de Modulo 10 (incidencias) sobre un documento
seleccionado. `ui` solo importa `application` (nunca `domain` ni
`infrastructure` directamente, ADR-001 seccion 4) salvo por los tipos de
`domain.documents.entities`/`domain.incidents.entities` que expone
`application` en las firmas de sus fachadas -- mismo criterio ya usado
en toda la capa `application`.
"""
