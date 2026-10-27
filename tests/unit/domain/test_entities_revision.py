from __future__ import annotations

import pytest

from domain.documents.entities import Revision


def test_revision_nace_con_comentario_vacio_y_sin_incidencias() -> None:
    revision = Revision(documento_id="doc-1", revisor="ana@nexom.mx")
    assert revision.comentario == ""
    assert revision.incidencias_detectadas == []
    assert revision.id


def test_revision_acepta_comentario_e_incidencias_detectadas() -> None:
    revision = Revision(
        documento_id="doc-1",
        revisor="ana@nexom.mx",
        comentario="Se coteja contra el original, todo correcto salvo una cifra.",
        incidencias_detectadas=["inc-1", "inc-2"],
    )
    assert revision.comentario == "Se coteja contra el original, todo correcto salvo una cifra."
    assert revision.incidencias_detectadas == ["inc-1", "inc-2"]


def test_revisor_vacio_es_rechazado() -> None:
    with pytest.raises(ValueError):
        Revision(documento_id="doc-1", revisor="   ")


def test_cada_revision_tiene_id_propio() -> None:
    primera = Revision(documento_id="doc-1", revisor="ana@nexom.mx")
    segunda = Revision(documento_id="doc-1", revisor="ana@nexom.mx")
    assert primera.id != segunda.id
