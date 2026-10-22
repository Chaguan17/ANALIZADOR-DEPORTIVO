"""Utilidades de consola para Windows.

Las consolas de Windows predeterminadas usan cp1252, que no sabe imprimir
símbolos como ✓ ✗ → ·. Este helper fuerza UTF-8 en stdout/stderr para que
los CLIs del proyecto nunca crasheen por caracteres de presentación.
"""

from __future__ import annotations

import sys


def consola_utf8() -> None:
    """Configura stdout/stderr en UTF-8 con sustitución en lugar de excepción."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
