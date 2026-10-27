"""Dialogos del prototipo de Modulo 8/10. Cada uno solo recolecta los
campos que su caso de uso de `application` necesita -- ningun dialogo
llama a `application` por si mismo, eso lo hace `ui.main_window`
despues de que el dialogo se acepta (mismo principio de "ui solo
orquesta, no decide" que ya siguen los casos de uso)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from domain.documents.entities import Documento
from domain.incidents.entities import EtapaIncidencia, SeveridadIncidencia
from domain.profiles.entities import PerfilProyecto
from domain.projects.entities import NivelConfidencialidad
from domain.validity.entities import Fuente, Vigencia


class RevisarDocumentoDialog(QDialog):
    """Recolecta revisor + comentario para
    DocumentsService.revisar_documento() (Modulo 8)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aprobar revision")

        self.campo_revisor = QLineEdit()
        self.campo_comentario = QPlainTextEdit()
        self.campo_comentario.setPlaceholderText("Comentario de la revision (opcional)")

        formulario = QFormLayout()
        formulario.addRow("Revisor:", self.campo_revisor)
        formulario.addRow("Comentario:", self.campo_comentario)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def revisor(self) -> str:
        return self.campo_revisor.text().strip()

    def comentario(self) -> str:
        return self.campo_comentario.toPlainText().strip()


