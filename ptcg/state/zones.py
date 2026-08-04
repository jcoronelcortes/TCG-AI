"""Zone keys of the card tracking (ZONE_DECK, ZONE_HAND...).

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

ZONE_DECK = "DECK"


ZONE_BENCH = "BENCH"


ZONE_HAND = "HAND"


ZONE_PRIZE = "PRIZE"


ZONE_DISCARD = "DISCARD"

__all__ = [
    'ZONE_DECK',
    'ZONE_HAND',
    'ZONE_BENCH',
    'ZONE_DISCARD',
    'ZONE_PRIZE',
]
