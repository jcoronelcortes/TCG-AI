"""Claves de zona del seguimiento de cartas (ESTADO_MAZO, ESTADO_MANO...).

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

ESTADO_MAZO = "MAZO"


ESTADO_BANCA = "BANCA"


ESTADO_MANO = "MANO"


ESTADO_PREMIO = "PREMIO"


ESTADO_DESCARTE = "DESCARTE"

__all__ = [
    'ESTADO_MAZO',
    'ESTADO_MANO',
    'ESTADO_BANCA',
    'ESTADO_DESCARTE',
    'ESTADO_PREMIO',
]
