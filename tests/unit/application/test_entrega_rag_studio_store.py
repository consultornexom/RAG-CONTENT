"""LocalEntregaRagStudioStore (Modulo 12, agregado 2026-07-31) -- mismo
criterio de prueba que test_csv_manifest_writer.py: carpeta creada al
vuelo, contenido determinista (se borra y se rehace en cada llamada,
nunca acumula archivos de una corrida anterior)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from infrastructure.filesystem.entrega_rag_studio_store import LocalEntregaRagStudioStore

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_entrega_rag_studio_store_test")


@pytest.fixture()
def raiz():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _crear_archivo(ruta: Path, contenido: str = "contenido") -> str:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return str(ruta)


def test_preparar_crea_la_carpeta_y_copia_el_manifiesto_y_los_markdown(raiz: Path) -> None:
    carpeta_entrega = raiz / "14_entrega_rag_studio"
    ruta_manifiesto = _crear_archivo(raiz / "12_exportaciones" / "manifiesto.csv", "titulo,ruta_archivo\n")
    ruta_md_1 = _crear_archivo(raiz / "07_markdown" / "doc-1.md", "# Doc 1")
    ruta_md_2 = _crear_archivo(raiz / "07_markdown" / "doc-2.md", "# Doc 2")

    store = LocalEntregaRagStudioStore(carpeta_entrega)
    ruta_devuelta = store.preparar(ruta_manifiesto, [ruta_md_1, ruta_md_2])

    assert ruta_devuelta == str(carpeta_entrega)
    assert (carpeta_entrega / "manifiesto.csv").read_text(encoding="utf-8") == "titulo,ruta_archivo\n"
    assert (carpeta_entrega / "doc-1.md").read_text(encoding="utf-8") == "# Doc 1"
    assert (carpeta_entrega / "doc-2.md").read_text(encoding="utf-8") == "# Doc 2"


def test_preparar_sin_documentos_liberados_deja_solo_el_manifiesto(raiz: Path) -> None:
    carpeta_entrega = raiz / "14_entrega_rag_studio"
    ruta_manifiesto = _crear_archivo(raiz / "12_exportaciones" / "manifiesto.csv", "titulo,ruta_archivo\n")

    store = LocalEntregaRagStudioStore(carpeta_entrega)
    store.preparar(ruta_manifiesto, [])

    assert list(carpeta_entrega.iterdir()) == [carpeta_entrega / "manifiesto.csv"]


def test_preparar_dos_veces_no_acumula_archivos_de_la_corrida_anterior(raiz: Path) -> None:
    carpeta_entrega = raiz / "14_entrega_rag_studio"
    ruta_manifiesto = _crear_archivo(raiz / "12_exportaciones" / "manifiesto.csv", "titulo,ruta_archivo\n")
    ruta_md_1 = _crear_archivo(raiz / "07_markdown" / "doc-1.md", "# Doc 1")
    ruta_md_2 = _crear_archivo(raiz / "07_markdown" / "doc-2.md", "# Doc 2")

    store = LocalEntregaRagStudioStore(carpeta_entrega)
    store.preparar(ruta_manifiesto, [ruta_md_1, ruta_md_2])
    # "doc-2" ya no esta LIBERADO en la segunda corrida (por ejemplo, se
    # bloqueo) -- su copia de la corrida anterior no debe seguir aqui.
    store.preparar(ruta_manifiesto, [ruta_md_1])

    nombres = sorted(p.name for p in carpeta_entrega.iterdir())
    assert nombres == ["doc-1.md", "manifiesto.csv"]


def _manifiesto_con_hash(ruta: Path, filas: list[tuple[str, str]]) -> str:
    lineas = ["manifest_schema_version,titulo,ruta_archivo,hash_contenido"]
    lineas += [f"2,{nombre},{nombre},{hash_}" for nombre, hash_ in filas]
    return _crear_archivo(ruta, "\n".join(lineas) + "\n")


def test_preparar_verifica_el_hash_de_cada_markdown_contra_el_manifiesto(raiz: Path) -> None:
    import hashlib

    ruta_md = raiz / "07_markdown" / "doc-1.md"
    ruta_md.parent.mkdir(parents=True)
    ruta_md.write_bytes(b"# Doc 1\n\nLinea.\n")
    hash_ok = hashlib.sha256(ruta_md.read_bytes()).hexdigest()
    ruta_manifiesto = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto.csv", [("doc-1.md", hash_ok)])

    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")
    store.preparar(ruta_manifiesto, [str(ruta_md)])

    assert (raiz / "14_entrega_rag_studio" / "doc-1.md").read_bytes() == b"# Doc 1\n\nLinea.\n"


def test_preparar_rechaza_un_markdown_con_crlf_cuyo_hash_se_calculo_con_lf(raiz: Path) -> None:
    """Regresion de la incidencia 2026-09-30: el productor no debe dejar
    lista una entrega que RAG STUDIO rechazara al importar."""
    import hashlib

    from domain.documents.exceptions import EntregaIntegridadError

    ruta_md = raiz / "07_markdown" / "doc-1.md"
    ruta_md.parent.mkdir(parents=True)
    ruta_md.write_bytes(b"# Doc 1\r\n\r\nLinea.\r\n")  # como lo dejaba Windows
    hash_lf = hashlib.sha256(b"# Doc 1\n\nLinea.\n").hexdigest()  # como se declaraba
    ruta_manifiesto = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto.csv", [("doc-1.md", hash_lf)])

    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")
    with pytest.raises(EntregaIntegridadError) as error:
        store.preparar(ruta_manifiesto, [str(ruta_md)])

    assert "doc-1.md" in str(error.value)
    assert not (raiz / "14_entrega_rag_studio").exists()  # no queda una entrega invalida


def test_preparar_rechaza_si_falta_un_markdown_declarado(raiz: Path) -> None:
    from domain.documents.exceptions import EntregaIntegridadError

    ruta_manifiesto = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto.csv", [("doc-x.md", "a" * 64)])

    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")
    with pytest.raises(EntregaIntegridadError):
        store.preparar(ruta_manifiesto, [])


def test_preparar_nombra_la_copia_igual_que_ruta_archivo_del_manifiesto(raiz: Path) -> None:
    """Auditoria 2026-09-30: la copia se nombraba con `Path(ruta).name`,
    que en macOS/Linux no separa una ruta con "\\" (Windows), mientras el
    manifiesto usa el ultimo segmento con cualquier separador. En POSIX
    "\\" es un caracter valido de nombre, lo que permite reproducirlo."""
    import hashlib

    ruta_md = raiz / "07_markdown" / "C:\\proyecto\\07_markdown\\doc-1.md"
    ruta_md.parent.mkdir(parents=True)
    ruta_md.write_bytes(b"# Doc 1\n")
    ruta_manifiesto = _manifiesto_con_hash(
        raiz / "12_exportaciones" / "manifiesto.csv", [("doc-1.md", hashlib.sha256(b"# Doc 1\n").hexdigest())]
    )

    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")
    store.preparar(ruta_manifiesto, [str(ruta_md)])

    assert (raiz / "14_entrega_rag_studio" / "doc-1.md").read_bytes() == b"# Doc 1\n"


# ---------- Entregas separadas por lote, con version (2026-10-03, NEXOM) ----------

def test_preparar_con_identificador_entrega_crea_subcarpeta_v1(raiz: Path) -> None:
    ruta_manifiesto = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto.csv", [])
    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")

    ruta_devuelta = store.preparar(ruta_manifiesto, [], identificador_entrega="LOTE-1_Diplomados")

    esperada = raiz / "14_entrega_rag_studio" / "LOTE-1_Diplomados" / "v1"
    assert ruta_devuelta == str(esperada)
    assert (esperada / "manifiesto.csv").is_file()


def test_preparar_dos_veces_el_mismo_lote_crea_v2_y_conserva_v1(raiz: Path) -> None:
    ruta_manifiesto = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto.csv", [])
    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")

    ruta_v1 = store.preparar(ruta_manifiesto, [], identificador_entrega="LOTE-1_Diplomados")
    ruta_v2 = store.preparar(ruta_manifiesto, [], identificador_entrega="LOTE-1_Diplomados")

    assert ruta_v1.endswith("/v1")
    assert ruta_v2.endswith("/v2")
    assert Path(ruta_v1).is_dir()  # la version anterior sigue intacta -- nunca se sobrescribe ni se borra.
    assert (Path(ruta_v1) / "manifiesto.csv").is_file()
    assert (Path(ruta_v2) / "manifiesto.csv").is_file()


def test_preparar_un_lote_distinto_no_toca_la_entrega_de_otro_lote(raiz: Path) -> None:
    ruta_manifiesto = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto.csv", [])
    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")

    ruta_licenciaturas = store.preparar(ruta_manifiesto, [], identificador_entrega="LOTE-1_Licenciaturas")
    ruta_diplomados = store.preparar(ruta_manifiesto, [], identificador_entrega="LOTE-2_Diplomados")

    # El caso real reportado: cerrar/exportar el lote de diplomados NO
    # debe eliminar ni mezclarse con la entrega ya hecha de licenciaturas.
    assert Path(ruta_licenciaturas).is_dir()
    assert (Path(ruta_licenciaturas) / "manifiesto.csv").is_file()
    assert Path(ruta_diplomados).is_dir()
    assert ruta_licenciaturas != ruta_diplomados


def test_preparar_entrega_de_lote_no_toca_ni_borra_la_entrega_del_proyecto_completo(raiz: Path) -> None:
    """La entrega de "todo el proyecto" (identificador_entrega=None seguro
    de siempre) y la de un lote especifico conviven en la misma carpeta
    raiz, en ramas separadas -- ninguna de las dos operaciones hace
    `rmtree` sobre lo que pertenece a la otra."""
    ruta_manifiesto = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto.csv", [])
    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")

    ruta_proyecto_completo = store.preparar(ruta_manifiesto, [])  # identificador_entrega=None, como siempre
    ruta_lote = store.preparar(ruta_manifiesto, [], identificador_entrega="LOTE-1_Diplomados")
    # Volver a preparar la entrega de TODO el proyecto no debe tocar la
    # subcarpeta de lotes que vive junto a ella.
    store.preparar(ruta_manifiesto, [])

    assert Path(ruta_proyecto_completo).is_dir()
    assert Path(ruta_lote).is_dir()
    assert (Path(ruta_proyecto_completo) / "LOTE-1_Diplomados").is_dir()


def test_preparar_rechaza_integridad_de_una_version_de_lote_sin_borrar_versiones_anteriores(raiz: Path) -> None:
    """Si una version nueva de un lote falla la verificacion de
    integridad, solo esa version se descarta -- las versiones anteriores
    de ese mismo lote (ya entregadas correctamente) deben seguir
    intactas, igual que la entrega de cualquier otro lote."""
    from domain.documents.exceptions import EntregaIntegridadError

    ruta_md = raiz / "07_markdown" / "doc-1.md"
    ruta_md.parent.mkdir(parents=True)
    ruta_md.write_bytes(b"# Doc 1\n")
    # Dos archivos de manifiesto DISTINTOS (rutas distintas) -- si
    # compartieran la misma ruta, escribir el segundo sobreescribiria el
    # contenido del primero en disco antes de que la primera llamada a
    # preparar() lo copie, y la prueba dejaria de probar lo que dice.
    ruta_manifiesto_v1 = _manifiesto_con_hash(raiz / "12_exportaciones" / "manifiesto_v1.csv", [])
    ruta_manifiesto_v2 = _manifiesto_con_hash(
        raiz / "12_exportaciones" / "manifiesto_v2.csv", [("doc-1.md", "a" * 64)]
    )
    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")
    ruta_v1 = store.preparar(ruta_manifiesto_v1, [], identificador_entrega="LOTE-1_Diplomados")

    with pytest.raises(EntregaIntegridadError):
        store.preparar(ruta_manifiesto_v2, [str(ruta_md)], identificador_entrega="LOTE-1_Diplomados")

    assert Path(ruta_v1).is_dir()  # v1 sigue intacta
    assert not (Path(ruta_v1).parent / "v2").exists()  # v2 (la que fallo) no queda a medias


def test_preparar_acepta_un_manifiesto_con_bom(raiz: Path) -> None:
    """Si alguien abre y guarda el manifiesto con Excel (agrega BOM), la
    verificacion no debe perder la columna `hash_contenido`."""
    import hashlib

    ruta_md = raiz / "07_markdown" / "doc-1.md"
    ruta_md.parent.mkdir(parents=True)
    ruta_md.write_bytes(b"# Doc 1\n")
    ruta_manifiesto = raiz / "12_exportaciones" / "manifiesto.csv"
    ruta_manifiesto.parent.mkdir(parents=True)
    ruta_manifiesto.write_bytes(
        b"\xef\xbb\xbfhash_contenido,titulo,ruta_archivo\n" + hashlib.sha256(b"otro").hexdigest().encode() + b",Doc,doc-1.md\n"
    )

    from domain.documents.exceptions import EntregaIntegridadError

    store = LocalEntregaRagStudioStore(raiz / "14_entrega_rag_studio")
    with pytest.raises(EntregaIntegridadError):  # con "utf-8" la columna se perdia y no se verificaba nada
        store.preparar(str(ruta_manifiesto), [str(ruta_md)])
