"""Pruebas para ui.errores.mensaje_amigable (bug real 2026-07-30: el
usuario de Windows reporto un `PermissionError` crudo al generar reportes
-- ver bitacora del Documento Maestro). A diferencia del resto de `ui/`,
este modulo no importa PySide6, asi que si puede ejecutarse en cualquier
entorno, incluyendo uno sin librerias graficas."""
from __future__ import annotations

from ui.errores import mensaje_amigable


def test_permission_error_produce_mensaje_accionable_con_el_nombre_del_archivo() -> None:
    exc = PermissionError(13, "Permission denied")
    exc.filename = r"C:\Usuarios\aleja\RAG Content Studio Desktop\proyectos\PROY-0519\10_reportes\informe_inventario.csv"

    mensaje = mensaje_amigable(exc)

    assert exc.filename in mensaje
    assert "abierto en otro programa" in mensaje
    assert "solo lectura" in mensaje
    # No debe mostrarse el texto crudo de Python al usuario.
    assert "Errno" not in mensaje


def test_permission_error_sin_nombre_de_archivo_no_falla() -> None:
    exc = PermissionError("Permission denied")

    mensaje = mensaje_amigable(exc)

    assert "el archivo" in mensaje


def test_otras_excepciones_se_comportan_igual_que_antes() -> None:
    exc = ValueError("fecha invalida: 2026-13-40")

    assert mensaje_amigable(exc) == str(exc)


def test_otro_oserror_que_no_es_permission_error_se_comporta_igual_que_antes() -> None:
    exc = FileNotFoundError(2, "No such file or directory")

    assert mensaje_amigable(exc) == str(exc)
