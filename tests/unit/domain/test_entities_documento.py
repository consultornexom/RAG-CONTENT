from __future__ import annotations

import pytest

from domain.documents.entities import Aprobacion, Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.exceptions import CorreccionRequiereEstadoExtraidoError, InvalidDocumentStateTransitionError

_HASH_VALIDO = "a" * 64


def _documento(**overrides) -> Documento:
    datos = {
        "proyecto_id": "PROY-0001",
        "nombre_original": "politica_vacaciones.pdf",
        "formato": FormatoDocumento.PDF,
        "ruta_origen": "/tmp/origen/politica_vacaciones.pdf",
        "ruta_copia_original": "/media/disco/Data/RAG CONTENT STUDIO/proyectos/PROY-0001_x/01_originales/abc_politica_vacaciones.pdf",
        "hash_sha256": _HASH_VALIDO,
        "tamano_bytes": 1024,
    }
    datos.update(overrides)
    return Documento(**datos)


def test_documento_nace_en_estado_recibido() -> None:
    documento = _documento()
    assert documento.estado == EstadoDocumento.RECIBIDO


def test_hash_invalido_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _documento(hash_sha256="no-es-un-hash")


def test_nombre_original_vacio_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _documento(nombre_original="   ")


def test_tamano_negativo_es_rechazado() -> None:
    with pytest.raises(ValueError):
        _documento(tamano_bytes=-1)


def test_avanzar_de_recibido_a_inventariado_es_valido() -> None:
    documento = _documento().avanzar_a(EstadoDocumento.INVENTARIADO)
    assert documento.estado == EstadoDocumento.INVENTARIADO


def test_no_se_puede_saltar_un_paso_del_flujo_principal() -> None:
    documento = _documento()
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.avanzar_a(EstadoDocumento.CLASIFICADO)


def test_no_se_puede_retroceder() -> None:
    documento = _documento().avanzar_a(EstadoDocumento.INVENTARIADO)
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.avanzar_a(EstadoDocumento.RECIBIDO)


def test_se_puede_marcar_observado_desde_cualquier_estado_del_flujo() -> None:
    documento = _documento().avanzar_a(EstadoDocumento.INVENTARIADO)
    observado = documento.avanzar_a(EstadoDocumento.OBSERVADO)
    assert observado.estado == EstadoDocumento.OBSERVADO


def test_observado_se_puede_bloquear() -> None:
    # Auditoria 2026-08-24: BLOQUEADO faltaba en las transiciones
    # permitidas desde OBSERVADO -- application.batches.commands.
    # cerrar_lote.CerrarLote llama avanzar_a(BLOQUEADO) sobre cualquier
    # documento sin resolver, incluido uno en OBSERVADO, asi que esta
    # transicion tiene que ser real (no solo teorica) para que cerrar un
    # lote con un documento observado no aborte a mitad de camino con
    # InvalidDocumentStateTransitionError.
    documento = _documento().avanzar_a(EstadoDocumento.INVENTARIADO).avanzar_a(EstadoDocumento.OBSERVADO)
    bloqueado = documento.avanzar_a(EstadoDocumento.BLOQUEADO)
    assert bloqueado.estado == EstadoDocumento.BLOQUEADO


def test_liberado_es_casi_terminal_solo_admite_obsoleto() -> None:
    documento = _documento(estado=EstadoDocumento.LIBERADO)
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.avanzar_a(EstadoDocumento.OBSERVADO)
    obsoleto = documento.avanzar_a(EstadoDocumento.OBSOLETO)
    assert obsoleto.estado == EstadoDocumento.OBSOLETO


def test_descartado_es_terminal() -> None:
    documento = _documento(estado=EstadoDocumento.DESCARTADO)
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.avanzar_a(EstadoDocumento.RECIBIDO)


def test_clasificar_nace_sin_tipo_procesamiento() -> None:
    assert _documento().tipo_procesamiento is None


def test_clasificar_desde_inventariado_fija_tipo_y_avanza_estado() -> None:
    documento = _documento().avanzar_a(EstadoDocumento.INVENTARIADO)
    clasificado = documento.clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
    assert clasificado.estado == EstadoDocumento.CLASIFICADO
    assert clasificado.tipo_procesamiento == TipoProcesamiento.EXTRACCION_DIRECTA


