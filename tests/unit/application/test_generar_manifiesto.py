"""GenerarManifiesto (Modulo 12, Documento Maestro seccion 4.6.1):
arma un `FilaManifiesto` por cada documento LIBERADO del proyecto (o de
un lote especifico, si se indica `lote_id` -- Fase 7) y lo entrega a
`ManifestWriter`."""
from __future__ import annotations

from datetime import date

import pytest

from application.documents.commands.generar_manifiesto import GenerarManifiesto
from domain.batches.entities import Lote
from domain.batches.exceptions import BatchNotFoundError
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento, EstadoDocumento, FilaManifiesto, FormatoDocumento, TipoProcesamiento
from domain.documents.ports import ManifestWriter
from domain.validity.entities import Vigencia
from domain.validity.ports import VigenciaRepository
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH_VALIDO = "4" * 64


class _FakeLoteRepository(LoteRepository):
    def __init__(self, lotes: list[Lote] | None = None) -> None:
        self._por_id: dict[str, Lote] = {lote.id: lote for lote in (lotes or [])}

    def save(self, lote: Lote) -> None:
        self._por_id[lote.id] = lote

    def get(self, lote_id: str):
        return self._por_id.get(lote_id)

    def list_by_proyecto(self, proyecto_id: str):
        return [lote for lote in self._por_id.values() if lote.proyecto_id == proyecto_id]

    def list(self):
        return list(self._por_id.values())


class _FakeVigenciaRepository(VigenciaRepository):
    def __init__(self, vigencias: list[Vigencia] | None = None) -> None:
        self._por_documento: dict[str, Vigencia] = {v.documento_id: v for v in (vigencias or [])}

    def save(self, vigencia: Vigencia) -> None:
        self._por_documento[vigencia.documento_id] = vigencia

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


class _FakeManifestWriter(ManifestWriter):
    def __init__(self) -> None:
        self.ultima_escritura: list[FilaManifiesto] | None = None

    def escribir(self, filas: list[FilaManifiesto]) -> str:
        self.ultima_escritura = filas
        return "/proyecto/12_exportaciones/manifiesto.csv"


def _documento_liberado(
    documento_id: str = "doc-1",
    hash_sha256: str = _HASH_VALIDO,
    metadatos: dict[str, str] | None = None,
    estado_final: EstadoDocumento = EstadoDocumento.LIBERADO,
    lote_id: str | None = None,
    ruta_markdown: str | None = None,
) -> Documento:
    documento = Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=hash_sha256,
        tamano_bytes=1024,
        metadatos=metadatos or {},
        lote_id=lote_id,
    )
    documento = (
        documento.avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion("/proyecto/06_normalizados/doc.md")
        .aprobar_para_markdown()
        .generar_markdown(ruta_markdown or f"/proyecto/07_markdown/{documento_id}.md", "hash-markdown-de-prueba")
        .validar_markdown()
    )
    if estado_final == EstadoDocumento.LIBERADO:
        documento = documento.liberar()
    return documento


def test_manifiesto_vacio_si_no_hay_documentos_liberados() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado(estado_final=EstadoDocumento.VALIDADO))  # no liberado
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    ruta = caso_de_uso.execute()

    assert ruta == "/proyecto/12_exportaciones/manifiesto.csv"
    assert writer.ultima_escritura == []


def test_manifiesto_solo_incluye_documentos_liberados() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1"))
    repo.save(_documento_liberado("doc-2", hash_sha256="5" * 64, estado_final=EstadoDocumento.VALIDADO))
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()

    assert len(writer.ultima_escritura) == 1
    # Solo el nombre de archivo, nunca la ruta absoluta completa --
    # incidencia real de portabilidad Windows -> macOS (ver docstring de
    # FilaManifiesto.ruta_archivo y generar_manifiesto._fila_de()).
    assert writer.ultima_escritura[0].ruta_archivo == "doc-1.md"


def test_fila_de_manifiesto_usa_metadatos_y_hash_markdown() -> None:
    repo = _FakeDocumentRepository()
    metadatos = {
        "titulo_oficial": "Politica de vacaciones",
        "area_propietaria": "rh",
        "nivel_confidencialidad": "interno",
    }
    repo.save(_documento_liberado("doc-1", metadatos=metadatos))
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()

    fila = writer.ultima_escritura[0]
    assert fila.titulo == "Politica de vacaciones"
    assert fila.tipo_fuente == "markdown"
    assert fila.area_propietaria == "rh"
    assert fila.nivel_acceso == "interno"
    assert fila.idioma == "es"
    assert fila.hash_contenido == "hash-markdown-de-prueba"
    assert fila.autoridad_fuente is None


