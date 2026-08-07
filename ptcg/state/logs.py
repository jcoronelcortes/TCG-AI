"""Reading the observation logs and the KO window.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from cg.api import AreaType, LogType
from ptcg.state.zones import ZONE_BENCH, ZONE_DISCARD, ZONE_HAND, ZONE_DECK, ZONE_PRIZE
from ptcg.state.tracking import _move_card_state


def _area_to_zone(area):
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
