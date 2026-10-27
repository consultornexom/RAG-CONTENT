"""Paleta de colores y hoja de estilos (QSS) de la interfaz.

Se agrega 2026-07-29, a pedido explicito del consultor, tras analizar
si un esquema de color afecta el rendimiento de la herramienta: no lo
hace (ver README, entrada de esta misma fecha) -- la interfaz no tenia
hasta ahora ningun `setStyleSheet()`/`QPalette` propio, solo el tema por
defecto del sistema operativo, y esta app no tiene ningun bucle de
repintado continuo que un color pudiera encarecer (se confirmo
revisando `ui/app.py`: el unico `QTimer` es un `singleShot` para el
maximizado al arrancar, no un refresco periodico).

Dos piezas, pensadas para que "cada seccion y la informacion se
perciban muy bien a la vista del usuario":

1. `HOJA_DE_ESTILOS`: QSS aplicado UNA SOLA VEZ sobre `QApplication`
   (ver `ui.app.main()`) -- da a toda la ventana una identidad visual
   consistente (barra de navegacion, botones, tablas, encabezados,
   tarjetas de la pantalla principal) sin tocar ningun widget
   individual.
2. `color_para_estado()`: mapea el `.value` de CUALQUIERA de los cinco
   enums de estado de esta aplicacion (`EstadoDocumento`,
   `EstadoTrabajo`, `EstadoIncidencia`, `EstadoLote`, `EstadoProyecto`)
   a un color semantico -- exito (verde), atencion (ambar), en proceso
   (azul) o bloqueo (rojo) -- para reforzar visualmente el texto del
   estado (nunca reemplazarlo: el texto siempre sigue ahi, el color es
   un refuerzo, no la unica senal -- accesibilidad basica para
   variaciones de percepcion del color). Los 34 valores posibles se
   confirmaron leyendo las cinco entidades reales antes de armar el
   mapa, no se adivino ninguno; los que no aparecen en ningun conjunto
   de abajo son pasos intermedios normales del flujo (Documento
   Maestro, seccion 4.7) sin alerta -- se dejan sin color especial a
   proposito, para que las filas que si necesitan destacar (exito,
   atencion, bloqueo) resalten por contraste en vez de competir con una
   tabla donde cada fila tiene un color distinto.

Misma paleta de marca (azules) que ya usa
`DOCS PROYECTO/Manual_de_Usuario_RAG_Content_Studio_Desktop.docx` (ver
su generador, `build.js`), para que el manual y la aplicacion se vean
consistentes entre si."""
from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTableWidgetItem

# -- Colores de marca (identicos al manual de usuario) -----------------
AZUL_OSCURO = "#1F3864"
AZUL_MEDIO = "#2E5395"
AZUL_OSCURO_HOVER = "#16294A"

# -- Neutrales -----------------------------------------------------------
GRIS_FONDO_VENTANA = "#F4F6F9"
GRIS_FONDO_TARJETA = "#FFFFFF"
GRIS_BORDE = "#D6DCE5"
GRIS_TEXTO = "#2B2F36"
BLANCO = "#FFFFFF"

# -- Colores semanticos de estado (texto + fondo suave de la celda) -----
VERDE_EXITO = "#2E7D32"
VERDE_EXITO_FONDO = "#E8F5E9"
AMBAR_ATENCION = "#B45309"
AMBAR_ATENCION_FONDO = "#FEF3E2"
AZUL_PROCESO = "#1565C0"
AZUL_PROCESO_FONDO = "#E3F2FD"
ROJO_BLOQUEO = "#C62828"
ROJO_BLOQUEO_FONDO = "#FDECEA"

# -- Categorias semanticas de estado ------------------------------------
# Confirmados leyendo domain.documents.entities.EstadoDocumento (18
# valores), domain.jobs.entities.EstadoTrabajo (7),
# domain.incidents.entities.EstadoIncidencia (5),
# domain.batches.entities.EstadoLote (2) y
# domain.projects.entities.EstadoProyecto (2) -- 34 valores en total,
# todos distintos entre si.
_EXITO = {"liberado", "validado", "completado", "resuelta", "cerrado", "archivado"}
_ATENCION = {
    "pendiente_de_aprobacion",
    "observado",
    "pendiente",
    "pausado",
    "abierta",
    "asignada",
    "respondida",
    "abierto",
}
_EN_PROCESO = {"en_extraccion", "en_revision", "en_normalizacion", "preparando", "ejecutando"}
_BLOQUEO = {"bloqueado", "descartado", "obsoleto", "fallido", "cancelado", "bloqueada"}
# El resto -- recibido, inventariado, clasificado, extraido, revisado,
# normalizado, aprobado_para_markdown, markdown_generado, activo --
# son pasos intermedios normales o el estado mas comun (un proyecto
# "activo"): se dejan sin color especial, ver docstring del modulo.


