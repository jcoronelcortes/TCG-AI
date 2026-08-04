"""Zone keys of the card tracking (ESTADO_MAZO, ESTADO_MANO...).

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
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
