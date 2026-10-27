"""scripts/reparar_fin_de_linea_markdown.py (incidencia 2026-09-30):
repara solo archivos cuya UNICA diferencia con el hash declarado son los
fines de linea CRLF; nunca toca el hash ni un archivo con una diferencia
real de contenido."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from scripts import reparar_fin_de_linea_markdown as reparar

_LF = b"# Programa\n\nLinea 1.\nLinea 2.\n"
_CRLF = _LF.replace(b"\n", b"\r\n")
_HASH_LF = hashlib.sha256(_LF).hexdigest()


def _entrega(carpeta: Path, archivos: dict[str, tuple[bytes, str]]) -> Path:
    carpeta.mkdir(parents=True)
    lineas = ["manifest_schema_version,titulo,ruta_archivo,hash_contenido"]
    for nombre, (datos, hash_declarado) in archivos.items():
        (carpeta / nombre).write_bytes(datos)
        lineas.append(f"2,{nombre},{nombre},{hash_declarado}")
    (carpeta / "manifiesto.csv").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return carpeta


def test_simulacion_no_modifica_nada(tmp_path: Path) -> None:
    carpeta = _entrega(tmp_path / "14_entrega_rag_studio", {"a.md": (_CRLF, _HASH_LF)})

    codigo = reparar.main([str(carpeta)])

    assert codigo == 1  # queda un archivo pendiente de reparar
    assert (carpeta / "a.md").read_bytes() == _CRLF
    assert not list(tmp_path.glob("*_respaldo_crlf_*"))


def test_aplicar_repara_solo_crlf_y_respalda_el_original(tmp_path: Path) -> None:
    carpeta = _entrega(
        tmp_path / "14_entrega_rag_studio",
        {"a.md": (_CRLF, _HASH_LF), "b.md": (_LF, _HASH_LF)},
    )

    codigo = reparar.main([str(carpeta), "--aplicar"])

    assert codigo == 0
    assert (carpeta / "a.md").read_bytes() == _LF
    assert (carpeta / "b.md").read_bytes() == _LF
    respaldos = list(tmp_path.glob("14_entrega_rag_studio_respaldo_crlf_*"))
    assert len(respaldos) == 1
    assert (respaldos[0] / "a.md").read_bytes() == _CRLF  # solo se respalda lo que se toco
    assert not (respaldos[0] / "b.md").exists()
    # el manifiesto (y por tanto el hash declarado) no se modifica
    assert _HASH_LF in (carpeta / "manifiesto.csv").read_text(encoding="utf-8")


def test_diferencia_real_de_contenido_no_se_toca(tmp_path: Path) -> None:
    alterado = _CRLF.replace(b"Linea 2", b"Linea X")
    carpeta = _entrega(tmp_path / "entrega", {"a.md": (alterado, _HASH_LF)})

    codigo = reparar.main([str(carpeta), "--aplicar"])

    assert codigo == 1
    assert (carpeta / "a.md").read_bytes() == alterado


def test_archivo_faltante_se_informa(tmp_path: Path) -> None:
    carpeta = _entrega(tmp_path / "entrega", {})
    with (carpeta / "manifiesto.csv").open("a", encoding="utf-8") as f:
        f.write(f"2,falta,falta.md,{_HASH_LF}\n")

    assert reparar.main([str(carpeta)]) == 1


def test_modo_proyecto_usa_hash_markdown_de_proyecto_db(tmp_path: Path) -> None:
    proyecto = tmp_path / "PROY-0001_udl"
    (proyecto / "07_markdown").mkdir(parents=True)
    (proyecto / "07_markdown" / "doc-1.md").write_bytes(_CRLF)
    conexion = sqlite3.connect(proyecto / "proyecto.db")
    conexion.execute("CREATE TABLE documentos (nombre_original TEXT, ruta_markdown TEXT, hash_markdown TEXT)")
    # ruta absoluta de Windows, tal como la guarda un proyecto procesado alli
    conexion.execute(
        "INSERT INTO documentos VALUES (?, ?, ?)",
        ("UDL_programa.pdf", r"C:\Users\op\RAG\proyectos\PROY-0001_udl\07_markdown\doc-1.md", _HASH_LF),
    )
    conexion.commit()
    conexion.close()

    codigo = reparar.main([str(proyecto), "--aplicar"])

    assert codigo == 0
    assert (proyecto / "07_markdown" / "doc-1.md").read_bytes() == _LF
    assert list(proyecto.glob("_respaldo_crlf_*/07_markdown/doc-1.md"))


def test_carpeta_sin_manifiesto_ni_proyecto_es_error_de_uso(tmp_path: Path) -> None:
    assert reparar.main([str(tmp_path)]) == 2


def test_dos_filas_al_mismo_archivo_respaldan_el_original_una_sola_vez(tmp_path: Path) -> None:
    """Auditoria 2026-09-30: con dos filas apuntando al mismo archivo, la
    segunda copia de respaldo pisaba el original con la version reparada."""
    carpeta = _entrega(tmp_path / "entrega", {"a.md": (_CRLF, _HASH_LF)})
    with (carpeta / "manifiesto.csv").open("a", encoding="utf-8") as f:
        f.write(f"2,a otra vez,a.md,{_HASH_LF}\n")

    assert reparar.main([str(carpeta), "--aplicar"]) == 0

    respaldo = next(tmp_path.glob("entrega_respaldo_crlf_*"))
    assert (respaldo / "a.md").read_bytes() == _CRLF
    assert (carpeta / "a.md").read_bytes() == _LF


def test_filas_ambiguas_con_hash_distinto_no_se_reparan(tmp_path: Path) -> None:
    carpeta = _entrega(tmp_path / "entrega", {"a.md": (_CRLF, _HASH_LF)})
    with (carpeta / "manifiesto.csv").open("a", encoding="utf-8") as f:
        f.write(f"2,a ambigua,a.md,{'b' * 64}\n")

    assert reparar.main([str(carpeta), "--aplicar"]) == 1
    assert (carpeta / "a.md").read_bytes() == _CRLF


def test_ruta_v2_fuera_de_la_carpeta_nunca_se_escribe(tmp_path: Path) -> None:
    afuera = tmp_path / "afuera.md"
    afuera.write_bytes(_CRLF)
    carpeta = _entrega(tmp_path / "entrega", {})
    with (carpeta / "manifiesto.csv").open("a", encoding="utf-8") as f:
        f.write(f"2,escape,../afuera.md,{_HASH_LF}\n")

    assert reparar.main([str(carpeta), "--aplicar"]) == 1
    assert afuera.read_bytes() == _CRLF


def test_ruta_v2_relativa_con_subcarpeta_se_respeta(tmp_path: Path) -> None:
    carpeta = _entrega(tmp_path / "entrega", {})
    (carpeta / "sub").mkdir()
    (carpeta / "sub" / "a.md").write_bytes(_CRLF)
    with (carpeta / "manifiesto.csv").open("a", encoding="utf-8") as f:
        f.write(f"2,sub,sub/a.md,{_HASH_LF}\n")

    assert reparar.main([str(carpeta), "--aplicar"]) == 0
    assert (carpeta / "sub" / "a.md").read_bytes() == _LF
    assert (next(tmp_path.glob("entrega_respaldo_crlf_*")) / "sub" / "a.md").read_bytes() == _CRLF


def test_manifiesto_con_bom_se_lee(tmp_path: Path) -> None:
    carpeta = tmp_path / "entrega"
    carpeta.mkdir()
    (carpeta / "a.md").write_bytes(_CRLF)
    (carpeta / "manifiesto.csv").write_bytes(
        b"\xef\xbb\xbfmanifest_schema_version,titulo,ruta_archivo,hash_contenido\n2,a,a.md," + _HASH_LF.encode() + b"\n"
    )

    assert reparar.main([str(carpeta), "--aplicar"]) == 0
    assert (carpeta / "a.md").read_bytes() == _LF
