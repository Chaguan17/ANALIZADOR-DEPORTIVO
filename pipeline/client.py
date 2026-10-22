"""Cliente HTTP para football-data.org con rate-limit, reintentos y caché cruda.

Por qué así (Fase 2 del plano maestro):
- `pacing` de MIN_INTERVAL segundos entre requests → respeta el free tier de 10 req/min.
- `get_cached`: si el JSON crudo ya existe en disco, NO vuelve a pedirlo a la API
  (caché-first). Cada dato se pide a la API una sola vez en la vida del proyecto.
- Reintentos con backoff exponencial solo para 429 (límite de ratio) y 5xx.
- Errores de permisos (403/404) se propagan de inmediato: no se reintenta.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from .config import (
    API_BASE_URL,
    API_TOKEN,
    MAX_RETRIES,
    MIN_INTERVAL,
    RAW_DIR,
    TIMEOUT_S,
)


class FootballDataClient:
    """Cliente de la API v4 de football-data.org con caché cruda en disco."""

    def __init__(self, raw_dir: Path = RAW_DIR) -> None:
        self._client = httpx.Client(
            base_url=API_BASE_URL,
            headers={"X-Auth-Token": API_TOKEN, "Accept": "application/json"},
            timeout=TIMEOUT_S,
        )
        self.raw_dir = raw_dir
        self._last_request: float = 0.0  # instante de la última petición (monotónico)

    # ── Rate limit ─────────────────────────────────────────────────────────
    def _pace(self) -> None:
        """Espera si la última petición fue hace menos de MIN_INTERVAL segundos."""
        delta = time.monotonic() - self._last_request
        if delta < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - delta)

    # ── Petición base ──────────────────────────────────────────────────────
    def get(self, path: str, params: dict | None = None) -> dict:
        """GET /v4/... con pacing y reintentos activados. Devuelve el JSON."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._pace()
            response = self._client.get(path.rstrip("/"), params=params)
            self._last_request = time.monotonic()

            if response.status_code == 200:
                return response.json()

            # Reintentable: excedimos la ventana de 10/min o hubo un fallo del servidor
            if response.status_code == 429 or response.status_code >= 500:
                wait = 5 * 2 ** (attempt - 1)  # 5, 10, 20 s
                last_error = RuntimeError(
                    f"HTTP {response.status_code} en {path} (intento {attempt}/{MAX_RETRIES})"
                )
                time.sleep(wait)
                continue

            # No reintenta nada: 403 (sin acceso, p/ ej. liga de pago), 404…
            response.raise_for_status()

        raise RuntimeError(f"Agotados {MAX_RETRIES} reintentos para {path}") from last_error

    # ── Caché-first a disco ────────────────────────────────────────────────
    def get_cached(
        self,
        path: str,
        save_path: Path,
        params: dict | None = None,
        refresh: bool = False,
    ) -> dict:
        """Devuelve los datos y los guarda crudos; si ya existen, usa la caché.

        save_path: ruta completa del archivo JSON, ej. pipeline/raw/PD/partidos_2026.json
        refresh: True fuerza la re-descarga aunque exista el archivo.
        """
        if save_path.exists() and not refresh:
            data = json.loads(save_path.read_text(encoding="utf-8"))
            return data

        data = self.get(path, params)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return data

    def close(self) -> None:
        """Cierra la conexión HTTP (llamar al terminar el uso del cliente)."""
        self._client.close()
