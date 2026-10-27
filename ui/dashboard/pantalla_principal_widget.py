"""Pantalla principal tipo dashboard (Fase 11.3, Documento Maestro
seccion 4.11): "Proyectos recientes, documentos por estado, trabajos en
ejecucion, incidencias criticas, documentos bloqueados, avance por
lote, almacenamiento disponible y ultimas actividades." Es la tercera y
ultima pieza de la Fase 11 (menu funcional y asistente por etapas ya
completos, ver README/bitacora).

Es la vista de ENTRADA de la ventana (antes de abrir cualquier
proyecto, y a la que siempre se puede volver con el boton "Inicio" de
la barra superior). Combina dos tipos de datos:
- Sin depender de ningun proyecto abierto: "proyectos recientes"
  (`ctx.projects.listar_proyectos()`, ordenados por `created_at`) y
  "almacenamiento disponible" (consulta directa al sistema operativo
  con `shutil.disk_usage()` sobre la carpeta del proyecto seleccionado
  en esa lista -- no es logica de negocio, mismo criterio que
  `ui.panels.configuracion_panel`/`pruebas_panel` leyendo
  `Proyecto.ruta_carpeta` directo con `pathlib`).
- Del proyecto actualmente abierto (si hay uno): documentos por estado,
  trabajos en ejecucion, incidencias criticas abiertas, documentos
  bloqueados, avance por lote y ultimas actividades de auditoria. Si no
  hay ningun proyecto abierto, esa mitad de la pantalla solo indica que
  hace falta abrir o crear uno -- nunca se inventan datos."""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext
from domain.documents.entities import EstadoDocumento
from domain.incidents.entities import filtrar_criticas_abiertas
from domain.jobs.entities import EstadoTrabajo
from domain.projects.entities import Proyecto
from ui.errores import mensaje_amigable

_MAX_PROYECTOS_RECIENTES = 8
_MAX_ACTIVIDADES = 10