def test_clasificar_desde_recibido_falla_por_salto_de_estado() -> None:
    documento = _documento()  # todavia en RECIBIDO
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.clasificar(TipoProcesamiento.OCR)


def test_completar_extraccion_nace_sin_ruta_ni_advertencias() -> None:
    documento = _documento()
    assert documento.ruta_extraccion is None
    assert documento.advertencias_extraccion == []


def test_completar_extraccion_desde_en_extraccion_fija_ruta_y_avanza_estado() -> None:
    documento = (
        _documento()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
    )
    extraido = documento.completar_extraccion("/proyecto/03_extracciones/doc.md", ["aviso 1"])
    assert extraido.estado == EstadoDocumento.EXTRAIDO
    assert extraido.ruta_extraccion == "/proyecto/03_extracciones/doc.md"
    assert extraido.advertencias_extraccion == ["aviso 1"]


def test_completar_extraccion_desde_clasificado_falla_por_salto_de_estado() -> None:
    documento = (
        _documento().avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
    )
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.completar_extraccion("/proyecto/03_extracciones/doc.md")


def test_marcar_extraccion_fallida_desde_en_extraccion_vuelve_a_clasificado() -> None:
    # Bug real encontrado 2026-07-29 (usuario sin Tesseract instalado):
    # sin este metodo, un documento EN_EXTRACCION cuya extraccion fallara
    # quedaba atascado ahi para siempre -- ni siquiera un reintento
    # posterior podia recuperarlo, porque EN_EXTRACCION -> EN_EXTRACCION
    # no es una transicion valida de avanzar_a(). Ver
    # application.documents.commands.extraer_documento.ExtraerDocumento.
    documento = (
        _documento()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
    )
    revertido = documento.marcar_extraccion_fallida()
    assert revertido.estado == EstadoDocumento.CLASIFICADO
    # Reintentar (volver a EN_EXTRACCION) debe volver a funcionar.
    reintentado = revertido.avanzar_a(EstadoDocumento.EN_EXTRACCION)
    assert reintentado.estado == EstadoDocumento.EN_EXTRACCION


def test_marcar_extraccion_fallida_fuera_de_en_extraccion_falla() -> None:
    documento = _documento().avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.marcar_extraccion_fallida()


def test_completar_extraccion_nace_sin_mapa_paginas() -> None:
    documento = _documento()
    assert documento.mapa_paginas == []


def test_completar_extraccion_guarda_mapa_paginas() -> None:
    documento = (
        _documento()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
    )
    extraido = documento.completar_extraccion("/proyecto/03_extracciones/doc.md", mapa_paginas=[0, 120, 340])
    assert extraido.mapa_paginas == [0, 120, 340]


def test_completar_extraccion_nace_sin_rangos_baja_confianza() -> None:
    documento = _documento()
    assert documento.rangos_baja_confianza == []


def test_completar_extraccion_guarda_rangos_baja_confianza() -> None:
    from domain.documents.ocr_table_reconstruction import RangoBajaConfianza

    documento = (
        _documento()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.OCR)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
    )
    rango = RangoBajaConfianza(inicio=5, fin=12, confianza=33.0, texto="incierto")
    extraido = documento.completar_extraccion("/proyecto/03_extracciones/doc.md", rangos_baja_confianza=[rango])
    assert extraido.rangos_baja_confianza == [rango]


def _documento_extraido() -> Documento:
    return (
        _documento()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
    )


def test_documento_nace_sin_ruta_revisado() -> None:
    assert _documento().ruta_revisado is None


def test_corregir_desde_extraido_fija_ruta_revisado_sin_avanzar_estado() -> None:
    documento = _documento_extraido()
    corregido = documento.corregir("/proyecto/05_revisiones/doc.md")
    assert corregido.ruta_revisado == "/proyecto/05_revisiones/doc.md"
    assert corregido.estado == EstadoDocumento.EXTRAIDO


def test_corregir_se_puede_llamar_varias_veces() -> None:
    documento = _documento_extraido()
    primera = documento.corregir("/proyecto/05_revisiones/doc_v1.md")
    segunda = primera.corregir("/proyecto/05_revisiones/doc_v2.md")
    assert segunda.ruta_revisado == "/proyecto/05_revisiones/doc_v2.md"
    assert segunda.estado == EstadoDocumento.EXTRAIDO


