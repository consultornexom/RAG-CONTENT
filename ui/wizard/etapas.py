"""Las etapas del asistente guiado (Fase 11.2, Documento Maestro
seccion 4.11: "Crear proyecto, seleccionar perfil, importar fuentes,
completar inventario, procesar, revisar, resolver incidencias,
normalizar, aprobar, generar Markdown, ejecutar pruebas y cerrar
lote"). Doce pasos en el documento maestro se convierten en NUEVE
pantallas aqui, por dos fusiones y una eliminacion deliberadas y
documentadas (no una omision):

- "Crear proyecto" + "seleccionar perfil" -> una sola etapa
  (`EtapaProyectoPerfil`): `ProjectsService.crear_proyecto()` exige
  `perfil_id` en el momento de crear, asi que el dominio ya obliga a
  que ambos pasos ocurran juntos -- mismo criterio que
  `RegistrarVigenciaDialog` (Modulo 11) combinando Fuente y Vigencia en
  un solo dialogo pese a ser conceptos separados en `domain`.
- "Importar fuentes" + "completar inventario" -> una sola etapa
  (se reutiliza `InventarioPanel` completo: agregar documentos Y ver la
  tabla del inventario son, en la practica, la misma pantalla).
- "Ejecutar pruebas" -- eliminada del asistente por completo
  (2026-07-31, comentario real del consultor: "que en el modo
  Asistente, la seccion de 'Pruebas de aceptacion' no se manifieste;
  que sea mas bien una funcionalidad del Modo Avanzado"). Esta etapa
  reutilizaba `PruebasPanel` (Fase 9), una herramienta de QA que valida
  el MOTOR de extraccion/OCR en general contra un corpus propio y
  ad-hoc -- no el documento que el operador acababa de procesar en este
  mismo proyecto (ver docstring de `ui.panels.pruebas_panel`, ya
  aclarado con texto explicativo el mismo dia que se agrego, pero
  reutilizarla como "Etapa 9 de 10" -- un paso aparentemente obligatorio
  de la secuencia lineal -- seguia siendo confuso). `PruebasPanel` sigue
  intacta y disponible en Modo Avanzado (`MainWindow.panel_pruebas`,
  entrada "Pruebas de aceptacion" del menu) para quien la necesite,
  independiente de cualquier proyecto especifico.

Cada etapa expone `establecer_proyecto(pctx, proyecto)`, llamado tanto
al abrir/cambiar de proyecto como CADA VEZ que el asistente navega a
esa etapa (mismo patron ya usado por `MainWindow._on_cambiar_pagina`
para el menu funcional) -- asi la etapa siempre recalcula lo que
depende del estado actual (conteos de documentos pendientes, etc.) sin
necesitar un metodo de refresco aparte.

Las etapas "Importar y completar inventario" y "Resolver incidencias"
reutilizan paneles YA construidos en `ui.panels.*` sin cambios
(`InventarioPanel`, `IncidenciasPanel`) -- no duplican esa logica. La
etapa "Procesar" NO reutiliza `ProcesamientoPanel` a proposito: ese
panel tambien hace de "modo avanzado" (cola de trabajos, seccion
4.11.1), y meterlo aqui filtraria justo lo que el interruptor de
`MainWindow` esta pensado para ocultar por defecto."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext, ProjectContext
from domain.documents.entities import Documento, EstadoDocumento
from domain.projects.entities import Proyecto
from ui.dialogs import CrearProyectoDialog
from ui.errores import mensaje_amigable
from ui.theme import aplicar_color_estado

_ESTADOS_PENDIENTES_DE_PROCESAR = {
    EstadoDocumento.RECIBIDO,
    EstadoDocumento.INVENTARIADO,
    EstadoDocumento.CLASIFICADO,
    EstadoDocumento.EN_EXTRACCION,
}


class _EtapaBase(QWidget):
    """Encabezado + descripcion comunes a todas las etapas dedicadas
    (no aplica a las que embeben un panel existente, que ya tienen su
    propio encabezado)."""

    def __init__(self, titulo: str, descripcion: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.layout_propio = QVBoxLayout(self)
        self.layout_propio.addWidget(QLabel(f"<b>{titulo}</b>"))
        etiqueta_descripcion = QLabel(descripcion)
        etiqueta_descripcion.setWordWrap(True)
        self.layout_propio.addWidget(etiqueta_descripcion)


class EtapaProyectoPerfil(_EtapaBase):
    proyecto_creado = Signal(str)  # proyecto_id

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(
            "Crear proyecto y elegir perfil",
            "Cree un proyecto nuevo (el perfil se elige al mismo tiempo -- todo "
            "proyecto necesita uno desde el momento en que se crea). Si ya tiene "
            "un proyecto, ábralo con el selector de la parte superior de la "
            "ventana; el asistente continúa donde lo dejó.",
            parent,
        )
        self.ctx = ctx
        self.proyecto: Proyecto | None = None

        self.etiqueta_estado = QLabel("")
        self.etiqueta_estado.setWordWrap(True)
        self.layout_propio.addWidget(self.etiqueta_estado)

        self.boton_crear = QPushButton("Crear proyecto nuevo...")
        self.boton_crear.clicked.connect(self._on_crear_proyecto)
        self.layout_propio.addWidget(self.boton_crear)
        self.layout_propio.addStretch()

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.proyecto = proyecto
        if proyecto is None:
            self.etiqueta_estado.setText("Todavia no hay ningun proyecto abierto.")
        else:
            self.etiqueta_estado.setText(f"Proyecto actual: {proyecto.nombre} -- perfil: {proyecto.perfil_id}.")

    def _on_crear_proyecto(self) -> None:
        # Bug real encontrado en la tercera auditoria general
        # 2026-07-31: `listar_perfiles()` (infrastructure.filesystem.
        # profile_loader) valida cada YAML con Pydantic al cargarlo --
        # un perfil corrupto (campo obligatorio faltante, archivo vacio,
        # o un nombre de version que no seguya el patron "N.N") lanza
        # sin traducir (`ValidationError`/`ValueError`), y esta era la
        # unica pantalla de las tres que cargan perfiles sin capturarlo,
        # dejando pasar un traceback crudo en vez del QMessageBox
        # amigable que se usa en el resto de la interfaz.
        try:
            perfiles = self.ctx.projects.listar_perfiles()
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudieron cargar los perfiles", mensaje_amigable(exc))
            return
        if not perfiles:
            QMessageBox.warning(
                self,
                "Sin perfiles disponibles",
                "No hay ningun perfil cargado todavia -- cree uno primero desde "
                "'Modo avanzado -> Configuracion'.",
            )
            return
        dialogo = CrearProyectoDialog(self, perfiles)
        if not dialogo.exec():
            return
        # perfil_id capturado una sola vez: dos llamadas separadas a
        # dialogo.perfil_id() no permiten que Mypy angoste la segunda a
        # partir del chequeo "is None" hecho sobre la primera.
        perfil_id = dialogo.perfil_id()
        if not dialogo.nombre() or perfil_id is None:
            QMessageBox.warning(self, "Campos requeridos", "Nombre y perfil son obligatorios.")
            return
        try:
            proyecto = self.ctx.projects.crear_proyecto(
                nombre=dialogo.nombre(),
                perfil_id=perfil_id,
                objetivo=dialogo.objetivo(),
                idioma=dialogo.idioma(),
                confidencialidad=dialogo.confidencialidad(),
            )
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo crear el proyecto", mensaje_amigable(exc))
            return
        self.proyecto_creado.emit(proyecto.id)


class EtapaProcesar(_EtapaBase):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(
            "Procesar",
            "Clasifica y extrae el contenido de los documentos recien "
            "importados. Los documentos ya procesados no se tocan de nuevo.",
            parent,
        )
        self.pctx: ProjectContext | None = None
        self.etiqueta_conteo = QLabel("")
        self.layout_propio.addWidget(self.etiqueta_conteo)
        self.boton_procesar = QPushButton("Clasificar y extraer documentos pendientes")
        self.boton_procesar.clicked.connect(self._on_procesar)
        self.layout_propio.addWidget(self.boton_procesar)
        self.layout_propio.addStretch()

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._actualizar_conteo()

    def _documentos_pendientes(self) -> list[Documento]:
        if self.pctx is None:
            return []
        return [d for d in self.pctx.documents.listar_documentos() if d.estado in _ESTADOS_PENDIENTES_DE_PROCESAR]

    def _actualizar_conteo(self) -> None:
        n = len(self._documentos_pendientes())
        self.etiqueta_conteo.setText(
            f"{n} documento(s) pendiente(s) de procesar." if n else "No hay documentos pendientes de procesar."
        )
        self.boton_procesar.setEnabled(n > 0)

    def _on_procesar(self) -> None:
        """Clasifica y extrae, uno por uno, cada documento pendiente.

        Sigue siendo sincrono sobre el hilo de la interfaz (no hay ningun
        mecanismo de segundo plano real todavia -- ver docstring de
        `ui.panels.procesamiento_panel`, cuya "cola" tambien procesa de
        forma sincrona bajo demanda; tampoco se resuelve con un
        `QThread`: `infrastructure.database.engine.build_engine()` abre
        SQLite con las opciones por defecto de SQLAlchemy, sin
        `check_same_thread=False`, asi que mover estas llamadas a otro
        hilo fallaria de inmediato, no solo seria "arriesgado"):
        clasificar/extraer puede tardar bastante por documento (OCR,
        transcripcion de audio/video, conversion de formatos legados), y
        sin ninguna senal visual el operador no tenia forma de saber si
        la herramienta seguia trabajando o se habia quedado colgada
        (comentario real del consultor, 2026-07-31, sobre esta misma
        etapa). Se agrega un `QProgressDialog` con el nombre y la ruta
        del archivo en turno.

        Corregido 2026-07-31, mismo dia (captura de pantalla real del
        consultor: el dialogo se veia completamente en negro, con los
        botones nativos de Windows "Forzar la salida"/"Esperar" -- el
        aviso de que la aplicacion "no responde"): el primer intento de
        este fix solo llamaba `QApplication.processEvents()` UNA vez por
        documento, antes de clasificar/extraer -- con un solo documento
        pendiente (como en la captura) o un documento con muchas
        paginas, esa unica llamada no bastaba: el hilo de la interfaz se
        quedaba bloqueado el resto del tiempo dentro de
        `extraer_documento()`, tiempo mas que suficiente para que
        Windows considere la ventana congelada, y el dialogo recien
        creado ni siquiera alcanzaba a pintarse una primera vez (de ahi
        el negro). Ahora se pasa `on_progreso` hasta
        `PdfOcrExtractor.extract()` (ver domain.documents.ports.
        DocumentExtractor.extract()): con OCR, se llama
        `processEvents()` una vez POR PAGINA, no solo una vez por
        documento, para que la ventana se repinte y la deteccion de
        "no responde" no se dispare incluso con un solo documento largo.
        Para los demas formatos (sin OCR de PDF) el callback no se
        invoca -- no lo necesitan, son rapidos incluso para documentos
        grandes -- y el operador tambien puede cancelar a mitad de
        camino (los documentos ya procesados quedan como tal, los
        restantes siguen pendientes para la proxima corrida)."""
        if self.pctx is None:
            return
        documentos = self._documentos_pendientes()
        progreso = QProgressDialog("Preparando...", "Cancelar", 0, len(documentos), self)
        progreso.setWindowTitle("Clasificando y extrayendo documentos")
        progreso.setMinimumDuration(0)
        progreso.setValue(0)
        ok = 0
        errores: list[str] = []
        for indice, documento in enumerate(documentos):
            if progreso.wasCanceled():
                break
            nombre_y_ruta = f"{documento.nombre_original}\n{documento.ruta_copia_original}"
            progreso.setLabelText(f"Procesando: {nombre_y_ruta}")
            progreso.setValue(indice)
            QApplication.processEvents()

            def _on_progreso_pagina(pagina: int, total_paginas: int, nombre_y_ruta: str = nombre_y_ruta) -> None:
                progreso.setLabelText(f"Procesando (pagina {pagina} de {total_paginas}): {nombre_y_ruta}")
                QApplication.processEvents()

            try:
                self.pctx.documents.clasificar_documento(documento.id)
            except Exception:
                pass  # puede que ya estuviera clasificado; el intento de extraer abajo revela un problema real si lo hay.
            try:
                self.pctx.documents.extraer_documento(documento.id, on_progreso=_on_progreso_pagina)
                ok += 1
            except Exception as exc:
                errores.append(f"{documento.nombre_original}: {mensaje_amigable(exc)}")
        progreso.setValue(len(documentos))
        self._actualizar_conteo()
        mensaje = f"{ok} documento(s) procesado(s) correctamente."
        if errores:
            mensaje += "\n\nCon error:\n" + "\n".join(errores)
            QMessageBox.warning(self, "Procesamiento con errores", mensaje)
        else:
            QMessageBox.information(self, "Procesamiento completo", mensaje)


class EtapaRevisar(_EtapaBase):
    ir_a_modo_avanzado = Signal(str)  # etiqueta de la pagina del menu

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(
            "Revisar",
            "La revision contra el original (correccion, verificacion de "
            "fechas/cifras, y registro de vigencia/fuente) usa la pantalla "
            "de Revision, que necesita mas espacio del que tiene una etapa "
            "del asistente -- este boton la abre directamente.",
            parent,
        )
        self.pctx: ProjectContext | None = None
        self.etiqueta_conteo = QLabel("")
        self.layout_propio.addWidget(self.etiqueta_conteo)
        self.boton_ir = QPushButton("Ir a Revision")
        self.boton_ir.clicked.connect(lambda: self.ir_a_modo_avanzado.emit("Revision"))
        self.layout_propio.addWidget(self.boton_ir)
        self.layout_propio.addStretch()

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        if pctx is None:
            self.etiqueta_conteo.setText("")
            return
        n = len([d for d in pctx.documents.listar_documentos() if d.estado == EstadoDocumento.EXTRAIDO])
        self.etiqueta_conteo.setText(
            f"{n} documento(s) en estado EXTRAIDO, listo(s) para revisar." if n else "No hay documentos pendientes de revision."
        )


class EtapaNormalizar(_EtapaBase):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(
            "Normalizar",
            "Aplica las reglas de normalizacion del perfil (Modulo 9) a los "
            "documentos ya revisados.",
            parent,
        )
        self.pctx: ProjectContext | None = None
        self.etiqueta_conteo = QLabel("")
        self.layout_propio.addWidget(self.etiqueta_conteo)
        self.boton_normalizar = QPushButton("Normalizar documentos revisados")
        self.boton_normalizar.clicked.connect(self._on_normalizar)
        self.layout_propio.addWidget(self.boton_normalizar)
        self.layout_propio.addStretch()

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._actualizar_conteo()

    def _documentos_pendientes(self) -> list[Documento]:
        if self.pctx is None:
            return []
        return [d for d in self.pctx.documents.listar_documentos() if d.estado == EstadoDocumento.REVISADO]

    def _actualizar_conteo(self) -> None:
        n = len(self._documentos_pendientes())
        self.etiqueta_conteo.setText(
            f"{n} documento(s) revisado(s), listo(s) para normalizar." if n else "No hay documentos pendientes de normalizar."
        )
        self.boton_normalizar.setEnabled(n > 0)

    def _on_normalizar(self) -> None:
        if self.pctx is None:
            return
        ok = 0
        errores: list[str] = []
        for documento in self._documentos_pendientes():
            try:
                self.pctx.documents.normalizar_documento(documento.id)
                ok += 1
            except Exception as exc:
                errores.append(f"{documento.nombre_original}: {mensaje_amigable(exc)}")
        self._actualizar_conteo()
        mensaje = f"{ok} documento(s) normalizado(s) correctamente."
        if errores:
            mensaje += "\n\nCon error:\n" + "\n".join(errores)
            QMessageBox.warning(self, "Normalizacion con errores", mensaje)
        else:
            QMessageBox.information(self, "Normalizacion completa", mensaje)


class EtapaAprobar(_EtapaBase):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(
            "Aprobar",
            "Aprueba para Markdown los documentos ya normalizados. El nombre "
            "de quien aprueba se aplica a todos los que se aprueben en esta "
            "pasada.",
            parent,
        )
        self.pctx: ProjectContext | None = None

        fila_aprobador = QHBoxLayout()
        fila_aprobador.addWidget(QLabel("Aprobador:"))
        self.campo_aprobador = QLineEdit()
        fila_aprobador.addWidget(self.campo_aprobador)
        self.layout_propio.addLayout(fila_aprobador)

        # Agregado 2026-07-31 (tercera auditoria general): esta etapa
        # descartaba el comentario de aprobacion, pasando siempre "" a
        # `aprobar_para_markdown()` -- a diferencia del Modo Avanzado
        # (`markdown_panel.py`, via `AprobadorDialog`), que si permite
        # capturarlo. Quien solo trabajara desde el asistente nunca
        # podia dejar constancia de un comentario; con este campo
        # (opcional, igual que en Modo Avanzado) se aplica el mismo
        # comentario a todos los documentos de esta pasada, igual que
        # ya ocurre con el aprobador.
        fila_comentario = QHBoxLayout()
        fila_comentario.addWidget(QLabel("Comentario (opcional):"))
        self.campo_comentario = QLineEdit()
        fila_comentario.addWidget(self.campo_comentario)
        self.layout_propio.addLayout(fila_comentario)

        self.etiqueta_conteo = QLabel("")
        self.layout_propio.addWidget(self.etiqueta_conteo)
        self.boton_aprobar = QPushButton("Aprobar documentos normalizados")
        self.boton_aprobar.clicked.connect(self._on_aprobar)
        self.layout_propio.addWidget(self.boton_aprobar)
        self.layout_propio.addStretch()

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._actualizar_conteo()

    def _documentos_pendientes(self) -> list[Documento]:
        if self.pctx is None:
            return []
        return [d for d in self.pctx.documents.listar_documentos() if d.estado == EstadoDocumento.NORMALIZADO]

    def _actualizar_conteo(self) -> None:
        n = len(self._documentos_pendientes())
        self.etiqueta_conteo.setText(
            f"{n} documento(s) normalizado(s), listo(s) para aprobar." if n else "No hay documentos pendientes de aprobar."
        )
        self.boton_aprobar.setEnabled(n > 0)

    def _on_aprobar(self) -> None:
        if self.pctx is None:
            return
        aprobador = self.campo_aprobador.text().strip()
        if not aprobador:
            QMessageBox.warning(self, "Campo requerido", "Debe indicar quien aprueba.")
            return
        comentario = self.campo_comentario.text().strip()
        ok = 0
        errores: list[str] = []
        for documento in self._documentos_pendientes():
            try:
                self.pctx.documents.aprobar_para_markdown(documento.id, aprobador, comentario)
                ok += 1
            except Exception as exc:
                errores.append(f"{documento.nombre_original}: {mensaje_amigable(exc)}")
        self._actualizar_conteo()
        mensaje = f"{ok} documento(s) aprobado(s) correctamente."
        if errores:
            mensaje += "\n\nCon error:\n" + "\n".join(errores)
            QMessageBox.warning(self, "Aprobacion con errores", mensaje)
        else:
            QMessageBox.information(self, "Aprobacion completa", mensaje)


class EtapaGenerarMarkdown(_EtapaBase):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(
            "Generar Markdown",
            "Genera y valida el Markdown final de los documentos ya "
            "aprobados. Liberarlos ocurre automaticamente al cerrar el lote "
            "(ultima etapa), no aqui.",
            parent,
        )
        self.pctx: ProjectContext | None = None
        self.etiqueta_conteo = QLabel("")
        self.layout_propio.addWidget(self.etiqueta_conteo)
        self.boton_generar = QPushButton("Generar y validar Markdown")
        self.boton_generar.clicked.connect(self._on_generar)
        self.layout_propio.addWidget(self.boton_generar)
        self.layout_propio.addStretch()

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self._actualizar_conteo()

    def _documentos_pendientes(self) -> list[Documento]:
        if self.pctx is None:
            return []
        return [d for d in self.pctx.documents.listar_documentos() if d.estado == EstadoDocumento.APROBADO_PARA_MARKDOWN]

    def _actualizar_conteo(self) -> None:
        n = len(self._documentos_pendientes())
        self.etiqueta_conteo.setText(
            f"{n} documento(s) aprobado(s), listo(s) para generar Markdown." if n else "No hay documentos pendientes."
        )
        self.boton_generar.setEnabled(n > 0)

    def _on_generar(self) -> None:
        if self.pctx is None:
            return
        ok = 0
        errores: list[str] = []
        for documento in self._documentos_pendientes():
            try:
                self.pctx.documents.generar_markdown(documento.id)
                self.pctx.documents.validar_markdown(documento.id)
                ok += 1
            except Exception as exc:
                errores.append(f"{documento.nombre_original}: {mensaje_amigable(exc)}")
        self._actualizar_conteo()
        mensaje = f"{ok} documento(s) con Markdown generado y validado."
        if errores:
            mensaje += "\n\nCon error:\n" + "\n".join(errores)
            QMessageBox.warning(self, "Generacion con errores", mensaje)
        else:
            QMessageBox.information(self, "Generacion completa", mensaje)


class EtapaCerrarLote(_EtapaBase):
    ir_a_modo_avanzado = Signal(str)  # etiqueta de la pagina del menu

    # Columnas de la tabla de seleccion (2026-10-03, NEXOM, Solicitud_
    # Ajustes_RAG_Content_Lotes_y_Portabilidad.pdf, seccion 2): antes
    # esta pantalla no ofrecia ninguna seleccion -- metia TODOS los
    # documentos del proyecto en el lote nuevo. El caso real que motivo
    # el cambio: un lote ya cerrado y entregado (25 licenciaturas) mas
    # 10 diplomados pendientes en el mismo proyecto -- cerrar un lote
    # nuevo solo para los diplomados no debe tocar ni volver a incluir
    # las licenciaturas.
    _COL_SELECCION, _COL_TITULO, _COL_ID, _COL_ESTADO, _COL_LOTE_ANTERIOR = range(5)

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(
            "Cerrar lote",
            "Elige que documentos del proyecto forman este lote y cierralo: "
            "los seleccionados que esten validados con fuente registrada "
            "quedan LIBERADOS; el resto de los seleccionados queda BLOQUEADO "
            "(Documento Maestro, seccion 4.10) -- ningun documento se pierde, "
            "solo queda marcado para revisar despues. Los documentos ya "
            "liberados en un lote anterior se muestran como referencia, sin "
            "marcar: inclúyelos solo si de verdad quieres volver a cerrarlos "
            "en este lote. Al cerrar, tambien se prepara automaticamente la "
            "entrega hacia RAG Studio (14_entrega_rag_studio), en una "
            "carpeta propia y versionada para este lote, sin tocar la "
            "entrega de ningun otro lote.",
            parent,
        )
        self.pctx: ProjectContext | None = None
        self.proyecto: Proyecto | None = None

        fila_nombre = QHBoxLayout()
        fila_nombre.addWidget(QLabel("Nombre del lote:"))
        self.campo_nombre = QLineEdit()
        fila_nombre.addWidget(self.campo_nombre)
        self.layout_propio.addLayout(fila_nombre)

        self.tabla_documentos = QTableWidget(0, 5)
        self.tabla_documentos.setHorizontalHeaderLabels(
            ["Incluir", "Titulo", "ID", "Estado actual", "Lote anterior"]
        )
        self.tabla_documentos.horizontalHeader().setStretchLastSection(True)
        self.tabla_documentos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_documentos.itemChanged.connect(self._on_item_cambiado)
        self.layout_propio.addWidget(self.tabla_documentos)

        self.etiqueta_contador = QLabel("0 documento(s) seleccionado(s).")
        self.layout_propio.addWidget(self.etiqueta_contador)

        self.boton_cerrar = QPushButton("Crear lote con los documentos seleccionados y cerrarlo")
        self.boton_cerrar.clicked.connect(self._on_cerrar_lote)
        self.layout_propio.addWidget(self.boton_cerrar)

        self.etiqueta_resultado = QLabel("")
        self.etiqueta_resultado.setWordWrap(True)
        self.layout_propio.addWidget(self.etiqueta_resultado)

        self.boton_ir_reportes = QPushButton("Ir a Reportes (acta de cierre)")
        self.boton_ir_reportes.clicked.connect(lambda: self.ir_a_modo_avanzado.emit("Reportes"))
        self.boton_ir_reportes.setEnabled(False)
        self.layout_propio.addWidget(self.boton_ir_reportes)
        self.layout_propio.addStretch()

        self._cargando_tabla = False  # evita que _on_item_cambiado reaccione mientras se puebla la tabla

    def establecer_proyecto(self, pctx: ProjectContext | None, proyecto: Proyecto | None) -> None:
        self.pctx = pctx
        self.proyecto = proyecto
        if proyecto is not None and not self.campo_nombre.text():
            self.campo_nombre.setText(f"Lote {proyecto.nombre}")
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        self._cargando_tabla = True
        self.tabla_documentos.setRowCount(0)
        if self.pctx is not None and self.proyecto is not None:
            lotes_por_id = {lote.id: lote.nombre for lote in self.pctx.batches.listar_lotes(self.proyecto.id)}
            for documento in self.pctx.documents.listar_documentos():
                fila = self.tabla_documentos.rowCount()
                self.tabla_documentos.insertRow(fila)

                item_seleccion = QTableWidgetItem()
                item_seleccion.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                # Sin marcar por defecto (ticket, seccion 2): la inclusion de
                # CUALQUIER documento -- ya liberado antes o no -- tiene que
                # ser una decision explicita del operador, nunca implicita.
                item_seleccion.setCheckState(Qt.CheckState.Unchecked)
                item_seleccion.setData(Qt.ItemDataRole.UserRole, documento.id)
                self.tabla_documentos.setItem(fila, self._COL_SELECCION, item_seleccion)

                self.tabla_documentos.setItem(fila, self._COL_TITULO, QTableWidgetItem(documento.nombre_original))
                self.tabla_documentos.setItem(fila, self._COL_ID, QTableWidgetItem(documento.id))

                item_estado = QTableWidgetItem(documento.estado.value)
                aplicar_color_estado(item_estado, documento.estado.value)
                self.tabla_documentos.setItem(fila, self._COL_ESTADO, item_estado)

                nombre_lote_anterior = lotes_por_id.get(documento.lote_id, "") if documento.lote_id else ""
                self.tabla_documentos.setItem(
                    fila, self._COL_LOTE_ANTERIOR, QTableWidgetItem(nombre_lote_anterior)
                )
        self.tabla_documentos.resizeColumnsToContents()
        self._cargando_tabla = False
        self._actualizar_contador()

    def _on_item_cambiado(self, item: QTableWidgetItem) -> None:
        if self._cargando_tabla or item.column() != self._COL_SELECCION:
            return
        self._actualizar_contador()

    def _ids_seleccionados(self) -> list[str]:
        ids = []
        for fila in range(self.tabla_documentos.rowCount()):
            item = self.tabla_documentos.item(fila, self._COL_SELECCION)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def _actualizar_contador(self) -> None:
        self.etiqueta_contador.setText(f"{len(self._ids_seleccionados())} documento(s) seleccionado(s).")

    def _on_cerrar_lote(self) -> None:
        if self.pctx is None or self.proyecto is None:
            return
        nombre = self.campo_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo requerido", "El lote necesita un nombre.")
            return
        documento_ids = self._ids_seleccionados()
        if not documento_ids:
            # Bloqueo de seleccion vacia (ticket, seccion 2) -- se valida
            # aqui mismo, en el cliente, antes de llamar al backend (que
            # ademas lo rechaza con SeleccionLoteVaciaError si se llegara
            # a saltar este control).
            QMessageBox.warning(
                self, "Seleccion vacia", "Selecciona al menos un documento para crear y cerrar el lote."
            )
            return

        # Vista previa antes de confirmar (ticket, seccion 2): mostrar el
        # nombre del lote, cuantos documentos se incluyen y cuales
        # cumplirian requisitos (quedarian LIBERADOS) o no (BLOQUEADOS),
        # usando la MISMA clasificacion que CerrarLote aplicara de verdad
        # (ver application.batches._resolucion.clasificar_para_cierre) --
        # para que la vista previa nunca pueda prometer algo distinto de
        # lo que de verdad va a pasar.
        try:
            previsualizacion = self.pctx.batches.previsualizar_seleccion(documento_ids)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo previsualizar la seleccion", mensaje_amigable(exc))
            return
        cumplen = [p for p in previsualizacion if p.cumple_requisitos]
        bloqueados_previstos = [p for p in previsualizacion if not p.cumple_requisitos]
        detalle_bloqueados = "\n".join(
            f"  - {p.documento.nombre_original}: {p.motivo}" for p in bloqueados_previstos
        )
        texto_preview = (
            f"Se creara y cerrara el lote '{nombre}' con {len(previsualizacion)} documento(s) seleccionado(s):\n"
            f"  - {len(cumplen)} quedarian LIBERADOS.\n"
            f"  - {len(bloqueados_previstos)} quedarian BLOQUEADOS."
        )
        if detalle_bloqueados:
            texto_preview += "\n\nBloqueados y por que:\n" + detalle_bloqueados
        texto_preview += "\n\n¿Confirmas crear y cerrar el lote con esta seleccion?"
        respuesta = QMessageBox.question(
            self,
            "Confirmar cierre de lote",
            texto_preview,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            lote_cerrado = self.pctx.batches.crear_lote_con_seleccion_y_cerrar(
                self.proyecto.id, nombre, documento_ids
            )
        except Exception as exc:  # se muestra al usuario, no se deja pasar en silencio
            QMessageBox.critical(self, "No se pudo crear y cerrar el lote", mensaje_amigable(exc))
            return
        self._cargar_tabla()  # refleja los nuevos estados/lote_id y limpia la seleccion
        documentos_finales = self.pctx.batches.listar_documentos_del_lote(lote_cerrado.id)
        liberados = len([d for d in documentos_finales if d.estado == EstadoDocumento.LIBERADO])
        bloqueados = len([d for d in documentos_finales if d.estado == EstadoDocumento.BLOQUEADO])
        mensaje = (
            f"Lote '{lote_cerrado.nombre}' cerrado con {len(documento_ids)} documento(s) seleccionado(s): "
            f"{liberados} liberado(s), {bloqueados} bloqueado(s) (sin fuente/aprobacion "
            f"suficiente -- registrelas y vuelva a intentar en un lote nuevo)."
        )
        # Agregado 2026-07-31 (comentario real del consultor): al cerrar
        # el lote (el momento natural de "ya termine de procesar estos
        # archivos"), se prepara de una vez la entrega hacia RAG Studio,
        # sin que el operador tenga que ir a la pantalla de Markdown
        # aparte -- no bloqueante: si falla (por ejemplo, permisos de
        # escritura), el lote ya quedo cerrado igual, solo se avisa.
        entrega_fallo = False
        try:
            ruta_entrega = self.pctx.documents.preparar_entrega_rag_studio(lote_id=lote_cerrado.id)
            mensaje += f"\n\nEntrega para RAG Studio lista en:\n{ruta_entrega}"
        except Exception as exc:
            entrega_fallo = True
            mensaje += f"\n\nNo se pudo preparar la entrega para RAG Studio: {mensaje_amigable(exc)}"
        self.etiqueta_resultado.setText(mensaje)
        self.boton_ir_reportes.setEnabled(True)
        # Agregado 2026-07-31 (comentario real del consultor: validar que
        # el cierre de lote avise de verdad de la entrega hacia RAG
        # Studio, no solo con una etiqueta facil de pasar por alto):
        # mismo patron de QMessageBox usado en EtapaProcesar/
        # EtapaNormalizar/EtapaAprobar/EtapaGenerarMarkdown para el
        # resultado del batch.
        if entrega_fallo:
            QMessageBox.warning(self, "Lote cerrado con avisos", mensaje)
        else:
            QMessageBox.information(self, "Lote cerrado", mensaje)
