"""PrepararEntregaRagStudio (Modulo 12, agregado 2026-07-31, comentario
real del consultor): reusa GenerarManifiesto (refresca 12_exportaciones/
sin cambiar su contenido) y ademas manda a copiar el manifiesto y cada
Markdown LIBERADO a la carpeta consolidada -- ver domain.documents.
ports.EntregaRagStudioStore."""
from __future__ import annotations

import pytest

from application.documents.commands.generar_manifiesto import GenerarManifiesto
from application.documents.commands.preparar_entrega_rag_studio import PrepararEntregaRagStudio
from domain.batches.entities import Lote
from domain.batches.exceptions import BatchNotFoundError
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento, EstadoDocumento, FilaManifiesto, FormatoDocumento, TipoProcesamiento
from domain.documents.ports import DocumentRepository, EntregaRagStudioStore, ManifestWriter
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
    def save(self, vigencia) -> None:
        raise NotImplementedError

    def get_by_document(self, documento_id: str):
        return None


class _FakeManifestWriter(ManifestWriter):
    def escribir(self, filas: list[FilaManifiesto]) -> str:
        return "/proyecto/12_exportaciones/manifiesto.csv"


class _FakeEntregaRagStudioStore(EntregaRagStudioStore):
    def __init__(self) -> None:
        self.ultima_llamada: tuple[str, list[str], str | None] | None = None

    def preparar(
        self, ruta_manifiesto: str, rutas_markdown: list[str], identificador_entrega: str | None = None
    ) -> str:
        self.ultima_llamada = (ruta_manifiesto, list(rutas_markdown), identificador_entrega)
        return "/proyecto/14_entrega_rag_studio"


def _documento_liberado(
    documento_id: str = "doc-1",
    hash_sha256: str = _HASH_VALIDO,
    estado_final: EstadoDocumento = EstadoDocumento.LIBERADO,
    lote_id: str | None = None,
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
        .generar_markdown(f"/proyecto/07_markdown/{documento_id}.md", "hash-markdown-de-prueba")
        .validar_markdown()
    )
    if estado_final == EstadoDocumento.LIBERADO:
        documento = documento.liberar()
    return documento


def _caso_de_uso(
    repo: DocumentRepository, entrega_store: _FakeEntregaRagStudioStore, lotes: list[Lote] | None = None
) -> PrepararEntregaRagStudio:
    lote_repository = _FakeLoteRepository(lotes)
    generar_manifiesto = GenerarManifiesto(repo, lote_repository, _FakeVigenciaRepository(), _FakeManifestWriter())
    return PrepararEntregaRagStudio(repo, generar_manifiesto, entrega_store, lote_repository)


def test_devuelve_la_ruta_de_la_carpeta_de_entrega() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1"))
    store = _FakeEntregaRagStudioStore()
    caso_de_uso = _caso_de_uso(repo, store)

    ruta = caso_de_uso.execute()

    assert ruta == "/proyecto/14_entrega_rag_studio"


def test_pasa_la_ruta_del_manifiesto_y_los_markdown_liberados_al_store() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1"))
    repo.save(_documento_liberado("doc-2", hash_sha256="5" * 64))
    store = _FakeEntregaRagStudioStore()
    caso_de_uso = _caso_de_uso(repo, store)

    caso_de_uso.execute()

    ruta_manifiesto, rutas_markdown, identificador_entrega = store.ultima_llamada
    assert ruta_manifiesto == "/proyecto/12_exportaciones/manifiesto.csv"
    assert set(rutas_markdown) == {"/proyecto/07_markdown/doc-1.md", "/proyecto/07_markdown/doc-2.md"}
    # Entrega de TODO el proyecto (sin lote_id) -- sin identificador, mismo
    # comportamiento de siempre (carpeta raiz fija).
    assert identificador_entrega is None


def test_documentos_no_liberados_no_se_incluyen() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1"))
    repo.save(_documento_liberado("doc-2", hash_sha256="5" * 64, estado_final=EstadoDocumento.VALIDADO))
    store = _FakeEntregaRagStudioStore()
    caso_de_uso = _caso_de_uso(repo, store)

    caso_de_uso.execute()

    _ruta_manifiesto, rutas_markdown, _identificador_entrega = store.ultima_llamada
    assert rutas_markdown == ["/proyecto/07_markdown/doc-1.md"]


def test_con_lote_id_solo_incluye_los_markdown_de_ese_lote() -> None:
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1", lote_id="LOTE-1"))
    repo.save(_documento_liberado("doc-2", hash_sha256="5" * 64, lote_id="LOTE-2"))
    store = _FakeEntregaRagStudioStore()
    lote_1 = Lote(id="LOTE-1", proyecto_id="PROY-0001", nombre="Lote 1")
    caso_de_uso = _caso_de_uso(repo, store, lotes=[lote_1])

    caso_de_uso.execute(lote_id="LOTE-1")

    _ruta_manifiesto, rutas_markdown, identificador_entrega = store.ultima_llamada
    assert rutas_markdown == ["/proyecto/07_markdown/doc-1.md"]
    # Entregas separadas por lote (2026-10-03): se le pasa al store un
    # identificador derivado del lote -- "<id>_<nombre convertido a
    # carpeta segura>" -- para que escriba en su propia subcarpeta
    # versionada, nunca en la carpeta raiz compartida.
    assert identificador_entrega == "LOTE-1_Lote_1"


def test_con_lote_id_pero_sin_lote_repository_configurado_falla_explicito() -> None:
    """PrepararEntregaRagStudio necesita lote_repository para leer el
    nombre del lote y armar el identificador de la subcarpeta -- un
    ensamblado incompleto (por ejemplo, un DocumentsService construido
    sin lote_repository) debe fallar con un mensaje claro, nunca
    entregar en un identificador generico o en la carpeta raiz sin
    avisar."""
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1", lote_id="LOTE-1"))
    store = _FakeEntregaRagStudioStore()
    lote_1 = Lote(id="LOTE-1", proyecto_id="PROY-0001", nombre="Lote 1")
    lote_repository = _FakeLoteRepository([lote_1])
    generar_manifiesto = GenerarManifiesto(repo, lote_repository, _FakeVigenciaRepository(), _FakeManifestWriter())
    caso_de_uso = PrepararEntregaRagStudio(repo, generar_manifiesto, store)  # sin lote_repository

    with pytest.raises(RuntimeError):
        caso_de_uso.execute(lote_id="LOTE-1")

    assert store.ultima_llamada is None


def test_lote_id_inexistente_lanza_batch_not_found_error_y_no_llama_al_store() -> None:
    """Hallazgo real de la cuarta auditoria general (2026-08-01): reusa
    GenerarManifiesto.execute(), asi que un lote_id inexistente debe
    fallar aqui tambien -- antes generaba en silencio una carpeta de
    entrega vacia."""
    repo = _FakeDocumentRepository()
    repo.save(_documento_liberado("doc-1", lote_id="LOTE-1"))
    store = _FakeEntregaRagStudioStore()
    caso_de_uso = _caso_de_uso(repo, store)  # sin lotes registrados

    with pytest.raises(BatchNotFoundError):
        caso_de_uso.execute(lote_id="LOTE-QUE-NO-EXISTE")

    assert store.ultima_llamada is None


def test_sin_documentos_liberados_llama_al_store_con_lista_vacia() -> None:
    repo = _FakeDocumentRepository()
    store = _FakeEntregaRagStudioStore()
    caso_de_uso = _caso_de_uso(repo, store)

    caso_de_uso.execute()

    _ruta_manifiesto, rutas_markdown, _identificador_entrega = store.ultima_llamada
    assert rutas_markdown == []