class RegistrarIncidenciaDialog(QDialog):
    """Recolecta etapa/tipo/severidad/evidencia/impacto para
    IncidentsService.registrar_incidencia() (Modulo 10) -- exactamente
    los campos de la tabla de modulos (Documento Maestro, seccion 4.6),
    salvo id/responsable/estado/respuesta/decision/cierre, que no
    aplican al registrar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar incidencia")

        self.campo_etapa = QComboBox()
        for etapa in EtapaIncidencia:
            self.campo_etapa.addItem(etapa.value, etapa)

        self.campo_severidad = QComboBox()
        for severidad in SeveridadIncidencia:
            self.campo_severidad.addItem(severidad.value, severidad)

        self.campo_tipo = QLineEdit()
        self.campo_tipo.setPlaceholderText("p. ej. cifra_dudosa, contenido_faltante, contradiccion")

        self.campo_evidencia = QPlainTextEdit()
        self.campo_evidencia.setPlaceholderText("Descripcion o cita de donde se detecto la incidencia")

        self.campo_impacto = QPlainTextEdit()
        self.campo_impacto.setPlaceholderText("Que consecuencia tiene si no se corrige")

        formulario = QFormLayout()
        formulario.addRow("Etapa:", self.campo_etapa)
        formulario.addRow("Tipo:", self.campo_tipo)
        formulario.addRow("Severidad:", self.campo_severidad)
        formulario.addRow("Evidencia:", self.campo_evidencia)
        formulario.addRow("Impacto:", self.campo_impacto)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def etapa(self) -> EtapaIncidencia:
        return self.campo_etapa.currentData()

    def severidad(self) -> SeveridadIncidencia:
        return self.campo_severidad.currentData()

    def tipo(self) -> str:
        return self.campo_tipo.text().strip()

    def evidencia(self) -> str:
        return self.campo_evidencia.toPlainText().strip()

    def impacto(self) -> str:
        return self.campo_impacto.toPlainText().strip()


class RegistrarVigenciaDialog(QDialog):
    """Recolecta los campos de Fuente y Vigencia (Modulo 11, ADR-001
    seccion 5) para ValidityService.registrar_fuente()/
    registrar_vigencia() -- un solo dialogo para las dos entidades,
    igual que el Documento Maestro las agrupa bajo un unico modulo
    ("11. Vigencias y fuentes"), aunque domain.validity las modela por
    separado (ver su docstring: "no deben confundirse").

    Si se construye con `fuente`/`vigencia` ya existentes, los campos
    se prellenan para editar en vez de partir de cero -- mismo
    principio de "confirmar o corregir" que
    application.validity.commands ya asume con su upsert.

    `documentos_disponibles` (2026-09-04, pedido explicito de un usuario
    real) alimenta un selector para "Sustituye a": antes habia que
    conocer de memoria (o ir a buscar fuera de la herramienta) el ID del
    documento a sustituir, un UUID largo dificil de transcribir a mano.
    El combo es editable, asi que si no se pasa la lista (o el documento
    buscado no esta en ella) el usuario sigue pudiendo pegar el ID a
    mano, igual que antes."""

    def __init__(
        self,
        parent=None,
        fuente: Optional[Fuente] = None,
        vigencia: Optional[Vigencia] = None,
        documentos_disponibles: Optional[list[Documento]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Vigencia y fuente")

        self.campo_sistema_origen = QLineEdit(fuente.sistema_origen if fuente else "")
        self.campo_autoridad_fuente = QLineEdit(fuente.autoridad if fuente else "")
        self.campo_evidencia_consulta = QLineEdit(fuente.evidencia_consulta if fuente else "")

        self.campo_fecha_emision = QLineEdit(_fecha_a_texto(vigencia.fecha_emision if vigencia else None))
        self.campo_fecha_emision.setPlaceholderText("AAAA-MM-DD (opcional)")
        self.campo_vigente_desde = QLineEdit(_fecha_a_texto(vigencia.vigente_desde if vigencia else None))
        self.campo_vigente_desde.setPlaceholderText("AAAA-MM-DD")
        self.campo_vigente_hasta = QLineEdit(_fecha_a_texto(vigencia.vigente_hasta if vigencia else None))
        self.campo_vigente_hasta.setPlaceholderText("AAAA-MM-DD (vacio si es indefinida)")
        self.campo_sin_vencimiento = QCheckBox("Vigente sin fecha de vencimiento (hasta nueva disposicion)")
        self.campo_sin_vencimiento.setChecked(bool(vigencia and vigencia.sin_vencimiento))
        self.campo_autoridad_vigencia = QLineEdit(vigencia.autoridad if vigencia else "")

        self.campo_sustituye_a = QComboBox()
        self.campo_sustituye_a.setEditable(True)
        self.campo_sustituye_a.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        campo_edicion_sustituye_a = self.campo_sustituye_a.lineEdit()
        if campo_edicion_sustituye_a is not None:
            campo_edicion_sustituye_a.setPlaceholderText("id del documento que este sustituye (opcional)")
        self.campo_sustituye_a.addItem("(ninguno)", None)
        sustituye_a_previo = vigencia.sustituye_a if vigencia and vigencia.sustituye_a else None
        for documento in documentos_disponibles or []:
            self.campo_sustituye_a.addItem(f"{documento.nombre_original}  [{documento.id}]", documento.id)
        if sustituye_a_previo:
            indice_previo = self.campo_sustituye_a.findData(sustituye_a_previo)
            if indice_previo >= 0:
                self.campo_sustituye_a.setCurrentIndex(indice_previo)
            else:
                # El documento no esta en la lista disponible (p. ej. se
                # elimino, o el llamador no la paso) -- se conserva el ID
                # tal cual estaba, igual que con el QLineEdit anterior.
                self.campo_sustituye_a.setCurrentText(sustituye_a_previo)
        else:
            self.campo_sustituye_a.setCurrentIndex(0)

        formulario = QFormLayout()
        formulario.addRow(QLabel("<b>Fuente</b>"))
        formulario.addRow("Sistema/area de origen:", self.campo_sistema_origen)
        formulario.addRow("Autoridad que emite:", self.campo_autoridad_fuente)
        formulario.addRow("Evidencia de consulta:", self.campo_evidencia_consulta)
        formulario.addRow(QLabel("<b>Vigencia</b>"))
        formulario.addRow("Fecha de emision:", self.campo_fecha_emision)
        formulario.addRow("Vigente desde:", self.campo_vigente_desde)
        formulario.addRow("Vigente hasta:", self.campo_vigente_hasta)
        formulario.addRow("", self.campo_sin_vencimiento)
        formulario.addRow("Autoridad de la vigencia:", self.campo_autoridad_vigencia)
        formulario.addRow("Sustituye a (documento_id):", self.campo_sustituye_a)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def sistema_origen(self) -> str:
        return self.campo_sistema_origen.text().strip()

    def autoridad_fuente(self) -> str:
        return self.campo_autoridad_fuente.text().strip()

    def evidencia_consulta(self) -> str:
        return self.campo_evidencia_consulta.text().strip()

    def fecha_emision(self) -> Optional[date]:
        return _texto_a_fecha(self.campo_fecha_emision.text(), "fecha de emision")

    def vigente_desde(self) -> Optional[date]:
        return _texto_a_fecha(self.campo_vigente_desde.text(), "vigente desde")

    def vigente_hasta(self) -> Optional[date]:
        return _texto_a_fecha(self.campo_vigente_hasta.text(), "vigente hasta")

    def sin_vencimiento(self) -> bool:
        return self.campo_sin_vencimiento.isChecked()

    def autoridad_vigencia(self) -> str:
        return self.campo_autoridad_vigencia.text().strip()

    def sustituye_a(self) -> Optional[str]:
        # Si el usuario eligio un documento de la lista, currentData()
        # trae su ID exacto. Si escribio/pego texto que no coincide con
        # ningun elemento (ID a mano, o el combo no tenia la lista),
        # currentData() es None y se usa el texto tal cual, igual que
        # antes con el QLineEdit -- ver docstring de la clase.
        id_seleccionado = self.campo_sustituye_a.currentData()
        if id_seleccionado:
            return id_seleccionado
        texto = self.campo_sustituye_a.currentText().strip()
        if texto == "(ninguno)":
            return None
        return texto or None


class CrearProyectoDialog(QDialog):
    """Recolecta los campos de ProjectsService.crear_proyecto() (Modulo
    1) -- pantalla "Proyectos" del menu funcional (Fase 11, Documento
    Maestro seccion 4.11). `perfiles` nunca esta vacio en un uso normal
    (el perfil generico se crea junto con la raiz de la aplicacion),
    pero si lo estuviera el combo queda vacio y el llamador debe avisar
    antes de intentar crear -- no es responsabilidad de este dialogo
    impedirlo."""

    def __init__(self, parent=None, perfiles: Optional[list[PerfilProyecto]] = None):
        super().__init__(parent)
        self.setWindowTitle("Crear proyecto")

        self.campo_nombre = QLineEdit()
        self.campo_perfil = QComboBox()
        for perfil in perfiles or []:
            self.campo_perfil.addItem(f"{perfil.id} (v{perfil.version})", perfil.id)
        self.campo_objetivo = QLineEdit()
        self.campo_idioma = QLineEdit("es")
        self.campo_confidencialidad = QComboBox()
        for nivel in NivelConfidencialidad:
            self.campo_confidencialidad.addItem(nivel.value, nivel)
        self.campo_confidencialidad.setCurrentIndex(
            self.campo_confidencialidad.findData(NivelConfidencialidad.INTERNO)
        )

        formulario = QFormLayout()
        formulario.addRow("Nombre:", self.campo_nombre)
        formulario.addRow("Perfil:", self.campo_perfil)
        formulario.addRow("Objetivo:", self.campo_objetivo)
        formulario.addRow("Idioma:", self.campo_idioma)
        formulario.addRow("Confidencialidad:", self.campo_confidencialidad)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def nombre(self) -> str:
        return self.campo_nombre.text().strip()

    def perfil_id(self) -> Optional[str]:
        return self.campo_perfil.currentData()

    def objetivo(self) -> str:
        return self.campo_objetivo.text().strip()

    def idioma(self) -> str:
        return self.campo_idioma.text().strip() or "es"

    def confidencialidad(self) -> NivelConfidencialidad:
        return self.campo_confidencialidad.currentData()


class CrearPerfilDialog(QDialog):
    """Recolecta perfil_id/version/descripcion para
    ProfilesService.crear_perfil() (Modulo 2). Solo los campos basicos
    -- catalogos, reglas de validacion/normalizacion y plantilla se
    dejan en sus valores por defecto (listas vacias), consistente con
    "cada perfil trae valores por defecto razonables" (Documento
    Maestro, seccion 4.11.1); ajustarlos a mano queda para una edicion
    posterior del paquete YAML, fuera del alcance de este dialogo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear perfil")

        self.campo_perfil_id = QLineEdit()
        self.campo_version = QLineEdit("0.1")
        self.campo_descripcion = QPlainTextEdit()

        formulario = QFormLayout()
        formulario.addRow("Id del perfil:", self.campo_perfil_id)
        formulario.addRow("Version:", self.campo_version)
        formulario.addRow("Descripcion:", self.campo_descripcion)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def perfil_id(self) -> str:
        return self.campo_perfil_id.text().strip()

    def version(self) -> str:
        return self.campo_version.text().strip() or "0.1"

    def descripcion(self) -> str:
        return self.campo_descripcion.toPlainText().strip()


