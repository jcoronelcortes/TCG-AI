"""Creencia sobre el mazo: escaneo inicial, movimiento de zona y premios.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from collections import defaultdict
from ptcg.cartas.ids import Ultra_Ball
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_BANCA, ESTADO_DESCARTE, ESTADO_MANO, ESTADO_MAZO, ESTADO_PREMIO


def _move_card_state(card_id, from_state, to_state):
    if card_id in ESTADO.CARTAS_ACTIVAS_EN_MAZO:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id][from_state] > 0:
            ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id][from_state] -= 1
            ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id][to_state] += 1
            return True
    return False


def _first_turn_scan(my_state):
    if ESTADO._cartas_first_scan_done:
        return

    if my_state.hand:
        for card in my_state.hand:
            _move_card_state(card.id, ESTADO_MAZO, ESTADO_MANO)

    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        _move_card_state(pokemon.id, ESTADO_MAZO, ESTADO_BANCA)
        for pre in pokemon.preEvolution:
            _move_card_state(pre.id, ESTADO_MAZO, ESTADO_BANCA)
        for ec in pokemon.energyCards:
            _move_card_state(ec.id, ESTADO_MAZO, ESTADO_BANCA)
        for tc in pokemon.tools:
            _move_card_state(tc.id, ESTADO_MAZO, ESTADO_BANCA)

    for card in my_state.discard:
        _move_card_state(card.id, ESTADO_MAZO, ESTADO_DESCARTE)
    ESTADO._cartas_first_scan_done = True


def _identify_prizes(obs, my_state=None):
    # Se recalcula en CADA revelacion COMPLETA del mazo. La vista del mazo
    # durante una busqueda (Ultra Ball, Poke Pad, etc.) muestra en select.deck
    # TODAS las cartas del mazo, por lo que es la verdad de referencia de lo que
    # hay en MAZO ahora mismo. Cualquier copia propia que no este en el mazo (ni
    # en mano/juego/descarte) esta en los premios. Al no usar un cerrojo de una
    # sola vez, el conocimiento de premios se corrige solo y se mantiene al dia.
    if obs.select is None or obs.select.deck is None:
        return
    if obs.select.effect is None:
        return
    # Ultra Ball SIEMPRE revela el mazo entero -> reconciliar directo.
    # Para otros efectos (Poke Pad, etc.) solo reconciliar si es una revelacion
    # del mazo COMPLETO: hay efectos que muestran solo una parte ("mira las 7 de
    # arriba", p.ej. Bug Catching Set) y en esos casos len(select.deck) < deckCount;
    # reconciliar con una vista parcial marcaria como PREMIADAS cartas que si estan
    # en el mazo. Por eso exigimos len(select.deck) == deckCount.
    if obs.select.effect.id != Ultra_Ball:
        deck_count = getattr(my_state, 'deckCount', None) if my_state is not None else None
        if deck_count is None or len(obs.select.deck) != deck_count:
            return

    deck_counts = defaultdict(int)
    for card in obs.select.deck:
        deck_counts[card.id] += 1

    for cid, entry in ESTADO.CARTAS_ACTIVAS_EN_MAZO.items():
        total_copies = sum(entry.values())
        in_deck = deck_counts.get(cid, 0)
        hidden = total_copies - entry[ESTADO_MANO] - entry[ESTADO_BANCA] - entry[ESTADO_DESCARTE]
        if hidden < 0:
            hidden = 0
        entry[ESTADO_MAZO] = in_deck
        premio = hidden - in_deck
        entry[ESTADO_PREMIO] = premio if premio > 0 else 0


def _sync_from_state(my_state):

    actual = defaultdict(lambda: {ESTADO_MANO: 0, ESTADO_BANCA: 0, ESTADO_DESCARTE: 0})
    if my_state.hand:
        for card in my_state.hand:
            actual[card.id][ESTADO_MANO] += 1
    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        actual[pokemon.id][ESTADO_BANCA] += 1
        for pre in pokemon.preEvolution:
            actual[pre.id][ESTADO_BANCA] += 1
        for ec in pokemon.energyCards:
            actual[ec.id][ESTADO_BANCA] += 1
        for tc in pokemon.tools:
            actual[tc.id][ESTADO_BANCA] += 1
    for card in my_state.discard:
        actual[card.id][ESTADO_DESCARTE] += 1

    for cid in ESTADO.CARTAS_ACTIVAS_EN_MAZO:
        entry = ESTADO.CARTAS_ACTIVAS_EN_MAZO[cid]
        real_mano = actual[cid][ESTADO_MANO]
        real_banca = actual[cid][ESTADO_BANCA]
        real_descarte = actual[cid][ESTADO_DESCARTE]

        total_copies = sum(entry.values())

        entry[ESTADO_MANO] = real_mano
        entry[ESTADO_BANCA] = real_banca
        entry[ESTADO_DESCARTE] = real_descarte

        remaining = total_copies - real_mano - real_banca - real_descarte
        if remaining < 0:
            remaining = 0

        known_premio = min(entry[ESTADO_PREMIO], remaining)
        entry[ESTADO_PREMIO] = known_premio
        entry[ESTADO_MAZO] = remaining - known_premio


def _move_card_state(card_id, from_state, to_state):
    if card_id in ESTADO.CARTAS_ACTIVAS_EN_MAZO:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id][from_state] > 0:
            ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id][from_state] -= 1
            ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id][to_state] += 1
            return True
    return False


def _first_turn_scan(my_state):
    if ESTADO._cartas_first_scan_done:
        return

    if my_state.hand:
        for card in my_state.hand:
            _move_card_state(card.id, ESTADO_MAZO, ESTADO_MANO)

    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        _move_card_state(pokemon.id, ESTADO_MAZO, ESTADO_BANCA)
        for pre in pokemon.preEvolution:
            _move_card_state(pre.id, ESTADO_MAZO, ESTADO_BANCA)
        for ec in pokemon.energyCards:
            _move_card_state(ec.id, ESTADO_MAZO, ESTADO_BANCA)
        for tc in pokemon.tools:
            _move_card_state(tc.id, ESTADO_MAZO, ESTADO_BANCA)

    for card in my_state.discard:
        _move_card_state(card.id, ESTADO_MAZO, ESTADO_DESCARTE)
    ESTADO._cartas_first_scan_done = True


def _identify_prizes(obs, my_state=None):
    # Se recalcula en CADA revelacion COMPLETA del mazo. La vista del mazo
    # durante una busqueda (Ultra Ball, Poke Pad, etc.) muestra en select.deck
    # TODAS las cartas del mazo, por lo que es la verdad de referencia de lo que
    # hay en MAZO ahora mismo. Cualquier copia propia que no este en el mazo (ni
    # en mano/juego/descarte) esta en los premios. Al no usar un cerrojo de una
    # sola vez, el conocimiento de premios se corrige solo y se mantiene al dia.
    if obs.select is None or obs.select.deck is None:
        return
    if obs.select.effect is None:
        return
    # Ultra Ball SIEMPRE revela el mazo entero -> reconciliar directo.
    # Para otros efectos (Poke Pad, etc.) solo reconciliar si es una revelacion
    # del mazo COMPLETO: hay efectos que muestran solo una parte ("mira las 7 de
    # arriba", p.ej. Bug Catching Set) y en esos casos len(select.deck) < deckCount;
    # reconciliar con una vista parcial marcaria como PREMIADAS cartas que si estan
    # en el mazo. Por eso exigimos len(select.deck) == deckCount.
    if obs.select.effect.id != Ultra_Ball:
        deck_count = getattr(my_state, 'deckCount', None) if my_state is not None else None
        if deck_count is None or len(obs.select.deck) != deck_count:
            return

    deck_counts = defaultdict(int)
    for card in obs.select.deck:
        deck_counts[card.id] += 1

    for cid, entry in ESTADO.CARTAS_ACTIVAS_EN_MAZO.items():
        total_copies = sum(entry.values())
        in_deck = deck_counts.get(cid, 0)
        hidden = total_copies - entry[ESTADO_MANO] - entry[ESTADO_BANCA] - entry[ESTADO_DESCARTE]
        if hidden < 0:
            hidden = 0
        entry[ESTADO_MAZO] = in_deck
        premio = hidden - in_deck
        entry[ESTADO_PREMIO] = premio if premio > 0 else 0


def _sync_from_state(my_state):

    actual = defaultdict(lambda: {ESTADO_MANO: 0, ESTADO_BANCA: 0, ESTADO_DESCARTE: 0})
    if my_state.hand:
        for card in my_state.hand:
            actual[card.id][ESTADO_MANO] += 1
    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        actual[pokemon.id][ESTADO_BANCA] += 1
        for pre in pokemon.preEvolution:
            actual[pre.id][ESTADO_BANCA] += 1
        for ec in pokemon.energyCards:
            actual[ec.id][ESTADO_BANCA] += 1
        for tc in pokemon.tools:
            actual[tc.id][ESTADO_BANCA] += 1
    for card in my_state.discard:
        actual[card.id][ESTADO_DESCARTE] += 1

    for cid in ESTADO.CARTAS_ACTIVAS_EN_MAZO:
        entry = ESTADO.CARTAS_ACTIVAS_EN_MAZO[cid]
        real_mano = actual[cid][ESTADO_MANO]
        real_banca = actual[cid][ESTADO_BANCA]
        real_descarte = actual[cid][ESTADO_DESCARTE]

        total_copies = sum(entry.values())

        entry[ESTADO_MANO] = real_mano
        entry[ESTADO_BANCA] = real_banca
        entry[ESTADO_DESCARTE] = real_descarte

        remaining = total_copies - real_mano - real_banca - real_descarte
        if remaining < 0:
            remaining = 0

        known_premio = min(entry[ESTADO_PREMIO], remaining)
        entry[ESTADO_PREMIO] = known_premio
        entry[ESTADO_MAZO] = remaining - known_premio

__all__ = [
    '_move_card_state',
    '_first_turn_scan',
    '_identify_prizes',
    '_sync_from_state',
    '_move_card_state',
    '_first_turn_scan',
    '_identify_prizes',
    '_sync_from_state',
]
