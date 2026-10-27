"""Pruebas de integracion real (bootstrap()/abrir_proyecto() reales,
SQLite y sistema de archivos reales, sin fakes) que NO dependen de
PySide6/qtbot -- a diferencia de tests/smoke/, que son GUI real
(requieren Qt y, en este sandbox, las bibliotecas de sistema
libEGL.so.1/libOpenGL.so.0/libGLX.so.0, ver README).

Hallazgo real de la cuarta auditoria general (2026-08-01): estos 12
archivos vivian mezclados dentro de tests/smoke/ bajo la misma
convencion de nombre `test_*_extremo_a_extremo.py` que las 6 pruebas de
GUI real -- cualquiera que asumiera "smoke = necesita entorno grafico"
dejaba de correrlos rutinariamente en ciclos rapidos de desarrollo, a
pesar de que corren sin ningun problema en cualquier entorno (incluido
este sandbox sin bibliotecas graficas, confirmado empiricamente antes de
moverlos). Se separan aqui para que `pytest tests/integration/` (o
`tests/unit/` + `tests/integration/`, sin `tests/smoke/`) sea un ciclo de
desarrollo rapido y completo, sin gate de PySide6/EGL -- solo
`tests/smoke/` exige ese entorno."""
