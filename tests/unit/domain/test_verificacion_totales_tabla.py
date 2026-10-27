from __future__ import annotations

from domain.documents.verificacion_fechas_cifras import TipoHallazgoVerificacion
from domain.documents.verificacion_totales_tabla import verificar_totales_de_tablas


def test_texto_sin_tablas_no_produce_hallazgos() -> None:
    assert verificar_totales_de_tablas("Este documento no tiene ninguna tabla.") == []


def test_tabla_sin_fila_de_total_no_produce_hallazgos() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_tabla_con_total_correcto_no_produce_hallazgos() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
            "| Total | 30 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_tabla_con_total_incorrecto_produce_hallazgo() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
            "| Total | 40 |",
        ]
    )
    hallazgos = verificar_totales_de_tablas(markdown)
    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == TipoHallazgoVerificacion.CIFRA
    assert hallazgos[0].texto == "40"
    assert hallazgos[0].advertencia is not None
    assert "30" in hallazgos[0].advertencia
    assert "40" in hallazgos[0].advertencia


def test_posicion_del_hallazgo_apunta_al_inicio_de_la_fila_de_total() -> None:
    markdown = "\n".join(
        [
            "Encabezado del documento, sin relacion con la tabla.",
            "",
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
            "| Total | 40 |",
        ]
    )
    hallazgo = verificar_totales_de_tablas(markdown)[0]
    fila_total = "| Total | 40 |"
    assert markdown[hallazgo.posicion : hallazgo.posicion + len(fila_total)] == fila_total


def test_columnas_numericas_se_validan_de_forma_independiente() -> None:
    # La columna "Cantidad" suma bien (30); la columna "Monto" NO (la
    # fila de total dice 200.00 pero A+B suman 150.00) -- solo debe
    # reportarse un hallazgo, el de "Monto".
    markdown = "\n".join(
        [
            "| Producto | Cantidad | Monto |",
            "| --- | --- | --- |",
            "| A | 10 | 50.00 |",
            "| B | 20 | 100.00 |",
            "| Total | 30 | 200.00 |",
        ]
    )
    hallazgos = verificar_totales_de_tablas(markdown)
    assert len(hallazgos) == 1
    assert hallazgos[0].texto == "200.00"
    assert "150" in hallazgos[0].advertencia


def test_celda_no_numerica_en_una_fila_se_ignora_en_la_suma() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | n/d |",
            "| Total | 10 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_fila_de_total_identificada_por_palabra_clave_suma() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
            "| Suma | 30 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_fila_de_total_identificada_por_palabra_clave_gran_total() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
            "| Gran total | 999 |",
        ]
    )
    hallazgos = verificar_totales_de_tablas(markdown)
    assert len(hallazgos) == 1  # 999 != 30, la palabra clave si se reconocio.


def test_numero_negativo_entre_parentesis_se_suma_correctamente() -> None:
    markdown = "\n".join(
        [
            "| Concepto | Monto |",
            "| --- | --- |",
            "| Cargo | 20 |",
            "| Abono | (10) |",
            "| Total | 10 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_separador_de_miles_ambiguo_se_interpreta_consistente() -> None:
    # '1.234' (un solo punto, 3 digitos despues) se interpreta como
    # separador de miles en las tres celdas -- 1234 + 1234 = 2468.
    markdown = "\n".join(
        [
            "| Concepto | Monto |",
            "| --- | --- |",
            "| A | 1.234 |",
            "| B | 1.234 |",
            "| Total | 2.468 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_separador_decimal_ambiguo_se_interpreta_consistente() -> None:
    # '1.5' (un solo punto, 1 digito despues) se interpreta como
    # separador decimal -- 1.5 + 1.5 = 3.0.
    markdown = "\n".join(
        [
            "| Concepto | Monto |",
            "| --- | --- |",
            "| A | 1.5 |",
            "| B | 1.5 |",
            "| Total | 3.0 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_formato_con_ambos_separadores_decimal_a_la_derecha() -> None:
    # '1,234.56' (convencion inglesa: coma de miles, punto decimal).
    markdown = "\n".join(
        [
            "| Concepto | Monto |",
            "| --- | --- |",
            "| A | 1,234.56 |",
            "| B | 1,000.44 |",
            "| Total | 2,235.00 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_multiples_tablas_se_validan_por_separado() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| A | 10 |",
            "| Total | 10 |",
            "",
            "| Producto | Cantidad |",
            "| --- | --- |",
            "| C | 5 |",
            "| Total | 999 |",
        ]
    )
    hallazgos = verificar_totales_de_tablas(markdown)
    assert len(hallazgos) == 1
    assert hallazgos[0].texto == "999"


def test_subtotal_no_se_confunde_con_la_fila_de_total() -> None:
    # Auditoria 2026-08-24: "Subtotal" contiene "total" como subcadena.
    # Antes del fix, `_fila_es_total` usaba `palabra in texto` y
    # `_verificar_tabla` tomaba la PRIMERA fila que matcheaba
    # (`next(...)`) -- con una fila "Subtotal" antes de la fila "Total"
    # real, el codigo viejo trataba "Subtotal" como si fuera LA fila de
    # total (y de paso, sumaba la fila "Total" real como si fuera un
    # dato mas), produciendo un falso positivo: 10+20+999+5=1034 sumado
    # y comparado contra el valor de "Subtotal" (999), un numero elegido
    # a proposito para que NO coincida con A+B (30) -- si el codigo
    # viejo tratara "Subtotal" como total, esto fallaria. Con el
    # patron de palabra completa, "Subtotal" ya no activa ninguna
    # palabra clave y se usa la fila "Total" real (la unica con la
    # palabra completa "total"), que si suma correctamente contra TODAS
    # las demas filas (incluida la que dice "Subtotal", con su valor
    # arbitrario de 999 -- este modulo no distingue subtotales
    # jerarquicos de cualquier otra fila de datos, ver limitaciones
    # documentadas en el docstring del modulo).
    markdown = "\n".join(
        [
            "| Producto | Monto |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
            "| Subtotal | 999 |",
            "| C | 5 |",
            "| Total | 1034 |",
        ]
    )
    assert verificar_totales_de_tablas(markdown) == []


def test_subtotal_no_evita_detectar_un_total_real_incorrecto() -> None:
    # Mismo escenario que arriba, pero con la fila de Total real
    # equivocada -- debe reportarse un unico hallazgo sobre ESA fila,
    # nunca sobre "Subtotal" (que ya no se reconoce como fila de total).
    markdown = "\n".join(
        [
            "| Producto | Monto |",
            "| --- | --- |",
            "| A | 10 |",
            "| B | 20 |",
            "| Subtotal | 999 |",
            "| C | 5 |",
            "| Total | 1 |",
        ]
    )
    hallazgos = verificar_totales_de_tablas(markdown)
    assert len(hallazgos) == 1
    assert hallazgos[0].texto == "1"
    fila_total = "| Total | 1 |"
    assert markdown[hallazgos[0].posicion : hallazgos[0].posicion + len(fila_total)] == fila_total


def test_celda_con_barra_vertical_escapada_no_rompe_el_conteo_de_columnas() -> None:
    markdown = "\n".join(
        [
            "| Producto | Cantidad |",
            "| --- | --- |",
            r"| A \| B | 10 |",
            "| Total | 5 |",
        ]
    )
    hallazgos = verificar_totales_de_tablas(markdown)
    assert len(hallazgos) == 1
    assert "10" in hallazgos[0].advertencia
