"""EjecutarPruebasDeAceptacion (Fase 9): fachadas falsas que reutilizan
las transiciones REALES de `Documento`/`Lote` (domain.documents/
domain.batches) y escriben archivos reales en disco -- para que las
comprobaciones de contenido (lectura de `ruta_extraccion`/
`ruta_markdown`) del caso de uso se ejerciten de verdad, sin necesitar
bootstrap()/motores de extraccion reales (eso ya lo cubre el smoke
test end-to-end con el corpus real)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from application.acceptance.commands.ejecutar_pruebas_aceptacion import EjecutarPruebasDeAceptacion
from domain.batches.entities import Lote
from domain.documents.entities import (
    Aprobacion,
    Documento,
    EstadoDocumento,
    FormatoDocumento,
    Revision,
    TipoProcesamiento,
)
from domain.documents.exceptions import DuplicateDocumentHashError
from domain.validity.entities import Fuente, Vigencia


class _FakeDocumentsService:
    def __init__(self, tmp_path: Path, fallar_para: set[str] | None = None):
        self._tmp_path = tmp_path
        self._fallar_para = fallar_para or set()
        self._docs: dict[str, Documento] = {}
        self._por_hash: dict[str, str] = {}
        self._aprobaciones: dict[str, list[Aprobacion]] = {}
        self._revisiones: dict[str, list[Revision]] = {}

    def registrar_documento(self, proyecto_id: str, ruta_origen: str, **_kwargs) -> Documento:
        ruta = Path(ruta_origen)
        if ruta.name in self._fallar_para:
            raise RuntimeError(f"fallo simulado registrando {ruta.name}")
        contenido = ruta.read_bytes()
        hash_sha256 = hashlib.sha256(contenido).hexdigest()
        if hash_sha256 in self._por_hash:
            raise DuplicateDocumentHashError(hash_sha256, self._por_hash[hash_sha256])
        documento = Documento(
            proyecto_id=proyecto_id,
            nombre_original=ruta.name,
            formato=FormatoDocumento.TXT,
            ruta_origen=str(ruta),
            ruta_copia_original=str(ruta),
            hash_sha256=hash_sha256,
            tamano_bytes=len(contenido),
        )
        self._docs[documento.id] = documento
        self._por_hash[hash_sha256] = documento.id
        return documento

    def clasificar_documento(self, documento_id: str) -> Documento:
        d = self._docs[documento_id].avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        self._docs[documento_id] = d
        return d

    def extraer_documento(self, documento_id: str) -> Documento:
        ruta = self._tmp_path / f"extraccion_{documento_id}.md"
        ruta.write_text("# Titulo\n\nContenido extraido real.\n", encoding="utf-8")
        d = self._docs[documento_id].avanzar_a(EstadoDocumento.EN_EXTRACCION).completar_extraccion(str(ruta))
        self._docs[documento_id] = d
        return d

    def revisar_documento(self, documento_id: str, revisor: str, comentario: str = "", **_kwargs) -> Documento:
        d = self._docs[documento_id].avanzar_a(EstadoDocumento.EN_REVISION).avanzar_a(EstadoDocumento.REVISADO)
        self._docs[documento_id] = d
        self._revisiones.setdefault(documento_id, []).append(Revision(documento_id=documento_id, revisor=revisor, comentario=comentario))
        return d

    def normalizar_documento(self, documento_id: str) -> Documento:
        ruta = self._tmp_path / f"normalizado_{documento_id}.md"
        ruta.write_text("# Titulo\n\nContenido normalizado real.\n", encoding="utf-8")
        d = (
            self._docs[documento_id]
            .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
            .completar_normalizacion(str(ruta))
        )
        self._docs[documento_id] = d
        return d

    def aprobar_para_markdown(self, documento_id: str, aprobador: str, comentario: str = "") -> Documento:
        d = self._docs[documento_id].aprobar_para_markdown()
        self._docs[documento_id] = d
        self._aprobaciones.setdefault(documento_id, []).append(
            Aprobacion(documento_id=documento_id, aprobador=aprobador, comentario=comentario)
        )
        return d

    def generar_markdown(self, documento_id: str) -> Documento:
        ruta = self._tmp_path / f"markdown_{documento_id}.md"
        ruta.write_bytes(b"# Titulo\n\nContenido de entrega real.\n")
        # Hash real de los bytes escritos: el criterio Markdown ahora
        # verifica que hash_markdown describa el archivo (incidencia
        # 2026-09-30), asi que un hash ficticio ya no pasa.
        d = self._docs[documento_id].generar_markdown(str(ruta), hashlib.sha256(ruta.read_bytes()).hexdigest())
        self._docs[documento_id] = d
        return d

    def validar_markdown(self, documento_id: str) -> Documento:
        d = self._docs[documento_id].validar_markdown()
        self._docs[documento_id] = d
        return d

    def liberar_documento(self, documento_id: str) -> Documento:
        d = self._docs[documento_id].liberar()
        self._docs[documento_id] = d
        return d

    def obtener_documento(self, documento_id: str) -> Documento | None:
        return self._docs.get(documento_id)

    def listar_aprobaciones(self, documento_id: str) -> list[Aprobacion]:
        return self._aprobaciones.get(documento_id, [])

    def listar_revisiones(self, documento_id: str) -> list[Revision]:
        return self._revisiones.get(documento_id, [])


class _FakeValidityService:
    def __init__(self) -> None:
        self._fuentes: dict[str, Fuente] = {}
        self._vigencias: dict[str, Vigencia] = {}

    def registrar_fuente(self, documento_id: str, sistema_origen: str, autoridad: str, evidencia_consulta: str) -> Fuente:
        fuente = Fuente(documento_id=documento_id, sistema_origen=sistema_origen, autoridad=autoridad, evidencia_consulta=evidencia_consulta)
        self._fuentes[documento_id] = fuente
        return fuente

    def registrar_vigencia(self, documento_id: str, **kwargs) -> Vigencia:
        vigencia = Vigencia(documento_id=documento_id, autoridad=kwargs.get("autoridad", ""), sin_vencimiento=kwargs.get("sin_vencimiento", False), vigente_desde=kwargs.get("vigente_desde"))
        self._vigencias[documento_id] = vigencia
        return vigencia

    def obtener_fuente(self, documento_id: str) -> Fuente | None:
        return self._fuentes.get(documento_id)

    def obtener_vigencia(self, documento_id: str) -> Vigencia | None:
        return self._vigencias.get(documento_id)


class _FakeIncidentsService:
    def existen_criticas_abiertas(self, documento_id: str) -> bool:
        return False


class _FakeBatchesService:
    def __init__(self) -> None:
        self._lotes: dict[str, Lote] = {}

    def crear_lote(self, proyecto_id: str, nombre: str) -> Lote:
        lote = Lote(proyecto_id=proyecto_id, nombre=nombre)
        self._lotes[lote.id] = lote
        return lote

    def agregar_documento(self, lote_id: str, documento_id: str) -> None:
        pass

    def cerrar_lote(self, lote_id: str) -> Lote:
        cerrado = self._lotes[lote_id].cerrar()
        self._lotes[lote_id] = cerrado
        return cerrado


class _FakeReportsService:
    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path

    def generar_acta_cierre_lote(self, lote_id: str) -> str:
        ruta = self._tmp_path / f"acta_{lote_id}.md"
        ruta.write_text("acta de cierre", encoding="utf-8")
        return str(ruta)


def _caso_de_uso(tmp_path: Path, fallar_para: set[str] | None = None) -> EjecutarPruebasDeAceptacion:
    return EjecutarPruebasDeAceptacion(
        _FakeDocumentsService(tmp_path, fallar_para),
        _FakeValidityService(),
        _FakeIncidentsService(),
        _FakeBatchesService(),
        _FakeReportsService(tmp_path),
        "PROY-ACEPTACION",
    )


def test_corpus_vacio_marca_los_siete_dominios_como_pendientes(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus_vacio"
    corpus.mkdir()
    caso_de_uso = _caso_de_uso(tmp_path)

    informe = caso_de_uso.execute(corpus)

    assert informe.documentos_evaluados == []
    assert len(informe.criterios_dominio) == 7
    assert all(c.cumplido is None for c in informe.criterios_dominio)
    assert informe.esta_completo() is False
    assert informe.aprobado() is True  # pendiente no es lo mismo que fallido


def test_un_documento_real_pasa_todos_los_dominios_evaluables(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "memo.txt").write_text("Contenido real del memo.", encoding="utf-8")
    caso_de_uso = _caso_de_uso(tmp_path)

    informe = caso_de_uso.execute(corpus)

    assert informe.documentos_evaluados == ["memo.txt"]
    por_dominio = {c.dominio: c for c in informe.criterios_dominio}
    assert por_dominio["Inventario"].cumplido is True
    assert por_dominio["Extraccion"].cumplido is True
    assert por_dominio["Normalizacion"].cumplido is True
    assert por_dominio["Markdown"].cumplido is True
    assert por_dominio["Trazabilidad"].cumplido is True
    assert por_dominio["Liberacion"].cumplido is True
    assert por_dominio["OCR"].cumplido is None  # sin corpus OCR en este archivo
    assert informe.aprobado() is True


def test_umbrales_100_por_ciento_cuando_todo_sale_bien(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "memo.txt").write_text("Contenido real del memo.", encoding="utf-8")
    caso_de_uso = _caso_de_uso(tmp_path)

    informe = caso_de_uso.execute(corpus)

    por_indicador = {c.indicador: c for c in informe.criterios_umbral}
    assert por_indicador["Incidencias criticas abiertas"].valor_observado == "0"
    assert por_indicador["Documentos con hash"].valor_observado == "100%"
    assert por_indicador["Archivos liberados con aprobacion"].valor_observado == "100%"
    assert all(c.cumplido for c in informe.criterios_umbral)


def test_un_archivo_que_falla_no_aborta_la_corrida_completa(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "malo.txt").write_text("archivo que fallara al registrarse", encoding="utf-8")
    (corpus / "bueno.txt").write_text("archivo que se procesa sin problema", encoding="utf-8")
    caso_de_uso = _caso_de_uso(tmp_path, fallar_para={"malo.txt"})

    informe = caso_de_uso.execute(corpus)

    assert set(informe.documentos_evaluados) == {"malo.txt", "bueno.txt"}
    inventario = next(c for c in informe.criterios_dominio if c.dominio == "Inventario")
    assert inventario.cumplido is False
    assert "malo.txt" in inventario.detalle
    liberacion = next(c for c in informe.criterios_dominio if c.dominio == "Liberacion")
    assert liberacion.cumplido is True  # el archivo bueno si se libero correctamente


def test_registrar_el_mismo_archivo_dos_veces_detecta_el_duplicado(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "unico.txt").write_text("contenido unico", encoding="utf-8")
    caso_de_uso = _caso_de_uso(tmp_path)

    informe = caso_de_uso.execute(corpus)

    inventario = next(c for c in informe.criterios_dominio if c.dominio == "Inventario")
    assert "detectados correctamente" in inventario.detalle


@pytest.mark.parametrize("dominio", ["OCR"])
def test_dominio_sin_corpus_no_cuenta_como_falla(tmp_path: Path, dominio: str) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "memo.txt").write_text("contenido", encoding="utf-8")
    caso_de_uso = _caso_de_uso(tmp_path)

    informe = caso_de_uso.execute(corpus)

    criterio = next(c for c in informe.criterios_dominio if c.dominio == dominio)
    assert criterio.cumplido is None
    assert informe.aprobado() is True


def test_criterio_markdown_falla_si_el_hash_no_coincide_con_el_archivo(tmp_path: Path, monkeypatch) -> None:
    """Incidencia 2026-09-30: un .md con CRLF y un hash calculado sobre LF
    debe hacer fallar el criterio Markdown, no solo comprobar que existe."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "memo.txt").write_text("contenido", encoding="utf-8")
    caso_de_uso = _caso_de_uso(tmp_path)

    def generar_con_crlf(self, documento_id: str) -> Documento:
        ruta = self._tmp_path / f"markdown_{documento_id}.md"
        ruta.write_bytes(b"# Titulo\r\n\r\nContenido.\r\n")
        d = self._docs[documento_id].generar_markdown(str(ruta), hashlib.sha256(b"# Titulo\n\nContenido.\n").hexdigest())
        self._docs[documento_id] = d
        return d

    monkeypatch.setattr(_FakeDocumentsService, "generar_markdown", generar_con_crlf)

    informe = caso_de_uso.execute(corpus)

    markdown = next(c for c in informe.criterios_dominio if c.dominio == "Markdown")
    assert markdown.cumplido is False
    assert "no coincide con hash_markdown" in markdown.detalle