def color_para_estado(valor_estado: str) -> tuple[str, str] | None:
    """Devuelve (color_de_texto, color_de_fondo) en hexadecimal para
    `valor_estado`, o None si no amerita un color especial (ver arriba).
    """
    if valor_estado in _EXITO:
        return VERDE_EXITO, VERDE_EXITO_FONDO
    if valor_estado in _ATENCION:
        return AMBAR_ATENCION, AMBAR_ATENCION_FONDO
    if valor_estado in _EN_PROCESO:
        return AZUL_PROCESO, AZUL_PROCESO_FONDO
    if valor_estado in _BLOQUEO:
        return ROJO_BLOQUEO, ROJO_BLOQUEO_FONDO
    return None


def aplicar_color_estado(item: QTableWidgetItem, valor_estado: str) -> None:
    """Colorea `item` (una celda de estado ya creada con
    `QTableWidgetItem(valor_estado)`) segun `color_para_estado()`. No
    hace nada si el estado no tiene un color especial asignado -- la
    celda conserva el estilo por defecto de la tabla."""
    colores = color_para_estado(valor_estado)
    if colores is None:
        return
    color_texto, color_fondo = colores
    item.setForeground(QBrush(QColor(color_texto)))
    item.setBackground(QBrush(QColor(color_fondo)))


HOJA_DE_ESTILOS = f"""
QMainWindow, QDialog {{
    background-color: {GRIS_FONDO_VENTANA};
}}

QWidget {{
    color: {GRIS_TEXTO};
}}

/* -- Barra de navegacion (modo avanzado) -- */
QListWidget {{
    background-color: {BLANCO};
    border: 1px solid {GRIS_BORDE};
    border-radius: 4px;
    outline: 0;
}}

QListWidget::item {{
    padding: 6px 8px;
}}

QListWidget::item:selected {{
    background-color: {AZUL_MEDIO};
    color: {BLANCO};
}}

QListWidget::item:hover:!selected {{
    background-color: #E7ECF5;
}}

/* -- Botones -- */
QPushButton {{
    background-color: {AZUL_MEDIO};
    color: {BLANCO};
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
}}

QPushButton:hover {{
    background-color: {AZUL_OSCURO};
}}

QPushButton:pressed {{
    background-color: {AZUL_OSCURO_HOVER};
}}

QPushButton:disabled {{
    background-color: #A9B4C4;
    color: #EEF1F5;
}}

/* -- Tablas -- */
QTableWidget {{
    background-color: {BLANCO};
    alternate-background-color: #F7F9FC;
    gridline-color: {GRIS_BORDE};
    border: 1px solid {GRIS_BORDE};
    border-radius: 4px;
    selection-background-color: {AZUL_MEDIO};
    selection-color: {BLANCO};
}}

QHeaderView::section {{
    background-color: {AZUL_OSCURO};
    color: {BLANCO};
    padding: 4px 6px;
    border: none;
    border-right: 1px solid {AZUL_MEDIO};
}}

/* -- Tarjetas de la pantalla principal y agrupadores de formularios -- */
QGroupBox {{
    background-color: {GRIS_FONDO_TARJETA};
    border: 1px solid {GRIS_BORDE};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: {AZUL_OSCURO};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}

/* -- Campos de entrada -- */
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit {{
    background-color: {BLANCO};
    border: 1px solid {GRIS_BORDE};
    border-radius: 4px;
    padding: 3px 5px;
    selection-background-color: {AZUL_MEDIO};
    selection-color: {BLANCO};
}}

QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {AZUL_MEDIO};
}}

/* -- Splitters (Revision: original / extraido / lateral) -- */
QSplitter::handle {{
    background-color: {GRIS_BORDE};
}}
"""
