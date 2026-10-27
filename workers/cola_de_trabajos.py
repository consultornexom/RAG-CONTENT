"""Despachador de trabajos en segundo plano (Fase 6, ADR-001 seccion 3:
"workers (hilos/procesos/colas en 2do plano)" y seccion 10: "la
interfaz solo captura, muestra estado, visualiza resultados y cancela.
Nunca ejecuta trabajo pesado en su propio hilo").

`ColaDeTrabajos` depende de `application.jobs.service.JobsService` (el
ciclo de vida del propio `Trabajo`) y de
`application.documents.service.DocumentsService` (el caso de uso pesado
real que cada trabajo termina invocando) -- nunca de infrastructure ni
de domain directamente (ADR-001, seccion 4: "workers: puede depender de
application, infrastructure; prohibido: ui").

Ofrece dos modos, deliberadamente distintos:

- Modo sincrono (`procesar_siguiente()`/`procesar_todos_los_pendientes()`):
  ejecuta un trabajo de punta a punta en el hilo que llama, sin ningun
  hilo de fondo real. Determinista -- es el modo que usan las pruebas
  automaticas y el que puede usar, si algun dia se necesita, un "modo
  de un solo hilo" sin `ThreadPoolExecutor`.
- Modo en segundo plano (`iniciar()`/`detener()`): usa un
  `concurrent.futures.ThreadPoolExecutor` acotado a
  `max_trabajos_concurrentes` para despachar varios trabajos PENDIENTE
  a la vez, respetando prioridad (ver
  `JobsService.siguiente_trabajo_pendiente()`).

  Riesgo real encontrado en la tercera auditoria general (2026-07-31):
  `infrastructure/database/engine.py` construye el engine de SQLite sin
  `check_same_thread=False` ni un `sessionmaker` con afinidad de hilo --
  a proposito, porque el resto de la aplicacion es deliberadamente
  sincrona, un solo hilo (ver docstring de
  `infrastructure/database/engine.py`). Si este modo alguna vez se
  activa contra el `JobsService`/`DocumentsService` REALES (los que usa
  `app.bootstrap.bootstrap()`, con una `Session` de SQLAlchemy
  compartida creada en el hilo principal), cada hilo del
  `ThreadPoolExecutor` terminaria usando esa misma `Session` desde un
  hilo distinto al que la creo -- sqlite3 lo rechaza
  (`ProgrammingError: SQLite objects created in a thread can only be
  used in that same thread`), o peor, si se relajara esa proteccion sin
  arreglar lo demas, dos hilos mutando la misma `Session` a la vez
  corromperia datos en silencio. Los tests existentes
  (`tests/unit/workers/test_cola_de_trabajos.py`) solo ejercitan este
  modo contra fakes en memoria con `threading.Lock` (thread-safe por
  construccion), por eso el problema nunca se manifesto ahi. Por eso
  `iniciar()` exige `permitir_segundo_plano=True` explicito en el
  constructor (ver mas abajo): en vez de dejar esto como una bomba de
  tiempo silenciosa para quien active el modo en el futuro contra un
  `ColaDeTrabajos` real, falla alto y claro con una explicacion, hasta
  que exista una sesion por hilo real.

Control de recursos (Documento Maestro, seccion 4.8: "limite de CPU y
memoria... aislamiento de procesos"): esta clase no impone limites de
CPU/memoria por sistema operativo (eso exigiria cgroups o un proceso
separado por trabajo, fuera de alcance para una herramienta de escritorio
de uso personal, confirmado 2026-07-28 en el Anexo B del Documento
Maestro: "no aplica -- herramienta de uso interno y personal"). El
control real y verificable que ofrece es `max_trabajos_concurrentes`:
un limite duro sobre cuantos casos de uso pesados corren al mismo
tiempo, que es la palanca que de verdad tiene disponible un proceso
Python de escritorio para no saturar la maquina del usuario."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from application.documents.service import DocumentsService
from application.jobs.service import JobsService
from domain.documents.entities import Documento
from domain.jobs.entities import Prioridad, Trabajo, TipoTrabajo

_Ejecutor = Callable[[DocumentsService, str], Documento]

_EJECUTORES: dict[TipoTrabajo, _Ejecutor] = {
    TipoTrabajo.EXTRACCION: lambda documents, documento_id: documents.extraer_documento(documento_id),
    TipoTrabajo.NORMALIZACION: lambda documents, documento_id: documents.normalizar_documento(documento_id),
    TipoTrabajo.GENERACION_MARKDOWN: lambda documents, documento_id: documents.generar_markdown(documento_id),
}
"""Que metodo real de DocumentsService invoca cada TipoTrabajo -- unico
lugar del codigo que conecta el vocabulario de domain.jobs con los casos
de uso concretos de Documentos (domain.jobs no importa domain.documents,
ver su docstring de modulo)."""


class ColaDeTrabajos:
    def __init__(
        self,
        jobs: JobsService,
        documents: DocumentsService,
        max_trabajos_concurrentes: int = 2,
        permitir_segundo_plano: bool = False,
    ):
        if max_trabajos_concurrentes < 1:
            raise ValueError("max_trabajos_concurrentes debe ser al menos 1")
        self._jobs = jobs
        self._documents = documents
        self._max_trabajos_concurrentes = max_trabajos_concurrentes
        # Agregado 2026-07-31 (tercera auditoria general, ver el
        # docstring del modulo para la explicacion completa): por
        # defecto en False -- quien construya esta clase con un
        # `jobs`/`documents` respaldados por una sesion de SQLAlchemy
        # real y de un solo hilo (el caso de `app.bootstrap.bootstrap()`
        # hoy) debe dejarlo en False. Solo pruebas contra fakes
        # thread-safe (o una futura implementacion con sesion por hilo)
        # deben pasar True de forma explicita.
        self._permitir_segundo_plano = permitir_segundo_plano
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._en_ejecucion: set[str] = set()

    def encolar(
        self,
        proyecto_id: str,
        tipo: TipoTrabajo,
        documento_id: str,
        prioridad: Prioridad = Prioridad.NORMAL,
        max_intentos: int = 3,
    ) -> Trabajo:
        trabajo = self._jobs.encolar_trabajo(proyecto_id, tipo, documento_id, prioridad, max_intentos)
        # Si ya hay un despachador en segundo plano corriendo, este
        # trabajo nuevo no tiene por que esperar a que alguien mas
        # llame a procesar_siguiente()/despache manualmente.
        self._despachar()
        return trabajo

    def _ejecutar_trabajo(self, trabajo: Trabajo) -> Trabajo:
        """Ejecuta UN trabajo de punta a punta: PREPARANDO -> EJECUTANDO
        -> COMPLETADO/FALLIDO. Compartido por el modo sincrono
        (`procesar_siguiente()`) y por cada hilo del modo en segundo
        plano (`_ejecutar_en_hilo()`) -- un solo lugar decide como se
        recorre el ciclo de vida de un trabajo real."""
        trabajo = self._jobs.iniciar_preparacion(trabajo.id)
        trabajo = self._jobs.iniciar_ejecucion(trabajo.id)
        ejecutor = _EJECUTORES.get(trabajo.tipo)
        if ejecutor is None:
            return self._jobs.fallar_trabajo(
                trabajo.id, f"Tipo de trabajo '{trabajo.tipo.value}' sin ejecutor registrado."
            )
        try:
            ejecutor(self._documents, trabajo.documento_id)
        except Exception as exc:  # noqa: BLE001 -- cualquier fallo del caso de uso subyacente
            # debe quedar registrado en el propio Trabajo (mensaje_error), nunca perderse en
            # un hilo de fondo silencioso (Documento Maestro, seccion 4.1).
            return self._jobs.fallar_trabajo(trabajo.id, str(exc))
        return self._jobs.completar_trabajo(trabajo.id)

    def procesar_siguiente(self) -> Trabajo | None:
        """Modo sincrono: toma el trabajo PENDIENTE de mayor prioridad y
        lo ejecuta de punta a punta en el hilo que llama. `None` si no
        hay ningun trabajo pendiente."""
        trabajo = self._jobs.siguiente_trabajo_pendiente()
        if trabajo is None:
            return None
        return self._ejecutar_trabajo(trabajo)

    def procesar_todos_los_pendientes(self) -> list[Trabajo]:
        """Modo sincrono: procesa, uno por uno y en orden de prioridad,
        todos los trabajos que estan PENDIENTE en este momento. No
        vuelve a mirar trabajos que se encolen mientras esta corriendo
        (a diferencia del modo en segundo plano)."""
        resultados = []
        while True:
            trabajo = self.procesar_siguiente()
            if trabajo is None:
                break
            resultados.append(trabajo)
        return resultados

    def iniciar(self) -> None:
        """Arranca el despachador en segundo plano: un
        `ThreadPoolExecutor` acotado a `max_trabajos_concurrentes` que
        va tomando trabajos PENDIENTE por orden de prioridad a medida
        que hay cupo libre. Llamarlo dos veces sin `detener()` de por
        medio no hace nada la segunda vez.

        Lanza `RuntimeError` si `permitir_segundo_plano` no se paso en
        `True` al construir esta instancia (ver docstring del modulo y
        del constructor) -- protege contra activar este modo sin querer
        contra un `JobsService`/`DocumentsService` real, cuya sesion de
        SQLAlchemy no es segura para usarse desde varios hilos."""
        if not self._permitir_segundo_plano:
            raise RuntimeError(
                "El modo en segundo plano de ColaDeTrabajos esta deshabilitado por defecto: la "
                "sesion de SQLAlchemy de este proceso se crea en un solo hilo, sin "
                "check_same_thread=False ni sesion por hilo, y no es segura para usarse desde los "
                "hilos de un ThreadPoolExecutor. Si el respaldo real es thread-safe (por ejemplo, "
                "en pruebas contra fakes en memoria), construya ColaDeTrabajos con "
                "permitir_segundo_plano=True de forma explicita."
            )
        with self._lock:
            if self._executor is not None:
                return
            self._executor = ThreadPoolExecutor(max_workers=self._max_trabajos_concurrentes)
        self._despachar()

    def _despachar(self) -> None:
        with self._lock:
            executor = self._executor
            if executor is None:
                return
            while len(self._en_ejecucion) < self._max_trabajos_concurrentes:
                trabajo = self._jobs.siguiente_trabajo_pendiente()
                if trabajo is None:
                    break
                self._en_ejecucion.add(trabajo.id)
                executor.submit(self._ejecutar_en_hilo, trabajo)

    def _ejecutar_en_hilo(self, trabajo: Trabajo) -> None:
        try:
            self._ejecutar_trabajo(trabajo)
        finally:
            with self._lock:
                self._en_ejecucion.discard(trabajo.id)
            self._despachar()

    def trabajos_en_ejecucion(self) -> int:
        """Cuantos trabajos estan corriendo de verdad en este momento en
        el modo en segundo plano -- util para pruebas y para un futuro
        panel de monitoreo (Fase 11)."""
        with self._lock:
            return len(self._en_ejecucion)

    def detener(self, esperar: bool = True) -> None:
        """Deja de despachar trabajos nuevos. Si `esperar=True`
        (predeterminado), bloquea hasta que los trabajos ya en curso
        terminen -- nunca los interrumpe a la mitad (mismo principio de
        "cancelacion segura" que `Trabajo.cancelar()`, ver
        domain.jobs.entities)."""
        with self._lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=esperar)
