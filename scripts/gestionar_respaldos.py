"""Punto de entrada de la Fase 10 (Documento Maestro, seccion 9:
"Respaldos cifrados y pruebas de restauracion"; ADR-001, seccion 14.3) --
crea o restaura respaldos cifrados de un proyecto real, ya que la GUI
(Fase 11) todavia no tiene una pantalla para esto.

Uso:
    python scripts/gestionar_respaldos.py listar
    python scripts/gestionar_respaldos.py crear <PROY-0000>
    python scripts/gestionar_respaldos.py restaurar <PROY-0000> <ruta_archivo.zip.enc> <carpeta_destino>

A diferencia de `scripts/ejecutar_pruebas_aceptacion.py` (Fase 9, que
usa una raiz aislada a proposito para no tocar los proyectos reales del
consultor), este script opera sobre la ruta raiz REAL confirmada
(Documento Maestro, seccion 4.1): crear o restaurar el respaldo de un
proyecto que no existe no tiene ningun sentido -- por definicion, esta
es una operacion sobre datos reales, no una prueba."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

_RAIZ_REPO = Path(__file__).resolve().parent.parent


def _importar() -> tuple[Callable[..., Any], Callable[..., Any]]:
    try:
        from app.bootstrap import abrir_proyecto, bootstrap
    except ImportError:
        sys.path.insert(0, str(_RAIZ_REPO))
        from app.bootstrap import abrir_proyecto, bootstrap
    return abrir_proyecto, bootstrap


def _listar(ctx: Any) -> int:
    proyectos = ctx.projects.listar_proyectos()
    if not proyectos:
        print("No hay proyectos registrados todavia.")
        return 0
    for proyecto in proyectos:
        print(f"{proyecto.id}\t{proyecto.nombre}\t{proyecto.ruta_carpeta}")
    return 0


def _crear(ctx: Any, abrir_proyecto: Callable[..., Any], proyecto_id: str) -> int:
    proyecto = ctx.projects.obtener_proyecto(proyecto_id)
    if proyecto is None:
        print(f"No existe ningun proyecto con id '{proyecto_id}'.")
        return 1
    pctx = abrir_proyecto(ctx, proyecto)
    respaldo = pctx.security.crear_respaldo(proyecto.id, Path(proyecto.ruta_carpeta))
    print(f"Respaldo creado: {respaldo.ruta_archivo}")
    print(f"Hash SHA-256 (archivo cifrado): {respaldo.hash_sha256}")
    print(f"Tamano: {respaldo.tamano_bytes} bytes")
    return 0


def _restaurar(ctx: Any, abrir_proyecto: Callable[..., Any], proyecto_id: str, ruta_archivo: str, destino: str) -> int:
    proyecto = ctx.projects.obtener_proyecto(proyecto_id)
    if proyecto is None:
        print(f"No existe ningun proyecto con id '{proyecto_id}'.")
        return 1
    pctx = abrir_proyecto(ctx, proyecto)
    restauracion = pctx.security.restaurar_respaldo(proyecto.id, Path(ruta_archivo), Path(destino))
    if not restauracion.exitosa:
        print(f"Restauracion NO exitosa: {restauracion.detalle}")
        return 1
    print(f"Restauracion exitosa en: {restauracion.ruta_destino}")
    return 0


def main() -> int:
    abrir_proyecto, bootstrap = _importar()

    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    accion = sys.argv[1]

    # Hallazgo de la tercera auditoria general (2026-07-31): este script
    # no capturaba errores especificos del dominio (por ejemplo
    # `ClaveDeRespaldoNoEncontradaError` al restaurar un respaldo sin
    # clave guardada en el almacen de credenciales, o un archivo/carpeta
    # invalidos) -- dejaba pasar un traceback completo de Python en vez
    # de mostrar el mensaje ya claro y accionable que esas excepciones
    # de dominio traen consigo (ver `domain/security/exceptions.py`).
    # `str(exc)` es suficiente aqui (a diferencia de `mensaje_amigable`
    # usado en la UI): los mensajes de las excepciones de dominio de
    # este contexto ya estan redactados en espanol y son accionables por
    # si mismos, y este script no debe depender de `ui` (ADR-001,
    # seccion 4: `scripts` no es una de las capas de esa tabla, pero
    # acoplarlo a `ui` de todas formas mezclaria un punto de entrada de
    # linea de comandos con el paquete de la interfaz grafica).
    try:
        ctx = bootstrap()

        if accion == "listar":
            return _listar(ctx)
        if accion == "crear":
            if len(sys.argv) != 3:
                print("Uso: python scripts/gestionar_respaldos.py crear <PROY-0000>")
                return 1
            return _crear(ctx, abrir_proyecto, sys.argv[2])
        if accion == "restaurar":
            if len(sys.argv) != 5:
                print(
                    "Uso: python scripts/gestionar_respaldos.py restaurar "
                    "<PROY-0000> <ruta_archivo.zip.enc> <carpeta_destino>"
                )
                return 1
            return _restaurar(ctx, abrir_proyecto, sys.argv[2], sys.argv[3], sys.argv[4])
    except Exception as exc:  # se muestra al usuario, no se deja pasar como traceback crudo
        print(f"Error: {exc}")
        return 1

    print(f"Accion desconocida: '{accion}'. Use 'listar', 'crear' o 'restaurar'.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
