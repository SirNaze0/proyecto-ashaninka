"""Planificador de fondo: lanza un ciclo cuando vence el intervalo guardado en ``FeedConfig``.

Es un hilo daemon que arranca en el ``lifespan`` de la aplicación (solo con ``NA_FEED_ENABLED=true``) y
se detiene al apagarla. Cada ``tick`` segundos lee la configuración; así un cambio hecho desde la PWA
(``PUT /api/feed/config``) se aplica sin reiniciar. Con varios procesos de uvicorn habría un
planificador por proceso: el despliegue usa uno solo (ver ``docs/tvperu.md``).
"""

from __future__ import annotations

import logging
import threading

from sqlmodel import Session

from app.db.session import get_engine
from app.feed import servicio

_log = logging.getLogger("uvicorn.error")


class Planificador:
    def __init__(self, tick_s: float = 30.0) -> None:
        self.tick_s = tick_s
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> None:
        if self._hilo and self._hilo.is_alive():
            return
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name="feed-planificador", daemon=True)
        self._hilo.start()
        _log.info("feed: planificador iniciado (revisa cada %g s)", self.tick_s)

    def detener(self, timeout: float = 5.0) -> None:
        self._parar.set()
        if self._hilo:
            self._hilo.join(timeout)

    def revisar(self) -> bool:
        """Una revisión: lanza el ciclo en segundo plano si toca. Devuelve si lo lanzó."""
        with Session(get_engine()) as session:
            cfg = servicio.obtener_config(session)
            toca = servicio.toca_ejecutar(cfg)
        return toca and servicio.lanzar_en_segundo_plano()

    def _bucle(self) -> None:
        while not self._parar.wait(self.tick_s):
            try:
                self.revisar()
            except Exception:  # nunca se cae el hilo por un error puntual (p. ej. base bloqueada)
                _log.exception("feed: error al revisar el intervalo")
