"""Belief about the deck: initial scan, zone movement and prizes.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from collections import defaultdict
from ptcg.cards.ids import Ultra_Ball
from ptcg.state.agent_state import AGENT_STATE
from ptcg.state.zones import ZONE_BENCH, ZONE_DISCARD, ZONE_HAND, ZONE_DECK, ZONE_PRIZE


def _move_card_state(card_id, from_state, to_state):
    if card_id in AGENT_STATE.ACTIVE_CARDS_IN_DECK:
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][from_state] > 0:
            AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][from_state] -= 1
            AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][to_state] += 1
            return True
    return False


def _first_turn_scan(my_state):
    if AGENT_STATE._cards_first_scan_done:
        return

    if my_state.hand:
        for card in my_state.hand:
            _move_card_state(card.id, ZONE_DECK, ZONE_HAND)

    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        _move_card_state(pokemon.id, ZONE_DECK, ZONE_BENCH)
        for pre in pokemon.preEvolution:
            _move_card_state(pre.id, ZONE_DECK, ZONE_BENCH)
        for ec in pokemon.energyCards:
            _move_card_state(ec.id, ZONE_DECK, ZONE_BENCH)
        for tc in pokemon.tools:
            _move_card_state(tc.id, ZONE_DECK, ZONE_BENCH)

    for card in my_state.discard:
        _move_card_state(card.id, ZONE_DECK, ZONE_DISCARD)
    AGENT_STATE._cards_first_scan_done = True


def _identify_prizes(obs, my_state=None):
    # Recomputed on EVERY COMPLETE reveal of the deck. The deck view during a
    # search (Ultra Ball, Poke Pad, etc.) shows ALL the cards of the deck in
    # select.deck, so it is the reference truth of what is in the DECK right now.
    # Any of our copies that is not in the deck (nor in hand/play/discard) is in
    # the prizes. Since there is no one-shot lock, prize knowledge corrects itself
    # and stays up to date.
    if obs.select is None or obs.select.deck is None:
        return
    if obs.select.effect is None:
        return
    # Ultra Ball ALWAYS reveals the whole deck -> reconcile directly.
    # For other effects (Poke Pad, etc.) only reconcile if it is a reveal of the
    # COMPLETE deck: some effects show only a part ("look at the top 7", e.g. Bug
    # Catching Set) and in those cases len(select.deck) < deckCount; reconciling
    # with a partial view would mark as PRIZED cards that really are in the deck.
    # That is why we require len(select.deck) == deckCount.
    if obs.select.effect.id != Ultra_Ball:
        deck_count = getattr(my_state, 'deckCount', None) if my_state is not None else None
        if deck_count is None or len(obs.select.deck) != deck_count:
            return

    deck_counts = defaultdict(int)
    for card in obs.select.deck:
        deck_counts[card.id] += 1

    for cid, entry in AGENT_STATE.ACTIVE_CARDS_IN_DECK.items():
        total_copies = sum(entry.values())
        in_deck = deck_counts.get(cid, 0)
        hidden = total_copies - entry[ZONE_HAND] - entry[ZONE_BENCH] - entry[ZONE_DISCARD]
        if hidden < 0:
            hidden = 0
        entry[ZONE_DECK] = in_deck
        prize = hidden - in_deck
        entry[ZONE_PRIZE] = prize if prize > 0 else 0


def _sync_from_state(my_state):

    actual = defaultdict(lambda: {ZONE_HAND: 0, ZONE_BENCH: 0, ZONE_DISCARD: 0})
    if my_state.hand:
        for card in my_state.hand:
            actual[card.id][ZONE_HAND] += 1
    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        actual[pokemon.id][ZONE_BENCH] += 1
        for pre in pokemon.preEvolution:
            actual[pre.id][ZONE_BENCH] += 1
        for ec in pokemon.energyCards:
            actual[ec.id][ZONE_BENCH] += 1
        for tc in pokemon.tools:
            actual[tc.id][ZONE_BENCH] += 1
    for card in my_state.discard:
        actual[card.id][ZONE_DISCARD] += 1

    for cid in AGENT_STATE.ACTIVE_CARDS_IN_DECK:
        entry = AGENT_STATE.ACTIVE_CARDS_IN_DECK[cid]
        real_hand = actual[cid][ZONE_HAND]
        real_bench = actual[cid][ZONE_BENCH]
        real_discard = actual[cid][ZONE_DISCARD]

        total_copies = sum(entry.values())

        entry[ZONE_HAND] = real_hand
        entry[ZONE_BENCH] = real_bench
        entry[ZONE_DISCARD] = real_discard

        remaining = total_copies - real_hand - real_bench - real_discard
        if remaining < 0:
            remaining = 0

        known_prize = min(entry[ZONE_PRIZE], remaining)
        entry[ZONE_PRIZE] = known_prize
        entry[ZONE_DECK] = remaining - known_prize

__all__ = [
    '_move_card_state',
    '_first_turn_scan',
    '_identify_prizes',
    '_sync_from_state',
]
