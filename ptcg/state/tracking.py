"""Belief about our own deck: where every one of our 60 cards currently is.

WHY A BELIEF AT ALL. The observation shows our hand, our field and our discard,
but the deck and the prizes are face down. Plenty of the agent's decisions need
to know what is still reachable -- an Ultra Ball is only worth playing if the
body it would fetch is in the DECK and not sitting under a prize, and the
Meowth -> Lillie's engine asks the same of both of its halves. This module is
what answers that, by tracking counts rather than cards.

THE MODEL. `AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][ZONE]` is a count per
zone, seeded from `deck.csv` (all 60 in ZONE_DECK) and moved around from there.
The five zones always sum to the number of copies of that card in the deck --
that conservation is the invariant everything here maintains, and the one
`utils/invariant_monitor.py` checks.

THE TWO WAYS IT LEARNS, and they are deliberately different:

  * INCREMENTALLY, from the logs -- `ptcg/state/logs.py` turns each DRAW and
    MOVE_CARD into a `_move_card_state` call. Cheap, and the only way to see a
    transition the observation does not spell out.
  * BY RECONCILIATION -- `_sync_from_state` overwrites hand/bench/discard with
    what the observation actually shows, every decision. This is the safety
    net: the log stream can be missed or arrive in odd batches, and without a
    periodic re-anchor the incremental half would drift for the rest of the
    game.

Between them, `_identify_prizes` handles the genuinely hidden part. It fires
only on a COMPLETE reveal of the deck (a search) and infers the prizes by
subtraction -- whatever we own and cannot find anywhere is face down. Because
it re-runs on every reveal it is self-correcting, so an error here costs a few
decisions rather than the game.

WHAT IT DOES NOT TRACK. The OPPONENT's deck: see `ptcg/calc/opponent.py` and
`ptcg/calc/probability.py` for what is inferred about their side. Nothing here
is pure -- it reads and writes `AGENT_STATE` -- which is why it lives in
`state/` and not in `calc/`.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from collections import defaultdict
from ptcg.cards.ids import Ultra_Ball
from ptcg.state.agent_state import AGENT_STATE
from ptcg.state.zones import ZONE_BENCH, ZONE_DISCARD, ZONE_HAND, ZONE_DECK, ZONE_PRIZE


def _move_card_state(card_id, from_state, to_state):
    """Move one copy of `card_id` between two zones. True if it happened.

    The single write point of the belief, and it REFUSES to move a copy that
    the source zone does not have (returning False). That refusal is what keeps
    the per-card counts from going negative when a log is replayed twice or
    arrives for a card we are not tracking -- the belief would rather miss a
    move than invent a copy, since `_sync_from_state` repairs the first and
    nothing repairs the second.
    """
    if card_id in AGENT_STATE.ACTIVE_CARDS_IN_DECK:
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][from_state] > 0:
            AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][from_state] -= 1
            AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][to_state] += 1
            return True
    return False


def _first_turn_scan(my_state):
    """Seed the belief from the board we open on, exactly once per game.

    The belief starts with all 60 cards in ZONE_DECK, but by the time we are
    first asked to decide, the opening hand has been drawn and the setup bodies
    are already down -- movements nobody logged to us. This walks what the
    observation shows and books those cards out of the deck.

    It goes down to the parts a Pokemon is made of -- pre-evolutions, attached
    energy, tools -- because each of those is a separate card of our 60, and
    leaving them in ZONE_DECK would have the agent planning to draw a Grass
    that is already attached to its active.

    Guarded by `_cards_first_scan_done`: running it twice would book the same
    cards out a second time.
    """
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
    """Work out which of our cards are under the prizes, from a deck reveal.

    Only meaningful when the whole deck is visible, which happens when a search
    is resolving. The inference is a subtraction: a copy we own that is not in
    hand, not in play, not in the discard and not in the revealed deck has to be
    face down. No one-shot lock, so every later reveal recomputes and corrects
    it.

    The two long comments below are the two ways this went wrong in practice --
    both about the card PAYING for the search, which is in flight and briefly in
    no zone at all. Read them before touching the arithmetic.
    """
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

    # THE CARD PAYING FOR THIS SEARCH IS IN FLIGHT, and without this line it is
    # filed as a prize. The reveal only happens because a card was PLAYED, and
    # at this instant that card is in none of the zones the subtraction below
    # can see: it has left the hand and has not reached the discard. So it
    # counts as `hidden`, it is not in the deck view, and `hidden - in_deck`
    # files it under PRIZE -- every full-deck search invents one prize, and it
    # is always the searcher itself.
    #
    # Found by utils/invariant_monitor.py, on the invariant that the tracker
    # cannot place more cards in the prizes than there are prizes face down: it
    # reported 7 in 6, on 3 281 of 13 358 judged boards. It is not bookkeeping.
    # `_gt_planes` and `_gt_wanted_basics` will not plan a line whose next card
    # reads `ZONE_DECK == 0`, and the Meowth -> Lillie's engine asks the same of
    # both its halves; a copy filed under PRIZE is a copy the deck does not have
    # as far as every one of them is concerned. Nor did it settle by itself: the
    # next reveal corrected the previous searcher and mis-filed the new one, so
    # there was always exactly one card the agent believed it could not draw.
    #
    # Pinned by tests/test_the_ultra_ball_in_flight_becomes_a_prize.py on the
    # board that found it: the deck shows three of the four Ultra Balls and the
    # fourth is the one being played.
    _in_flight = getattr(obs.select.effect, 'id', None)

    for cid, entry in AGENT_STATE.ACTIVE_CARDS_IN_DECK.items():
        total_copies = sum(entry.values())
        in_deck = deck_counts.get(cid, 0)
        hidden = total_copies - entry[ZONE_HAND] - entry[ZONE_BENCH] - entry[ZONE_DISCARD]
        if hidden < 0:
            hidden = 0
        entry[ZONE_DECK] = in_deck
        prize = hidden - in_deck
        entry[ZONE_PRIZE] = prize if prize > 0 else 0

    # ...and now the ARBITER, because the subtraction above cannot tell an
    # unaccounted copy from a prized one and the engine can. There are exactly
    # `len(my_state.prize)` cards face down; if the reconciliation has placed
    # more than that, the surplus is the searcher in flight, and the searcher
    # is the one card we can name.
    #
    # The first version of this fix decided in the loop -- "if this is the
    # effect's card and something is unaccounted, it is in flight" -- and that
    # guess was wrong 65 times in 26 280 boards, because a copy of the searcher
    # sitting in a PRIZE looks identical from inside the loop. Deciding against
    # the prize count instead can only fire when the belief is provably
    # impossible, so it cannot invent the opposite error.
    _prizes = len(getattr(my_state, 'prize', None) or []) if my_state is not None else None
    if _prizes is not None and _in_flight in AGENT_STATE.ACTIVE_CARDS_IN_DECK:
        _placed = sum(e[ZONE_PRIZE] for e in AGENT_STATE.ACTIVE_CARDS_IN_DECK.values())
        _entry = AGENT_STATE.ACTIVE_CARDS_IN_DECK[_in_flight]
        if _placed > _prizes and _entry[ZONE_PRIZE] > 0:
            # It is not in the prizes, it is on its way to the DISCARD, so it
            # is booked there: the five zones have to keep adding up to the
            # sixty cards of the deck. `_sync_from_state` overwrites DISCARD
            # from the observation on the very next decision, so this only has
            # to hold until then.
            _entry[ZONE_PRIZE] -= 1
            _entry[ZONE_DISCARD] += 1


def _sync_from_state(my_state):
    """Re-anchor the belief against what the observation actually shows.

    Runs every decision. The three VISIBLE zones -- hand, field, discard -- are
    not adjusted but OVERWRITTEN from the board, because the board is the truth
    and the incremental log path is only an approximation of it. Whatever is
    left over after that is what we cannot see, and it gets split between deck
    and prizes.

    That split keeps prize knowledge but never lets it exceed the leftover
    (`min(entry[ZONE_PRIZE], remaining)`): a card we had filed as prized and
    have since drawn must come off the prize count, or the belief would hold
    more copies than the deck has. Everything not attributed to a prize is
    assumed drawable -- the optimistic default, and the right one, since the
    cost of missing a reachable card is a play never attempted.
    """
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
