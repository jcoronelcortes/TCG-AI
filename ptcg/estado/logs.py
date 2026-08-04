"""Reading the observation logs and the KO window.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

from cg.api import AreaType, LogType
from ptcg.estado.claves import ESTADO_BANCA, ESTADO_DESCARTE, ESTADO_MANO, ESTADO_MAZO, ESTADO_PREMIO
from ptcg.estado.tracking import _move_card_state


def _area_to_estado(area):
    if area == AreaType.DECK:
        return ESTADO_MAZO
    elif area == AreaType.HAND:
        return ESTADO_MANO
    elif area in (AreaType.ACTIVE, AreaType.BENCH):
        return ESTADO_BANCA
    elif area == AreaType.DISCARD:
        return ESTADO_DESCARTE
    elif area == AreaType.PRIZE:
        return ESTADO_PREMIO
    return None


def _process_logs(obs, my_index):
    for log in obs.logs:
        if not hasattr(log, 'type'):
            continue

        if log.type == LogType.DRAW and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            _move_card_state(log.cardId, ESTADO_MAZO, ESTADO_MANO)

        elif log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            if hasattr(log, 'fromArea') and hasattr(log, 'toArea') and hasattr(log, 'cardId'):
                from_estado = _area_to_estado(log.fromArea)
                to_estado = _area_to_estado(log.toArea)
                if from_estado and to_estado and from_estado != to_estado:
                    _move_card_state(log.cardId, from_estado, to_estado)


def _area_to_estado(area):
    if area == AreaType.DECK:
        return ESTADO_MAZO
    elif area == AreaType.HAND:
        return ESTADO_MANO
    elif area in (AreaType.ACTIVE, AreaType.BENCH):
        return ESTADO_BANCA
    elif area == AreaType.DISCARD:
        return ESTADO_DESCARTE
    elif area == AreaType.PRIZE:
        return ESTADO_PREMIO
    return None


def _process_logs(obs, my_index):
    for log in obs.logs:
        if not hasattr(log, 'type'):
            continue

        if log.type == LogType.DRAW and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            _move_card_state(log.cardId, ESTADO_MAZO, ESTADO_MANO)

        elif log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            if hasattr(log, 'fromArea') and hasattr(log, 'toArea') and hasattr(log, 'cardId'):
                from_estado = _area_to_estado(log.fromArea)
                to_estado = _area_to_estado(log.toArea)
                if from_estado and to_estado and from_estado != to_estado:
                    _move_card_state(log.cardId, from_estado, to_estado)

__all__ = [
    '_area_to_estado',
    '_process_logs',
    '_area_to_estado',
    '_process_logs',
]