def test_fila_de_manifiesto_reduce_ruta_windows_a_solo_nombre_de_archivo() -> None:
    """Incidencia real de portabilidad (2026-09-29): si este proceso
    corriera en Windows, `Documento.ruta_markdown` traeria una ruta con
    backslashes (p. ej. "C:\\Users\\...\\07_markdown\\doc-1.md"). Antes
    de esta correccion, esa cadena completa se transcribia tal cual a
    `FilaManifiesto.ruta_archivo`, y RAG STUDIO no podia resolverla en un
    equipo distinto (macOS/Linux). `_fila_de()` ahora se queda solo con
    el nombre de archivo -- valido sin importar en que sistema operativo
    se genero ni en cual se importa despues."""
    repo = _FakeDocumentRepository()
    repo.save(
        _documento_liberado(
            "doc-1",
            ruta_markdown="C:\\Users\\sopor\\RAG Content Studio Desktop\\proyectos\\PROY-9928\\07_markdown\\doc-1.md",
        )
    )
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()

    assert writer.ultima_escritura[0].ruta_archivo == "doc-1.md"


def test_fila_de_manifiesto_sin_titulo_oficial_usa_nombre_original() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1", metadatos={}))
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()

    assert writer.ultima_escritura[0].titulo == "politica.pdf"


def test_fila_de_manifiesto_incluye_vigencia_si_esta_registrada() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1"))
    vigencia = Vigencia(
        documento_id="doc-1",
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 12, 31),
        autoridad="Direccion Juridica",
        sustituye_a="doc-0",
    )
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository([vigencia]), writer)

    caso_de_uso.execute()

    fila = writer.ultima_escritura[0]
    assert fila.vigente_desde == "2026-01-01"
    assert fila.vigente_hasta == "2026-12-31"
    assert fila.sustituye_a == "doc-0"


def test_fila_de_manifiesto_sin_vigencia_registrada_deja_campos_vacios() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1"))
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()

    fila = writer.ultima_escritura[0]
    assert fila.vigente_desde is None
    assert fila.vigente_hasta is None
    assert fila.sustituye_a is None


def test_sin_lote_id_incluye_liberados_de_cualquier_lote_o_sin_lote() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1", lote_id="LOTE-1"))
    repo.save(_documento_liberado("doc-2", hash_sha256="6" * 64, lote_id=None))
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()  # lote_id=None (predeterminado) -- comportamiento sin cambios desde la Fase 5

    assert {f.ruta_archivo for f in writer.ultima_escritura} == {"doc-1.md", "doc-2.md"}


def test_con_lote_id_solo_incluye_liberados_de_ese_lote() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1", lote_id="LOTE-1"))
    repo.save(_documento_liberado("doc-2", hash_sha256="6" * 64, lote_id="LOTE-2"))
    repo.save(_documento_liberado("doc-3", hash_sha256="7" * 64, lote_id=None))
    writer = _FakeManifestWriter()
    lote_repository = _FakeLoteRepository([Lote(id="LOTE-1", proyecto_id="PROY-0001", nombre="Lote 1")])
    caso_de_uso = GenerarManifiesto(repo, lote_repository, _FakeVigenciaRepository(), writer)

    caso_de_uso.execute(lote_id="LOTE-1")

    assert len(writer.ultima_escritura) == 1
    assert writer.ultima_escritura[0].ruta_archivo == "doc-1.md"


def test_lote_id_inexistente_lanza_batch_not_found_error() -> None:
    """Hallazgo real de la cuarta auditoria general (2026-08-01): antes de
    depender de LoteRepository, un `lote_id` con un typo (o de un lote ya
    borrado) no producia ningun aviso -- simplemente filtraba a una lista
    vacia y generaba en silencio un manifiesto vacio. Ahora debe fallar de
    forma explicita, igual que AgregarDocumentoALote."""
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1", lote_id="LOTE-1"))
    writer = _FakeManifestWriter()
    caso_de_uso = GenerarManifiesto(repo, _FakeLoteRepository(), _FakeVigenciaRepository(), writer)

    with pytest.raises(BatchNotFoundError):
        caso_de_uso.execute(lote_id="LOTE-QUE-NO-EXISTE")

    assert writer.ultima_escritura is None