def test_corregir_fuera_de_extraido_falla() -> None:
    documento = _documento()  # todavia en RECIBIDO
    with pytest.raises(CorreccionRequiereEstadoExtraidoError):
        documento.corregir("/proyecto/05_revisiones/doc.md")


def test_ruta_markdown_vigente_sin_nada_es_none() -> None:
    assert _documento().ruta_markdown_vigente() is None


def test_ruta_markdown_vigente_prefiere_extraccion_sobre_nada() -> None:
    documento = _documento_extraido()
    assert documento.ruta_markdown_vigente() == "/proyecto/03_extracciones/doc.md"


def test_ruta_markdown_vigente_prefiere_correccion_sobre_extraccion() -> None:
    documento = _documento_extraido().corregir("/proyecto/05_revisiones/doc.md")
    assert documento.ruta_markdown_vigente() == "/proyecto/05_revisiones/doc.md"


def test_ruta_markdown_vigente_prefiere_normalizado_sobre_todo_lo_demas() -> None:
    documento = (
        _documento_extraido()
        .corregir("/proyecto/05_revisiones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion("/proyecto/06_normalizados/doc.md")
    )
    assert documento.ruta_markdown_vigente() == "/proyecto/06_normalizados/doc.md"


def test_completar_normalizacion_nace_sin_ruta_ni_cambios() -> None:
    documento = _documento()
    assert documento.ruta_normalizado is None
    assert documento.cambios_normalizacion == []


def _documento_revisado() -> Documento:
    # Modulo 8 (revision humana) todavia no existe: se avanza el
    # estado directamente con avanzar_a(), el primitivo de bajo nivel
    # ya disponible desde el Modulo 3 -- Modulo 9 solo necesita que el
    # documento este REVISADO, sin necesitar el caso de uso real que
    # lo produzca.
    return (
        _documento()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
    )


def test_completar_normalizacion_desde_en_normalizacion_fija_ruta_y_avanza_estado() -> None:
    documento = _documento_revisado().avanzar_a(EstadoDocumento.EN_NORMALIZACION)
    normalizado = documento.completar_normalizacion("/proyecto/06_normalizados/doc.md", ["cambio 1"])
    assert normalizado.estado == EstadoDocumento.NORMALIZADO
    assert normalizado.ruta_normalizado == "/proyecto/06_normalizados/doc.md"
    assert normalizado.cambios_normalizacion == ["cambio 1"]


def test_completar_normalizacion_desde_revisado_falla_por_salto_de_estado() -> None:
    documento = _documento_revisado()  # todavia no avanzo a EN_NORMALIZACION
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.completar_normalizacion("/proyecto/06_normalizados/doc.md")


def test_marcar_normalizacion_fallida_desde_en_normalizacion_vuelve_a_revisado() -> None:
    # Mismo bug y mismo criterio que
    # test_marcar_extraccion_fallida_desde_en_extraccion_vuelve_a_clasificado.
    documento = _documento_revisado().avanzar_a(EstadoDocumento.EN_NORMALIZACION)
    revertido = documento.marcar_normalizacion_fallida()
    assert revertido.estado == EstadoDocumento.REVISADO
    reintentado = revertido.avanzar_a(EstadoDocumento.EN_NORMALIZACION)
    assert reintentado.estado == EstadoDocumento.EN_NORMALIZACION


def test_marcar_normalizacion_fallida_fuera_de_en_normalizacion_falla() -> None:
    documento = _documento_revisado()  # todavia no avanzo a EN_NORMALIZACION
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.marcar_normalizacion_fallida()


def test_no_se_puede_normalizar_sin_pasar_por_revision() -> None:
    documento = (
        _documento()
        .avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
    )  # EXTRAIDO, sin pasar por EN_REVISION/REVISADO
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.avanzar_a(EstadoDocumento.EN_NORMALIZACION)


# -- Modulo 12 (Generador de Markdown) --------------------------------


def _documento_normalizado() -> Documento:
    return _documento_revisado().avanzar_a(EstadoDocumento.EN_NORMALIZACION).completar_normalizacion(
        "/proyecto/06_normalizados/doc.md", ["cambio 1"]
    )


def test_documento_nace_sin_datos_de_markdown_final() -> None:
    documento = _documento()
    assert documento.ruta_markdown is None
    assert documento.hash_markdown is None
    assert documento.advertencias_markdown == []


def test_aprobar_para_markdown_desde_normalizado_avanza_dos_pasos() -> None:
    documento = _documento_normalizado()
    aprobado = documento.aprobar_para_markdown()
    assert aprobado.estado == EstadoDocumento.APROBADO_PARA_MARKDOWN


def test_aprobar_para_markdown_desde_revisado_falla_por_salto_de_estado() -> None:
    documento = _documento_revisado()  # todavia no normalizado
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.aprobar_para_markdown()


def test_generar_markdown_desde_aprobado_fija_ruta_y_hash_y_avanza_estado() -> None:
    documento = _documento_normalizado().aprobar_para_markdown()
    generado = documento.generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)
    assert generado.estado == EstadoDocumento.MARKDOWN_GENERADO
    assert generado.ruta_markdown == "/proyecto/07_markdown/doc.md"
    assert generado.hash_markdown == "e" * 64