class PantallaPrincipalWidget(QWidget):
    abrir_proyecto_id = Signal(str)

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Pantalla principal</b>"))

        fila_superior = QHBoxLayout()

        grupo_recientes = QGroupBox("Proyectos recientes")
        layout_recientes = QVBoxLayout(grupo_recientes)
        self.lista_recientes = QListWidget()
        self.lista_recientes.itemDoubleClicked.connect(self._on_abrir_reciente)
        layout_recientes.addWidget(self.lista_recientes)
        layout_recientes.addWidget(QLabel("(doble clic para abrir)"))
        fila_superior.addWidget(grupo_recientes, stretch=1)

        grupo_almacenamiento = QGroupBox("Almacenamiento disponible")
        layout_almacenamiento = QVBoxLayout(grupo_almacenamiento)
        self.etiqueta_almacenamiento = QLabel("")
        self.etiqueta_almacenamiento.setWordWrap(True)
        layout_almacenamiento.addWidget(self.etiqueta_almacenamiento)
        layout_almacenamiento.addStretch()
        fila_superior.addWidget(grupo_almacenamiento, stretch=1)

        layout.addLayout(fila_superior)

        self.etiqueta_sin_proyecto = QLabel(
            "Abra o cree un proyecto (barra superior, o etapa 'Crear proyecto y elegir "
            "perfil' del asistente) para ver su resumen aqui."
        )
        self.etiqueta_sin_proyecto.setWordWrap(True)
        layout.addWidget(self.etiqueta_sin_proyecto)

        fila_media = QHBoxLayout()

        grupo_documentos = QGroupBox("Documentos por estado")
        layout_documentos = QVBoxLayout(grupo_documentos)
        self.etiqueta_documentos = QLabel("")
        self.etiqueta_documentos.setWordWrap(True)
        layout_documentos.addWidget(self.etiqueta_documentos)
        fila_media.addWidget(grupo_documentos, stretch=1)

        grupo_trabajos = QGroupBox("Trabajos en ejecucion")
        layout_trabajos = QVBoxLayout(grupo_trabajos)
        self.etiqueta_trabajos = QLabel("")
        self.etiqueta_trabajos.setWordWrap(True)
        layout_trabajos.addWidget(self.etiqueta_trabajos)
        fila_media.addWidget(grupo_trabajos, stretch=1)

        grupo_incidencias = QGroupBox("Incidencias criticas abiertas")
        layout_incidencias = QVBoxLayout(grupo_incidencias)
        self.etiqueta_incidencias = QLabel("")
        self.etiqueta_incidencias.setWordWrap(True)
        layout_incidencias.addWidget(self.etiqueta_incidencias)
        fila_media.addWidget(grupo_incidencias, stretch=1)

        layout.addLayout(fila_media)

        fila_inferior = QHBoxLayout()

        grupo_lotes = QGroupBox("Avance por lote")
        layout_lotes = QVBoxLayout(grupo_lotes)
        self.lista_lotes = QListWidget()
        layout_lotes.addWidget(self.lista_lotes)
        fila_inferior.addWidget(grupo_lotes, stretch=1)

        grupo_actividad = QGroupBox("Ultimas actividades")
        layout_actividad = QVBoxLayout(grupo_actividad)
        self.lista_actividad = QListWidget()
        layout_actividad.addWidget(self.lista_actividad)
        fila_inferior.addWidget(grupo_actividad, stretch=1)

        layout.addLayout(fila_inferior, stretch=1)

        self._refrescar_proyectos_recientes()

    # -- refresco -------------------------------------------------------

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        self._refrescar_proyectos_recientes()
        self._refrescar_resumen_proyecto()

    def _refrescar_proyectos_recientes(self) -> None:
        # incluir_archivados=False (Auditoria 2026-09-02, hallazgo real
        # de la auditoria independiente de esta ronda): esta lista es
        # justamente la fuente del doble clic que abre un proyecto
        # (`_on_abrir_reciente` -> `abrir_proyecto_id` ->
        # `MainWindow._on_abrir_proyecto_id`), y ese handler busca el id
        # en `combo_proyectos`, que desde el fix de RAG_CONTENT_01 solo
        # contiene proyectos activos. Antes de este cambio, un proyecto
        # archivado seguia apareciendo aqui pero el doble clic no hacia
        # nada -- sin ningun aviso -- porque `combo_proyectos.findData()`
        # nunca lo encontraba. Filtrar aqui con el mismo criterio que el
        # combo evita llegar a ese estado en vez de tener que manejarlo
        # despues.
        self.lista_recientes.clear()
        proyectos = sorted(
            self.ctx.projects.listar_proyectos(incluir_archivados=False), key=lambda p: p.created_at, reverse=True
        )
        for proyecto in proyectos[:_MAX_PROYECTOS_RECIENTES]:
            item = QListWidgetItem(f"{proyecto.nombre} ({proyecto.estado.value})")
            item.setData(256, proyecto.id)  # Qt.UserRole == 256
            self.lista_recientes.addItem(item)
        # Almacenamiento disponible: del proyecto abierto si hay uno, o
        # del mas reciente en la lista, o nada si todavia no existe
        # ningun proyecto.
        referencia = self.proyecto or (proyectos[0] if proyectos else None)
        self._refrescar_almacenamiento(referencia)

    def _refrescar_almacenamiento(self, proyecto: Proyecto | None) -> None:
        if proyecto is None or not proyecto.ruta_carpeta:
            self.etiqueta_almacenamiento.setText("Sin proyecto para consultar todavia.")
            return
        try:
            uso = shutil.disk_usage(Path(proyecto.ruta_carpeta))
        except OSError as exc:
            self.etiqueta_almacenamiento.setText(f"No se pudo consultar: {mensaje_amigable(exc)}")
            return
        libres_gb = uso.free / (1024**3)
        total_gb = uso.total / (1024**3)
        self.etiqueta_almacenamiento.setText(
            f"{libres_gb:.1f} GB libres de {total_gb:.1f} GB totales\n(disco de '{proyecto.nombre}')"
        )

    def _refrescar_resumen_proyecto(self) -> None:
        # if/is None (no un booleano "tiene_proyecto" aparte) para que
        # Mypy pueda angostar self.pctx/self.proyecto en el resto del
        # metodo -- mismo criterio que TextoSimpleDialog.valor().
        self.etiqueta_sin_proyecto.setVisible(self.pctx is None or self.proyecto is None)
        if self.pctx is None or self.proyecto is None:
            self.etiqueta_documentos.setText("")
            self.etiqueta_trabajos.setText("")
            self.etiqueta_incidencias.setText("")
            self.lista_lotes.clear()
            self.lista_actividad.clear()
            return

        documentos = self.pctx.documents.listar_documentos()
        conteos: dict[str, int] = {}
        for documento in documentos:
            conteos[documento.estado.value] = conteos.get(documento.estado.value, 0) + 1
        self.etiqueta_documentos.setText(
            "\n".join(f"{estado}: {n}" for estado, n in sorted(conteos.items())) or "Sin documentos todavia."
        )
        bloqueados = conteos.get(EstadoDocumento.BLOQUEADO.value, 0)
        if bloqueados:
            self.etiqueta_documentos.setText(
                self.etiqueta_documentos.text() + f"\n\n{bloqueados} documento(s) BLOQUEADO(s)."
            )

        trabajos = self.pctx.jobs.listar_trabajos_por_estado(EstadoTrabajo.EJECUTANDO)
        self.etiqueta_trabajos.setText(
            "\n".join(f"{t.tipo.value} -- documento {t.documento_id}" for t in trabajos)
            or "Ningun trabajo en ejecucion."
        )

        criticas = filtrar_criticas_abiertas(self.pctx.incidents.listar_incidencias())
        self.etiqueta_incidencias.setText(
            "\n".join(f"{i.tipo} -- documento {i.documento_id}" for i in criticas)
            or "Ninguna incidencia critica abierta."
        )

        self.lista_lotes.clear()
        for lote in self.pctx.batches.listar_lotes(self.proyecto.id):
            documentos_lote = self.pctx.batches.listar_documentos_del_lote(lote.id)
            liberados = len([d for d in documentos_lote if d.estado == EstadoDocumento.LIBERADO])
            self.lista_lotes.addItem(
                f"{lote.nombre} ({lote.estado.value}): {liberados}/{len(documentos_lote)} liberado(s)"
            )

        self.lista_actividad.clear()
        # Hallazgo real de la cuarta auditoria general (2026-08-01): antes
        # se traian TODOS los eventos de auditoria del proyecto a memoria
        # Python y recien ahi se truncaba con el slice -- ahora el limite
        # se aplica en la propia consulta SQL (ver AuditLogger.list_by_project).
        for evento in self.ctx.audit.list_by_project(self.proyecto.id, limite=_MAX_ACTIVIDADES):
            self.lista_actividad.addItem(f"{evento.fecha.strftime('%Y-%m-%d %H:%M')} -- {evento.accion}")

    def _on_abrir_reciente(self, item: QListWidgetItem) -> None:
        proyecto_id = item.data(256)
        if proyecto_id:
            self.abrir_proyecto_id.emit(proyecto_id)
