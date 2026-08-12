"""The five places one of our cards can be, as keys of the deck belief.

These are the axes of `AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id]`, and the
counts across all five always add up to the copies of that card in our 60 --
the conservation law that `ptcg/state/tracking.py` maintains and
`utils/invariant_monitor.py` checks.

They are COARSER than the engine's own `AreaType`, on purpose: ACTIVE and BENCH
collapse into ZONE_BENCH because the belief only ever asks whether a card is in
play, not where. `_area_to_zone` in `ptcg/state/logs.py` does that collapsing.

Strings rather than an enum so a belief dump reads as itself in a log or a test
failure, with no import needed to interpret it.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

# Face down and shuffled: reachable by a draw or a search.
ZONE_DECK = "DECK"


# In play, active or benched -- the belief does not distinguish. Includes the
# cards a Pokemon is BUILT from: its pre-evolutions, attached energy and tools.
ZONE_BENCH = "BENCH"


# Held. Playable now.
ZONE_HAND = "HAND"


# Face down under the prizes: ours, but unreachable until a knockout. Inferred
# by subtraction in `_identify_prizes`, never observed directly.
ZONE_PRIZE = "PRIZE"


# Spent. Reachable only by a recovery card (Night Stretcher, Lana's Aid).
ZONE_DISCARD = "DISCARD"

__all__ = [
    'ZONE_DECK',
    'ZONE_HAND',
    'ZONE_BENCH',
    'ZONE_DISCARD',
    'ZONE_PRIZE',
]
