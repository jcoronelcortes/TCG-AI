"""Reading the board as a whole: the active, what can evolve, what can be played.

Three readings that several unrelated decisions share. Each one is here rather
than inlined for the same reason: when two rules compute the same fact
separately they eventually disagree, and on this board that disagreement is a
lost game rather than a failing test.

  * `_active_of` -- the active Pokemon or None. Trivial, and centralised
    because the raw pattern is three checks deep and was being written by hand
    in dozens of places.
  * `_evolvable_counts` -- which pre-evolutions can REALLY be evolved this
    turn. The subtle one; its docstring carries the game it came from and,
    more importantly, the measurement showing why the other four call sites
    were deliberately left alone.
  * `_count_hand_play_options` -- roughly how much the hand can still DO. A
    coarse "am I flooded or stuck" number, not a plan.

`_count_hand_play_options` is the one place in this package that is written
against OUR deck list by name. That is a limit worth knowing about: it counts
our four evolution links and our five Supporters, so against a different deck
it would simply undercount. The rest of the file reads properties and works
anywhere.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Dawn, Dipplin, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Teal_Mask_Ogerpon_ex, Xerosic_Machinations


def _active_of(state):
    """The active Pokemon of `state`, or None -- for either player.

    There genuinely may not be one: between a knockout and its replacement the
    active slot is empty, and that board reaches the scorers.
    """
    # Centralises the repeated pattern `state.active[0] if state.active and
    # state.active[0] is not None else None`.
    if state is None:
        return None
    _act = getattr(state, "active", None)
    return _act[0] if _act and _act[0] is not None else None


def _evolvable_counts(field_counts, at_turn_start, forest_in_play_flag):
    """Pre-evolutions that can really be EVOLVED this turn.

    With Forest of Vitality on the field the "did not come down this turn"
    restriction disappears: the CURRENT snapshot of the field rules. Without
    Forest the body has to have been in play when the turn STARTED... and to
    STILL BE THERE.

    That second requirement was missing (user, registro_006 step 84 vs Marnie):
    the start-of-turn snapshot is NOT decremented when that same pre-evolution
    is consumed by evolving during the turn. The turn started with an Applin on
    the bench, it evolved into Dipplin on step 79, and from then on the snapshot
    kept saying "there is an evolvable Applin". With that, Night Stretcher was
    played to recover a Dipplin that no longer had anything to go on top of: a
    dead card in hand, which the Unfair Stamp of that same turn shuffled back
    into the deck.

    The MINIMUM per species is taken: present NOW and present at the start. It
    is the same criterion that `_ub_evolve_now_search` and `_lillie_evolve_now`
    already spelled out BY HAND (`field_counts >= 1 and (forest or start >= 1)`):
    those two never had the bug, the frozen snapshot did.

    SCOPE (MEASURED): only the TWO faces of Night Stretcher -- `_CtxNSPlay`
    (playing it) and `evolvable_ns` (what to recover). The same idiom lives in
    four other places (Ultra Ball x2, Poke Pad, Lillie's) and cleaning those up
    TOO cost **-4.7 points vs Crustle/Kangaskhan** (68.6% vs 73.3%, n=1000);
    limited to Night Stretcher the same matchup gives **+2.4** (72.5% vs 70.1%,
    n=1000). In those four the "dirty" snapshot is acting as a proxy for
    something that does matter -- probably "this line is still alive even if it
    already evolved today", which is what sustains development in a long
    matchup. They were reverted on purpose: do not unify them without measuring
    that matchup again. (The deltas are ALWAYS from the same run: the bot's
    absolute level moves ~3 points between runs, the paired delta does not.)

    A THIRD consumer joined in August 2026, measured the same way and adopted:
    `_us_evo_jugable`, the "is there an evolution to make" rung of the Unfair
    Stamp's ladder (`ptcg/decision/disruption.py`). There the dirty snapshot is
    NOT a proxy for anything -- the rung is explicitly about what the hand can do
    TODAY -- and Crustle/Kangaskhan, the matchup that punished the other four,
    came out bit-identical: 0 flipped decisions in 200 paired games. Full
    numbers in `log/census_gate/README.md`.

    Empty snapshot = no data (first menu of the turn, before it is filled): the
    current one rules, just like the original idiom (`{}` is falsy).
    """
    if forest_in_play_flag or not at_turn_start:
        return field_counts
    return {cid: min(n, field_counts.get(cid, 0))
            for cid, n in at_turn_start.items()}


def _count_hand_play_options(hand_counts, field_counts, bench_count, energy_attached):
    """How much this hand can still DO. Returns (play_options, supporters).

    A coarse liveness number, used to tell a hand that is out of moves from one
    that is merely awkward -- which is what the refill and disruption rules turn
    on. It is not a plan and nothing executes from it.

    What counts as an option: an evolution whose body is already in play (worth
    2, since it both spends a card and upgrades a body), each Supporter held, an
    attachment if the turn's energy is unspent, and each Basic that could still
    be benched while there is room.

    `supporters` comes back separately because callers want it on its own; it is
    already included in `play_options`.

    Written against OUR deck by name -- our four evolution links, our five
    Supporters, our three benchable Basics -- so it undercounts for any other
    deck rather than failing.
    """
    play_options = 0

    if hand_counts.get(Meganium, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:
        play_options += 2
    if hand_counts.get(Bayleef, 0) >= 1 and field_counts.get(Chikorita, 0) >= 1:
        play_options += 2
    if hand_counts.get(Hydrapple_ex, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:
        play_options += 2
    if hand_counts.get(Dipplin, 0) >= 1 and field_counts.get(Applin, 0) >= 1:
        play_options += 2

    supporters_in_hand = (hand_counts.get(Lillie_Determination, 0) + hand_counts.get(Boss_Orders, 0) +
                         hand_counts.get(Dawn, 0) +
                         hand_counts.get(Lanas_Aid, 0) +
                         hand_counts.get(Xerosic_Machinations, 0))
    play_options += supporters_in_hand

    if hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not energy_attached:
        play_options += 1

    if bench_count < 5:
        for bcid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex):
            if hand_counts.get(bcid, 0) >= 1:
                play_options += 1
    return play_options, supporters_in_hand

__all__ = [
    '_active_of',
    '_evolvable_counts',
    '_count_hand_play_options',
]
