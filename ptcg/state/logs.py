"""Turning the observation's LOG STREAM into moves of the deck belief.

The observation carries a log of what has happened since we were last asked to
decide. This module reads the entries that tell us one of OUR cards changed
zone and forwards them to `ptcg/state/tracking.py`, which owns the counts.

WHAT IT LISTENS FOR, and what it deliberately ignores:
  * DRAW -- deck to hand. The one transition the board cannot show us after
    the fact, since a drawn card is indistinguishable from one already held.
  * MOVE_CARD -- any zone to any other, and the reason `_area_to_zone` exists:
    the engine's areas are finer than the belief's zones, and ACTIVE and BENCH
    both collapse to ZONE_BENCH because "in play" is the only distinction the
    belief needs.
  * Everything else, and every entry belonging to the OPPONENT. This module
    only maintains OUR side.

DEFENSIVE ON PURPOSE. Every field is reached through `hasattr` first, and
`_area_to_zone` returns None for an area it does not recognise, which the
caller drops. Log entries vary in shape by type, and a live game is the wrong
place to raise on an unexpected one -- the belief is self-correcting
(`_sync_from_state` re-anchors it every decision), so a skipped entry is a
smaller cost than a crash.

This is the incremental half of the belief. The reconciling half, and the
overall design, are documented in `ptcg/state/tracking.py`.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from cg.api import AreaType, LogType
from ptcg.state.zones import ZONE_BENCH, ZONE_DISCARD, ZONE_HAND, ZONE_DECK, ZONE_PRIZE
from ptcg.state.tracking import _move_card_state


def _area_to_zone(area):
    """Engine `AreaType` -> belief zone, or None if the belief does not care.

    ACTIVE and BENCH both map to ZONE_BENCH: the belief only asks whether a
    card is in play, never where. None means "not a zone we track", and the
    caller skips that log entry.
    """
    if area == AreaType.DECK:
        return ZONE_DECK
    elif area == AreaType.HAND:
        return ZONE_HAND
    elif area in (AreaType.ACTIVE, AreaType.BENCH):
        return ZONE_BENCH
    elif area == AreaType.DISCARD:
        return ZONE_DISCARD
    elif area == AreaType.PRIZE:
        return ZONE_PRIZE
    return None


def _process_logs(obs, my_index):
    """Apply every one of OUR card movements in this batch to the belief.

    `my_index` is the filter that keeps the opponent's logs out. A move whose
    endpoints land in the same zone is dropped rather than applied, since it
    would decrement and increment the same counter -- and would spend a copy
    the source zone might not have.
    """
    for log in obs.logs:
        if not hasattr(log, 'type'):
            continue

        if log.type == LogType.DRAW and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            _move_card_state(log.cardId, ZONE_DECK, ZONE_HAND)

        elif log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            if hasattr(log, 'fromArea') and hasattr(log, 'toArea') and hasattr(log, 'cardId'):
                from_zone = _area_to_zone(log.fromArea)
                to_zone = _area_to_zone(log.toArea)
                if from_zone and to_zone and from_zone != to_zone:
                    _move_card_state(log.cardId, from_zone, to_zone)

__all__ = [
    '_area_to_zone',
    '_process_logs',
]