def test_generar_markdown_desde_normalizado_falla_por_salto_de_estado() -> None:
    documento = _documento_normalizado()  # todavia no aprobado
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)


def test_validar_markdown_desde_markdown_generado_fija_advertencias_y_avanza_estado() -> None:
    documento = (
        _documento_normalizado()
        .aprobar_para_markdown()
        .generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)
    )
    validado = documento.validar_markdown(["sin encabezados"])
    assert validado.estado == EstadoDocumento.VALIDADO
    assert validado.advertencias_markdown == ["sin encabezados"]


def test_validar_markdown_sin_advertencias_queda_lista_vacia() -> None:
    documento = (
        _documento_normalizado()
        .aprobar_para_markdown()
        .generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)
    )
    validado = documento.validar_markdown()
    assert validado.advertencias_markdown == []


def test_liberar_desde_validado_avanza_estado() -> None:
    documento = (
        _documento_normalizado()
        .aprobar_para_markdown()
        .generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)
        .validar_markdown()
    )
    liberado = documento.liberar()
    assert liberado.estado == EstadoDocumento.LIBERADO


def test_liberar_desde_markdown_generado_falla_por_salto_de_estado() -> None:
    documento = (
        _documento_normalizado()
        .aprobar_para_markdown()
        .generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)
    )  # todavia no validado
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.liberar()


def test_liberado_sigue_siendo_casi_terminal_solo_admite_obsoleto() -> None:
    documento = (
        _documento_normalizado()
        .aprobar_para_markdown()
        .generar_markdown("/proyecto/07_markdown/doc.md", "e" * 64)
        .validar_markdown()
        .liberar()
    )
    with pytest.raises(InvalidDocumentStateTransitionError):
        documento.avanzar_a(EstadoDocumento.OBSERVADO)
    obsoleto = documento.avanzar_a(EstadoDocumento.OBSOLETO)
    assert obsoleto.estado == EstadoDocumento.OBSOLETO


def test_aprobacion_rechaza_aprobador_vacio() -> None:
    with pytest.raises(ValueError):
        Aprobacion(documento_id="doc-1", aprobador="   ")


def test_aprobacion_guarda_comentario_y_documento_id() -> None:
    aprobacion = Aprobacion(documento_id="doc-1", aprobador="ana@nexom.mx", comentario="Todo en orden.")
    assert aprobacion.documento_id == "doc-1"
    assert aprobacion.aprobador == "ana@nexom.mx"
    assert aprobacion.comentario == "Todo en orden."


def test_documento_nace_sin_lote() -> None:
    assert _documento().lote_id is None


def test_asignar_a_lote_fija_lote_id_sin_tocar_el_estado() -> None:
    documento = _documento()
    asignado = documento.asignar_a_lote("LOTE-1")
    assert asignado.lote_id == "LOTE-1"
    assert asignado.estado == documento.estado


def test_asignar_a_lote_reemplaza_una_asignacion_anterior() -> None:
    documento = _documento().asignar_a_lote("LOTE-1")
    reasignado = documento.asignar_a_lote("LOTE-2")
    assert reasignado.lote_id == "LOTE-2"


def test_quitar_de_lote_deja_lote_id_en_none() -> None:
    documento = _documento().asignar_a_lote("LOTE-1")
    quitado = documento.quitar_de_lote()
    assert quitado.lote_id is None
    assert quitado.estado == documento.estado
