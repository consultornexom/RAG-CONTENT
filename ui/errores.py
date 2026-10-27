"""Utilidad para presentar errores al usuario (Documento Maestro, seccion
4.11.1: "baja friccion" -- un mensaje de error debe decirle al usuario que
hacer a continuacion, no solo repetir el texto crudo de una excepcion de
Python).

Bug real reportado 2026-07-30 por el usuario de Windows: al fallar la
escritura de un archivo (reportes, Markdown, manifiestos, etc.) por un
error de permisos de Windows, la aplicacion mostraba el texto crudo de
`PermissionError` tal cual lo entrega Python -- por ejemplo:

    [Errno 13] Permission denied: 'C:\\Usuarios\\aleja\\RAG Content
    Studio Desktop\\proyectos\\PROY-0519...\\10_reportes\\informe_
    inventario.csv'

Ese texto no le dice al usuario que puede hacer al respecto. La causa mas
comun de un `PermissionError` al escribir un archivo en Windows (cuando el
codigo Python solo abre el archivo en modo escritura y lo cierra de
inmediato, sin dejar el descriptor abierto ni leerlo -- que es el caso de
todos los escritores de esta herramienta) es que el archivo esta bloqueado
por otro programa que lo tiene abierto (tipicamente Excel, si el usuario
abrio un reporte .csv anterior), o que el archivo quedo con el atributo de
"solo lectura" activado (por ejemplo, tras copiarlo desde un respaldo o un
zip). `mensaje_amigable()` detecta especificamente ese caso y devuelve una
explicacion accionable en espanol; para cualquier otra excepcion se
comporta igual que el `str(exc)` que se usaba antes, sin cambiar nada.
"""
from __future__ import annotations


def mensaje_amigable(exc: Exception) -> str:
    """Traduce una excepcion a un mensaje que le diga al usuario que hacer.

    Con `PermissionError` (el caso reportado en Windows), agrega una
    explicacion de las dos causas mas probables y que hacer en cada caso.
    Para cualquier otra excepcion, devuelve `str(exc)` sin modificar --
    mismo comportamiento que antes de este ajuste."""
    if isinstance(exc, PermissionError):
        nombre_archivo = exc.filename or "el archivo"
        return (
            f"No se pudo escribir '{nombre_archivo}' porque el sistema "
            "operativo denego el permiso.\n\n"
            "Las causas mas comunes son: (1) el archivo esta abierto en "
            "otro programa (por ejemplo, Excel) -- cierrelo e intente de "
            "nuevo; o (2) el archivo o la carpeta tienen activado el "
            "atributo de solo lectura -- quiteselo desde las propiedades "
            "del archivo/carpeta en el explorador de Windows."
        )
    return str(exc)
