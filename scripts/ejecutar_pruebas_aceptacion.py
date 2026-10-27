"""Punto de entrada de la Fase 9 (Documento Maestro, secciones 8.1 y
8.2): corre las pruebas minimas por dominio y los umbrales recomendados
de liberacion sobre el corpus real de `corpus_aceptacion/documentos/`.

Uso:
    python scripts/ejecutar_pruebas_aceptacion.py

Deliberadamente NO usa la ruta raiz real de datos que resuelve
`app.configuration.cargar_rutas()` (la carpeta de proyectos del
consultor): esta corrida crea un proyecto nuevo en cada ejecucion
("Aceptacion <fecha>") solo para procesar el corpus, y mezclarlo con
los proyectos reales del consultor lo iria ensuciando en cada corrida,
sin ninguna forma de limpiarlo desde la GUI todavia (el "borrar
proyecto" no existe en esta version). En vez de eso, se usa una raiz
propia y aislada, `corpus_aceptacion/_runtime/`, con su propia
`aplicacion.db` -- persiste entre corridas (para poder inspeccionar
corridas anteriores si hace falta) pero nunca toca los datos reales.

Esta es la razon por la que la Fase 9 se considera "distinta de la
suite de pytest de este propio codigo" (ver README): el resultado que
importa es el informe humano-legible en `corpus_aceptacion/informes/`,
revisado por una persona, no un pass/fail automatico de CI."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

_RAIZ_REPO = Path(__file__).resolve().parent.parent
_RAIZ_ACEPTACION = _RAIZ_REPO / "corpus_aceptacion" / "_runtime"
_CORPUS_DOCUMENTOS = _RAIZ_REPO / "corpus_aceptacion" / "documentos"
_CORPUS_INFORMES = _RAIZ_REPO / "corpus_aceptacion" / "informes"


def _preparar_raiz_aceptacion() -> None:
    """Crea la raiz aislada de aceptacion la primera vez, copiando el
    perfil generico -- mismo patron que los fixtures de
    `tests/smoke/test_*_extremo_a_extremo.py`."""
    perfiles_dir = _RAIZ_ACEPTACION / "perfiles" / "perfil_generico"
    perfiles_dir.mkdir(parents=True, exist_ok=True)
    origen = _RAIZ_REPO / "perfiles" / "perfil_generico" / "0.1.yaml"
    destino = perfiles_dir / "0.1.yaml"
    if not destino.exists():
        shutil.copy(origen, destino)


def main() -> int:
    try:
        from app.bootstrap import abrir_proyecto, bootstrap
        from application.acceptance.service import AcceptanceService
        from infrastructure.filesystem.markdown_informe_aceptacion_writer import MarkdownInformeAceptacionWriter
    except ImportError:
        sys.path.insert(0, str(_RAIZ_REPO))
        from app.bootstrap import abrir_proyecto, bootstrap
        from application.acceptance.service import AcceptanceService
        from infrastructure.filesystem.markdown_informe_aceptacion_writer import MarkdownInformeAceptacionWriter

    if not _CORPUS_DOCUMENTOS.exists() or not any(_CORPUS_DOCUMENTOS.rglob("*")):
        print(
            f"El corpus '{_CORPUS_DOCUMENTOS}' esta vacio -- agrega al menos un archivo representativo "
            "antes de correr este script (ver corpus_aceptacion/README.md)."
        )
        return 1

    _preparar_raiz_aceptacion()

    # Hallazgo de la tercera auditoria general (2026-07-31): este script
    # no capturaba errores especificos del dominio (por ejemplo, un
    # perfil YAML corrupto en corpus_aceptacion/_runtime/perfiles/, o un
    # documento del corpus que el extractor no puede abrir) -- dejaba
    # pasar un traceback completo de Python en vez de mostrar el mensaje
    # ya claro que esas excepciones de dominio traen consigo. `str(exc)`
    # es suficiente aqui (mismo criterio que en
    # `scripts/gestionar_respaldos.py`): este script no debe depender de
    # `ui` solo para formatear un mensaje de error de linea de comandos.
    try:
        ctx = bootstrap(raiz=str(_RAIZ_ACEPTACION))
        proyecto = ctx.projects.crear_proyecto(nombre="Aceptacion Fase 9", perfil_id="perfil_generico")
        pctx = abrir_proyecto(ctx, proyecto)

        acceptance = AcceptanceService(
            pctx.documents, pctx.validity, pctx.incidents, pctx.batches, pctx.reports, proyecto.id
        )
        informe = acceptance.ejecutar_pruebas_de_aceptacion(_CORPUS_DOCUMENTOS)

        writer = MarkdownInformeAceptacionWriter(_CORPUS_INFORMES)
        ruta_informe = writer.escribir(informe)
    except Exception as exc:  # se muestra al usuario, no se deja pasar como traceback crudo
        print(f"Error: {exc}")
        return 1

    print(f"Informe de aceptacion escrito en: {ruta_informe}")
    print(f"Resultado general: {'APROBADO' if informe.aprobado() else 'CON HALLAZGOS'}")
    print(f"Corpus completo (7 dominios de la seccion 8.1): {'si' if informe.esta_completo() else 'no'}")
    return 0 if informe.aprobado() else 1


if __name__ == "__main__":
    raise SystemExit(main())
