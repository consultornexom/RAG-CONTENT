"""Asistente guiado por etapas (Fase 11.2, Documento Maestro seccion
4.11.1: "el asistente por etapas es la vista predeterminada al abrir un
proyecto"). Contenedor que arma las nueve etapas de `ui.wizard.etapas` +
dos paneles reutilizados de `ui.panels.*` (ver docstring de
`etapas.py` para el porque de nueve y no doce -- incluye por que
"Ejecutar pruebas" ya no es una etapa del asistente, 2026-07-31) dentro
de un `QStackedWidget`, con una lista de etapas a la izquierda (solo se
puede saltar hacia una etapa ya alcanzada -- no hacia adelante sin pasar
por las intermedias) y botones Atras/Siguiente.

Solo depende de `app.bootstrap` y de otras piezas de `ui` (nunca de
`infrastructure` directamente, ADR-001 seccion 4). Emite dos señales
hacia `MainWindow`, reenviando las de sus etapas hijas:
- `proyecto_creado(proyecto_id)`: la etapa "Crear proyecto y elegir
  perfil" creo un proyecto -- `MainWindow` lo abre de inmediato (mismo
  criterio de baja friccion que `ProyectosPanel`, Fase 11).
- `ir_a_modo_avanzado(etiqueta)`: alguna etapa (Revisar, Cerrar lote)
  necesita una pantalla del menu funcional que no tiene sentido
  duplicar aqui -- `MainWindow` activa el interruptor de modo avanzado
  y navega directo a esa pagina."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from app.bootstrap import AppContext, ProjectContext
from domain.projects.entities import Proyecto
from ui.panels.incidencias_panel import IncidenciasPanel
from ui.panels.inventario_panel import InventarioPanel
from ui.wizard.estado_asistente import guardar_etapa, leer_etapa
from ui.wizard.etapas import (
    EtapaAprobar,
    EtapaCerrarLote,
    EtapaGenerarMarkdown,
    EtapaNormalizar,
    EtapaProcesar,
    EtapaProyectoPerfil,
    EtapaRevisar,
)

_ETIQUETAS = [
    "Crear proyecto y elegir perfil",
    "Importar y completar inventario",
    "Procesar",
    "Revisar",
    "Resolver incidencias",
    "Normalizar",
    "Aprobar",
    "Generar Markdown",
    "Cerrar lote",
]


class AsistenteWidget(QWidget):
    proyecto_creado = Signal(str)
    ir_a_modo_avanzado = Signal(str)

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None
        self._etapa_actual = 0
        self._etapa_maxima_alcanzada = 0

        layout = QVBoxLayout(self)
        self.etiqueta_progreso = QLabel("")
        layout.addWidget(self.etiqueta_progreso)

        fila = QHBoxLayout()
        self.lista_etapas = QListWidget()
        self.lista_etapas.setMaximumWidth(230)
        for etiqueta in _ETIQUETAS:
            self.lista_etapas.addItem(etiqueta)
        self.lista_etapas.currentRowChanged.connect(self._on_click_etapa)
        fila.addWidget(self.lista_etapas)

        self.paginas = QStackedWidget()
        fila.addWidget(self.paginas, stretch=1)
        layout.addLayout(fila, stretch=1)

        self._construir_etapas(ctx)

        barra = QHBoxLayout()
        self.boton_atras = QPushButton("<- Atras")
        self.boton_atras.clicked.connect(self._ir_atras)
        barra.addWidget(self.boton_atras)
        barra.addStretch()
        self.boton_siguiente = QPushButton("Siguiente ->")
        self.boton_siguiente.clicked.connect(self._ir_adelante)
        barra.addWidget(self.boton_siguiente)
        layout.addLayout(barra)

        self._mostrar_etapa(0)

    def _construir_etapas(self, ctx: AppContext) -> None:
        self.etapa_proyecto_perfil = EtapaProyectoPerfil(ctx)
        self.etapa_proyecto_perfil.proyecto_creado.connect(self.proyecto_creado.emit)
        self.etapa_inventario = InventarioPanel(ctx)
        self.etapa_procesar = EtapaProcesar(ctx)
        self.etapa_revisar = EtapaRevisar(ctx)
        self.etapa_revisar.ir_a_modo_avanzado.connect(self.ir_a_modo_avanzado.emit)
        self.etapa_incidencias = IncidenciasPanel(ctx)
        self.etapa_normalizar = EtapaNormalizar(ctx)
        self.etapa_aprobar = EtapaAprobar(ctx)
        self.etapa_markdown = EtapaGenerarMarkdown(ctx)
        self.etapa_cerrar_lote = EtapaCerrarLote(ctx)
        self.etapa_cerrar_lote.ir_a_modo_avanzado.connect(self.ir_a_modo_avanzado.emit)

        self._etapas: list[QWidget] = [
            self.etapa_proyecto_perfil,
            self.etapa_inventario,
            self.etapa_procesar,
            self.etapa_revisar,
            self.etapa_incidencias,
            self.etapa_normalizar,
            self.etapa_aprobar,
            self.etapa_markdown,
            self.etapa_cerrar_lote,
        ]
        for etapa in self._etapas:
            self.paginas.addWidget(etapa)

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        """Llamado por `MainWindow` al abrir un proyecto (o al crear uno
        nuevo desde la propia etapa 1). Restaura la etapa donde el
        operador se quedo la ultima vez (autoguardado, seccion
        4.11.1) -- ver `ui.wizard.estado_asistente`."""
        self.pctx = pctx
        self.proyecto = proyecto
        etapa_inicial = leer_etapa(proyecto.ruta_carpeta) if proyecto is not None else 0
        self._etapa_maxima_alcanzada = max(self._etapa_maxima_alcanzada, etapa_inicial)
        self._mostrar_etapa(etapa_inicial)

    def _mostrar_etapa(self, indice: int) -> None:
        indice = max(0, min(indice, len(self._etapas) - 1))
        self._etapa_actual = indice
        self._etapa_maxima_alcanzada = max(self._etapa_maxima_alcanzada, indice)
        self.paginas.setCurrentIndex(indice)
        if self.lista_etapas.currentRow() != indice:
            self.lista_etapas.blockSignals(True)
            self.lista_etapas.setCurrentRow(indice)
            self.lista_etapas.blockSignals(False)
        self.etiqueta_progreso.setText(f"Etapa {indice + 1} de {len(self._etapas)}: {_ETIQUETAS[indice]}")
        self.boton_atras.setEnabled(indice > 0)
        self.boton_siguiente.setEnabled(indice < len(self._etapas) - 1)
        etapa = self._etapas[indice]
        establecer = getattr(etapa, "establecer_proyecto", None)
        if establecer is not None:
            establecer(self.pctx, self.proyecto)
        if self.proyecto is not None:
            guardar_etapa(self.proyecto.ruta_carpeta, indice)

    def _ir_atras(self) -> None:
        self._mostrar_etapa(self._etapa_actual - 1)

    def _ir_adelante(self) -> None:
        self._mostrar_etapa(self._etapa_actual + 1)

    def _on_click_etapa(self, indice: int) -> None:
        if indice < 0:
            return
        if indice > self._etapa_maxima_alcanzada:
            # Todavia no llego hasta ahi -- revertir la seleccion visual
            # sin moverse (no tiene sentido "saltar" etapas que dependen
            # de que las anteriores ya hayan corrido).
            self.lista_etapas.blockSignals(True)
            self.lista_etapas.setCurrentRow(self._etapa_actual)
            self.lista_etapas.blockSignals(False)
            return
        self._mostrar_etapa(indice)