class AprobadorDialog(QDialog):
    """Recolecta aprobador + comentario -- mismo par de campos que
    RevisarDocumentoDialog, en un dialogo propio para no reutilizar una
    etiqueta ("Revisor") que no aplica a la aprobacion para Markdown
    (Modulo 12)."""

    def __init__(self, parent=None, titulo: str = "Aprobar"):
        super().__init__(parent)
        self.setWindowTitle(titulo)

        self.campo_aprobador = QLineEdit()
        self.campo_comentario = QPlainTextEdit()

        formulario = QFormLayout()
        formulario.addRow("Aprobador:", self.campo_aprobador)
        formulario.addRow("Comentario:", self.campo_comentario)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def aprobador(self) -> str:
        return self.campo_aprobador.text().strip()

    def comentario(self) -> str:
        return self.campo_comentario.toPlainText().strip()


class TextoSimpleDialog(QDialog):
    """Un solo campo de texto largo -- reutilizado por las tres acciones
    de incidencias con un solo campo (Modulo 10): asignar (responsable,
    de una linea), responder (respuesta) y cerrar (cierre). `una_linea`
    cambia el widget de entrada; el resto del dialogo es identico."""

    def __init__(self, parent=None, titulo: str = "", etiqueta: str = "", una_linea: bool = False):
        super().__init__(parent)
        self.setWindowTitle(titulo)

        self.campo: QLineEdit | QPlainTextEdit = QLineEdit() if una_linea else QPlainTextEdit()

        formulario = QFormLayout()
        formulario.addRow(etiqueta, self.campo)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def valor(self) -> str:
        # isinstance (no self._una_linea) para que Mypy pueda angostar
        # el tipo union de self.campo -- comprobar un booleano aparte no
        # le alcanza para relacionarlo con el tipo real del atributo.
        if isinstance(self.campo, QLineEdit):
            return self.campo.text().strip()
        return self.campo.toPlainText().strip()


class DecidirIncidenciaDialog(QDialog):
    """Recolecta decision + resuelta para
    IncidentsService.decidir_incidencia() (Modulo 10) -- el unico paso
    del ciclo de vida de una incidencia con dos campos a la vez."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Decidir incidencia")

        self.campo_decision = QPlainTextEdit()
        self.campo_resuelta = QCheckBox("Queda resuelta")

        formulario = QFormLayout()
        formulario.addRow("Decision:", self.campo_decision)
        formulario.addRow("", self.campo_resuelta)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(formulario)
        layout.addWidget(botones)

    def decision(self) -> str:
        return self.campo_decision.toPlainText().strip()

    def resuelta(self) -> bool:
        return self.campo_resuelta.isChecked()


def _fecha_a_texto(fecha: Optional[date]) -> str:
    return fecha.isoformat() if fecha else ""


def _texto_a_fecha(texto: str, nombre_campo: str) -> Optional[date]:
    """Convierte 'AAAA-MM-DD' a `date`; vacio -> None. Lanza ValueError
    con un mensaje en espanol simple (Documento Maestro, seccion
    4.11.1) si el texto no esta vacio pero tampoco es una fecha valida
    -- quien llama (ui.main_window) lo muestra en un QMessageBox en vez
    de dejar pasar un ValueError generico de `date.fromisoformat`."""
    texto = texto.strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValueError(f"El campo '{nombre_campo}' debe tener el formato AAAA-MM-DD, o quedar vacio.") from None
