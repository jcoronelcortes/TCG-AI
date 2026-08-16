"""POKE PAD: a free search, limited to Pokemon WITHOUT a Rule Box.

The cheap counterpart to the Ultra Ball: it costs no cards, so there is almost
no "should we play it" question -- the interesting part is what it can reach
and when the item is going to be usable at all.

WHAT IT CANNOT FETCH is the defining constraint. No ex, which rules out the
Hydrapple ex line's top, Meowth ex, Fezandipiti ex and Ogerpon. What is left is
`_PP_NON_RULEBOX_IDS`: the Meganium line, the lower half of the Hydrapple line,
and Tapu Bulu. So the Pad is the card that ASSEMBLES LINES and finds the
one-prize bodies, while the Ultra Ball is the one that buys finishers.

TIMING IS MOST OF THE SCORE. Two situations dominate:

  * THE OPENING (`_pp_es_t1`) -- the turn where getting a line started is worth
    more than anything else in hand.
  * AN INCOMING ITEM LOCK (`_pp_budew_dump`) -- Budew's Itchy Pollen blocks our
    Items next turn, so THIS turn is the only one in which the Pads can be
    used at all. When that is true, they all get played now. This is the
    general principle the agent applies to Items under threat: a resource that
    expires is not a resource to keep.

It also supplies the body for the OPENING SACRIFICE -- when a two-prize ex is
stuck in front on our first turn and there is no one-prize body to hand over,
the Pad is what goes and finds one (`opening_sac_needs_body` in the decision
context).

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.engine.rules import _FixedRule
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Applin, Bayleef, Chikorita, Dipplin, Meganium
from ptcg.cards.ids import Applin, Bayleef, Chikorita, DOOMED_SAC_BENCH_ORDER, Dipplin, Hydrapple_ex, Meganium, SCORE_VETO, SETUP_ACTIVE_BASIC_ORDER, Tapu_Bulu
from ptcg.state.zones import ZONE_DECK
from ptcg.cards.groups import GRASS_DOUBLER_LINE_IDS
from ptcg.cards.ids import Forest_of_Vitality
from ptcg.cards.lines import (_evolution_stage, _line_climb_from_hand,
                              _line_in_play_from)
from ptcg.engine.context import DecisionContext
from ptcg.engine.rules import _Adjustment, _FixedRule, _resolve_with_trace


_PP_NON_RULEBOX_IDS = (Chikorita, Bayleef, Meganium, Applin, Dipplin,
                       Tapu_Bulu)


def _pp_buscables(c):
    """Pokemon WITHOUT a Rule Box that still have copies in the deck (the only
    thing Poke Pad can search for: it excludes the Hydrapple ex line and the
    other ex)."""
    cards = c.cards_in_deck
    return {cid: cards[cid][ZONE_DECK] for cid in _PP_NON_RULEBOX_IDS
            if cid in cards and cards[cid][ZONE_DECK] > 0}


def _pp_es_t1(c):
    """Is this OUR first turn? Turn 1 going first, turn 2 going second.

    `state.turn` counts both players' turns, so "our first" is a different
    number depending on who opened. Written out here because several rules
    across the package need it and getting the parity wrong silently applies
    the opening rules on the wrong turn.
    """
    return ((c.state.turn == 1 and c.we_go_first)
            or (c.state.turn == 2 and not c.we_go_first))


def _pp_budew_dump(c):
    """The opponent opens with Budew ACTIVE and we go second: its Itchy Pollen
    blocks items on our next turn; this first turn is the ONLY one for using
    items -> play ALL the Poke Pads now."""
    return (c.budew_op_index == 0
            and c.state.turn == 2 and not c.we_go_first)


def _v_pp_t1(c):
    s = _pp_buscables(c)
    tiene_applin = (c.field_counts.get(Applin, 0) >= 1
                    or c.hand_counts.get(Applin, 0) >= 1)
    tiene_chik = (c.field_counts.get(Chikorita, 0) >= 1
                  or c.hand_counts.get(Chikorita, 0) >= 1)
    if not tiene_applin and Applin in s and c.bench_count < 5:
        return 12800
    if not tiene_chik and Chikorita in s and c.bench_count < 5:
        return 12600
    if _pp_budew_dump(c):
        return 12400
    return SCORE_VETO


def _pp_forest_this_turn(hand_counts):
    """Can a body that comes down this turn still evolve this turn?

    `_forest_disponible` word for word -- on the field OR still in hand, the
    reading `_v_ub_applin_arrancar` already buys the bottom of a line with --
    but asked of a plain `{card_id: copies}` instead of a context, because the
    Pad's two halves carry the hand under different names (`hand_counts` on the
    PLAY context, `hand` on the fetch one). ONE function, both call sites: the
    alternative is the pair of readings `_ld_supp_comprometido` documents, where
    two halves of the same rule quietly disagree about the board.
    """
    return (AGENT_STATE.forest_in_play
            or (hand_counts or {}).get(Forest_of_Vitality, 0) >= 1)


def _pp_seat_the_hand_completes(c):
    """The BASIC still in the DECK that the HAND would finish the moment it is
    benched, as `(steps, basic_id)` -- `(0, None)` when there is none.

    THE SEAT A SEARCH BUYS IS EVOLVABLE TODAY, and this is the only rung of the
    Pad that says so. Every other "rush" in the package asks for the
    pre-evolution to be ON THE BOARD already (`c.field.get(Applin, 0) >= 1`),
    which is the right question for the Ultra Ball's `applin_evolvable` and the
    wrong one here: with Forest of Vitality out, a Basic bought out of the deck
    goes down and evolves in the SAME turn, so a hand holding the Stage 1 and
    the Stage 2 of a line whose Basic is still in the deck is one Pad away from
    that Stage 2 -- and the Pad, which cannot fetch a Rule Box card, is often
    the only card in hand that can buy the bottom of an ex line at all.

    `_line_climb_from_hand` does the reading and knows nothing about the turn;
    the three conditions that make it a play TODAY are asked here:

      * the stadium lifts the "came down this turn" veto
        (`_pp_forest_this_turn`: on the field, or still in hand);
      * there is a BENCH SEAT for the Basic to land on;
      * NOTHING of that line is on the board yet (`_line_in_play_from`) -- with
        a body already standing, the pieces in hand have a seat without the
        search and buying a second Basic is development, not the turn. It is
        the guard `_RULES_BCS_APPLIN.line_from_scratch_rush` writes by hand.

    Deck-agnostic: the candidates come from `_pp_buscables` (what is left in the
    deck and has no Rule Box) and the chain from the card data, so the Meganium
    line, the Hydrapple line and a line neither of them is written for all get
    the same answer. The FIRST turn is excluded by the ladder above it, which is
    also what the stadium's own text says ("except during their first turn").
    """
    if not _pp_forest_this_turn(c.hand_counts) or c.bench_count >= 5:
        return 0, None
    best = (0, None)
    for cid in _pp_buscables(c):
        if _evolution_stage(cid) != 0:
            continue
        if _line_in_play_from(cid, c.field_counts):
            continue
        steps, _ = _line_climb_from_hand(cid, c.hand_counts)
        if steps < 1:
            continue
        # Ties go to the line that ends in the Grass doubler, the same order
        # `rush_seat_the_hand_completes` states on the fetch side. The two
        # halves have to name the SAME line or the play and the pick disagree.
        rank = (steps, 1 if cid in GRASS_DOUBLER_LINE_IDS else 0)
        best_rank = (best[0], 1 if best[1] in GRASS_DOUBLER_LINE_IDS else 0)
        if rank > best_rank:
            best = (steps, cid)
    return best


def _pp_evo_value(c):
    """Best evolution enabled THIS turn by a Poke Pad search (0 = none). The
    evolvable snapshot is the start-of-turn one when there is no Forest."""
    s = _pp_buscables(c)
    h, f = c.hand_counts, c.field_counts
    # It does NOT use `_evolvable_counts`: MEASURED AND REVERTED (see its scope note).
    evolvable = (c.field_at_turn_start
                 if (not c.forest_in_play and c.field_at_turn_start) else f)
    v = 0
    if (Meganium in s and not c.meganium_in_play
            and h.get(Meganium, 0) == 0):
        if evolvable.get(Bayleef, 0) >= 1:
            v = max(v, 1200)
        elif (c.forest_in_play and evolvable.get(Chikorita, 0) >= 1
                and h.get(Bayleef, 0) >= 1):
            v = max(v, 1100)
    if (Bayleef in s and not c.meganium_in_play
            and h.get(Bayleef, 0) == 0):
        if evolvable.get(Chikorita, 0) >= 1:
            v = max(v, 1000)
            if c.forest_in_play and h.get(Meganium, 0) >= 1:
                v = max(v, 1150)
    if Dipplin in s and h.get(Dipplin, 0) == 0:
        if evolvable.get(Applin, 0) >= 1:
            v = max(v, 950)
            if c.forest_in_play and h.get(Hydrapple_ex, 0) >= 1:
                v = max(v, 1100)
    # ...and the same evolution bought from the BOTTOM: the Basic out of the
    # deck, the rest of the line already in hand. Two steps is a Stage 2 today
    # and prices with the rung above it; one step is a Stage 1, which is what
    # the `950` band is for.
    _seat_steps, _ = _pp_seat_the_hand_completes(c)
    if _seat_steps >= 2:
        v = max(v, 1100)
    elif _seat_steps == 1:
        v = max(v, 950)
    return v


def _pp_evolution_pending_search(c):
    """Some pre-evolution in play whose evolution is NOT in hand but IS in the
    deck: a search enables it (do not cut off because the bench is full)."""
    h, f, cards = c.hand_counts, c.field_counts, c.cards_in_deck
    return ((f.get(Chikorita, 0) >= 1 and h.get(Bayleef, 0) == 0
             and cards.get(Bayleef, {}).get(ZONE_DECK, 0) > 0)
            or (f.get(Bayleef, 0) >= 1 and h.get(Meganium, 0) == 0
                and cards.get(Meganium, {}).get(ZONE_DECK, 0) > 0)
            or (f.get(Applin, 0) >= 1 and h.get(Dipplin, 0) == 0
                and cards.get(Dipplin, {}).get(ZONE_DECK, 0) > 0))


_RULES_PP_PLAY = [
    _FixedRule("nothing_to_search_for",
               lambda c: not _pp_buscables(c),
               lambda c: SCORE_VETO),
    _FixedRule("first_turn",
               _pp_es_t1,
               _v_pp_t1),
    _FixedRule("evolution_this_turn",
               lambda c: _pp_evo_value(c) > 0,
               lambda c: (23000 if _pp_evo_value(c) >= 1100
                          else (22000 if _pp_evo_value(c) >= 900
                                else 20000))),
    _FixedRule("secure_chikorita",
               lambda c: (Chikorita in _pp_buscables(c)
                          and not c.meganium_in_play
                          and (c.field_counts.get(Chikorita, 0)
                               + c.field_counts.get(Bayleef, 0)
                               + c.field_counts.get(Meganium, 0)) == 0
                          and c.hand_counts.get(Chikorita, 0) == 0
                          and c.bench_count < 5),
               lambda c: 12800),
    _FixedRule("secure_applin",
               lambda c: (Applin in _pp_buscables(c) and c.bench_count < 5),
               lambda c: 12600),
]


def _pp_opening_sac_target(c):
    """The body the OPENING SACRIFICE is missing, or None.

    Our first turn has an ex in the active spot, a matchup that can knock it
    out early and NO one-prize body anywhere -- not on the bench, not in hand
    (`opening_sac_needs_body`, main.py). The Poke Pad is the one card that can
    still produce one, and it searches in the user's order: Tapu Bulu first,
    then Applin, then Chikorita. It only names a body that is actually left in
    the DECK and not already in hand or in play: fetching a fourth copy of what
    we hold changes nothing about who stands in front.
    """
    if not c.opening_sac_needs_body:
        return None
    searchable = _pp_buscables(c)
    for cid in SETUP_ACTIVE_BASIC_ORDER:
        if cid not in searchable:
            continue
        if c.field_counts.get(cid, 0) >= 1 or c.hand_counts.get(cid, 0) >= 1:
            continue
        return cid
    return None


def _pp_doomed_sac_target(c):
    """The body the DOOMED sacrifice is missing, or None.

    The twin of `_pp_opening_sac_target` on the board where the knockout is
    already visible: our active is a 2-prize ex the projection kills, nothing
    on the bench survives that hit either, and the retreat has no spare BASIC
    to put in front -- not benched, not in hand (`_doomed_sac_needs_body`,
    main.py). It searches in the SACRIFICE order (Chikorita, then Applin), the
    same one the promotion menu ranks with, and not in the opening order: this
    is picking a body to LOSE, so Tapu Bulu -- the deck's manual attacker --
    is deliberately not on the list.

    Like its twin it only names a body still left in the DECK and not already
    held: fetching a copy of what we have changes nothing about who stands in
    front.
    """
    if not c.doomed_sac_needs_body:
        return None
    searchable = _pp_buscables(c)
    for cid in DOOMED_SAC_BENCH_ORDER:
        if cid not in searchable:
            continue
        if c.field_counts.get(cid, 0) >= 1 or c.hand_counts.get(cid, 0) >= 1:
            continue
        return cid
    return None


_AJUSTES_PP_PLAY = [
    # THE POKE PAD BUYS THE BODY THE OPENING SACRIFICE NEEDS (user, ago 2026):
    # "it is allowed to use a Poke Pad this turn to look for a Basic,
    # especially if we do not have Tapu Bulu and need to find it". Without a
    # one-prize body the pivot cannot fire at all and the turn ends with a
    # 2-prize ex in front of a deck that knocks it out on its second turn --
    # which is the whole thing the opening rule exists to prevent.
    #
    # Same band (13000) as the Lucario sacrifice below, and for the same
    # reason: both are searching for the body that turns two prizes into one,
    # so neither should lose the Poke Pad to the ordinary first-turn
    # development rungs (12800 / 12600) that are only stocking the bench.
    _Adjustment("opening_sac_body",
            lambda c, s: (_pp_opening_sac_target(c) is not None
                          and c.bench_count < 5),
            lambda c, s: 13000),
    # ...AND THE SAME PURCHASE ON THE TURN THE FINISHER IS ALREADY VISIBLE
    # (user, episode 91522306 step 37 vs Archaludon ex). Same band and same
    # sentence as the rung above -- the card that turns two prizes into one --
    # asked of the board where the projection, evolution included, already
    # kills whatever we leave in front.
    _Adjustment("doomed_sac_body",
            lambda c, s: (_pp_doomed_sac_target(c) is not None
                          and c.bench_count < 5),
            lambda c, s: 13000),
    # Search for Tapu Bulu as a 1-prize sacrifice (pivot vs Lucario).
    _Adjustment("lucario_tapu_sacrifice",
            lambda c, s: (c.lucario_sac_pivot
                          and Tapu_Bulu in _pp_buscables(c)
                          and c.field_counts.get(Tapu_Bulu, 0) == 0
                          and c.hand_counts.get(Tapu_Bulu, 0) == 0
                          and c.bench_count < 5),
            lambda c, s: 13000),
    # Bench full and no pre-evolution to evolve WITH A SEARCH: keep the
    # resource (Poke Pad excludes the Dipplin->Hydrapple ex line).
    _Adjustment("full_bench_keep_it",
            lambda c, s: (c.bench_count >= 5
                          and not _pp_evolution_pending_search(c)
                          and s > 0 and not _pp_budew_dump(c)),
            lambda c, s: SCORE_VETO),
]


def _score_poke_pad_play(ctx: DecisionContext) -> int:
    """Scores playing Poke Pad (searches for a Pokemon WITHOUT a Rule Box). It
    prioritises enabling an evolution THIS turn; failing that, securing basics;
    with a full bench and nothing to evolve, it keeps the resource. Body
    migrated to the RULES ENGINE (phase 4)."""
    return _resolve_with_trace("pokepad->play", _RULES_PP_PLAY,
                               _AJUSTES_PP_PLAY, ctx, default=SCORE_VETO)


class _CtxPPFetch:
    """Ctx of the Poke Pad fetch: candidate card + values derived from the mode."""

    def __init__(self, card_id, hand_counts, field_counts, bench_count,
                 state, opening_sac_needs_body=False,
                 doomed_sac_needs_body=False):
        self.card_id = card_id
        self.hand = hand_counts
        self.field = field_counts
        self.bench_count = bench_count
        # The opening sacrifice has no one-prize body to promote (main.py):
        # this fetch is the one that produces it. Defaults to False so the
        # contexts the unit tests build by hand keep working.
        self.opening_sac_needs_body = opening_sac_needs_body
        # ...and the same for the sacrifice whose finisher is already on the
        # board and has no spare BASIC to hand over.
        self.doomed_sac_needs_body = doomed_sac_needs_body
        self.first_turn = ((state.turn == 1 and AGENT_STATE.we_go_first) or
                           (state.turn == 2 and not AGENT_STATE.we_go_first))
        self.have_chik = (field_counts.get(Chikorita, 0) >= 1 or
                          hand_counts.get(Chikorita, 0) >= 1)
        self.have_bay = (field_counts.get(Bayleef, 0) >= 1 or
                         hand_counts.get(Bayleef, 0) >= 1)
        self.have_applin = (field_counts.get(Applin, 0) >= 1 or
                            hand_counts.get(Applin, 0) >= 1)
        self.have_dipplin = (field_counts.get(Dipplin, 0) >= 1 or
                             hand_counts.get(Dipplin, 0) >= 1)
        has_evo = False
        if not AGENT_STATE.meganium_in_play and hand_counts.get(Meganium, 0) == 0:
            if field_counts.get(Bayleef, 0) >= 1:
                has_evo = True
            elif (AGENT_STATE.forest_in_play and field_counts.get(Chikorita, 0) >= 1 and
                  hand_counts.get(Bayleef, 0) >= 1):
                has_evo = True
        if (not AGENT_STATE.meganium_in_play and hand_counts.get(Bayleef, 0) == 0 and
                field_counts.get(Chikorita, 0) >= 1):
            has_evo = True
        if (hand_counts.get(Dipplin, 0) == 0 and
                field_counts.get(Applin, 0) >= 1):
            has_evo = True
        self.has_evo = has_evo


def _pp_fetch_seat_steps(c):
    """Steps the HAND would climb from THIS candidate the turn it is benched, or
    0 if it is not that purchase.

    The fetch-side mirror of `_pp_seat_the_hand_completes`, written separately
    for the reason `_pp_fetch_osac_rank` already documents: the two contexts are
    different objects -- the PLAY one carries the whole DecisionContext, this one
    only the candidate and the counts -- and threading a chosen id from one
    decision into the other is how two halves of one rule end up disagreeing
    about the board.
    """
    if (not _pp_forest_this_turn(c.hand) or c.bench_count >= 5
            or c.first_turn):
        return 0
    if _evolution_stage(c.card_id) != 0:
        return 0
    if _line_in_play_from(c.card_id, c.field):
        return 0
    steps, _ = _line_climb_from_hand(c.card_id, c.hand)
    return steps


def _pp_fetch_osac_rank(c):
    """Rung of this candidate in the opening-sacrifice order, or None.

    The mirror of `_pp_opening_sac_target` on the FETCH side: same list, same
    order, same "do not fetch what we already hold" filter. It is a separate
    function because the two contexts are different objects -- the PLAY one
    carries the whole DecisionContext, this one only the card and the counts --
    and the alternative, threading a chosen id from one decision to the other,
    is the trap `_ld_supp_comprometido` documents: two halves of one rule that
    can disagree about what the board looks like.
    """
    if not c.opening_sac_needs_body:
        return None
    if c.card_id not in SETUP_ACTIVE_BASIC_ORDER:
        return None
    if c.field.get(c.card_id, 0) >= 1 or c.hand.get(c.card_id, 0) >= 1:
        return None
    return SETUP_ACTIVE_BASIC_ORDER.index(c.card_id)


def _pp_fetch_dsac_rank(c):
    """Rung of this candidate in the DOOMED-sacrifice order, or None.

    The mirror of `_pp_doomed_sac_target` on the FETCH side, exactly as
    `_pp_fetch_osac_rank` mirrors its twin, and for the same reason: the two
    contexts are different objects and threading a chosen id between them is
    how two halves of one rule end up disagreeing about the board.
    """
    if not c.doomed_sac_needs_body:
        return None
    if c.card_id not in DOOMED_SAC_BENCH_ORDER:
        return None
    if c.field.get(c.card_id, 0) >= 1 or c.hand.get(c.card_id, 0) >= 1:
        return None
    return DOOMED_SAC_BENCH_ORDER.index(c.card_id)


_RULES_PP_FETCH = [
    # (0) THE BODY THAT STANDS IN FRONT OF THE ex (user, ago 2026). This search
    # is not stocking the bench, it is buying the difference between one prize
    # and two on the opponent's first knockout, so it outranks every
    # development rung below -- Tapu Bulu at 2200 beats the t1_applin 2000 that
    # would otherwise take the fetch. Three rungs 100 apart in the user's
    # order, so the menu order can never decide between them.
    _FixedRule("opening_sac_body",
               lambda c: _pp_fetch_osac_rank(c) is not None,
               lambda c: 2200 - 100 * _pp_fetch_osac_rank(c)),
    # (0b) ...and the body the DOOMED sacrifice is missing. Same band, same
    # spacing and the same reason to sit above every development rung; the
    # order is the sacrifice one (Chikorita, then Applin), so the two rungs
    # cannot both fire on the same board -- the two flags that arm them are
    # exclusive by construction (one asks for our first turn, the other for a
    # projection that already kills the active).
    _FixedRule("doomed_sac_body",
               lambda c: _pp_fetch_dsac_rank(c) is not None,
               lambda c: 2200 - 100 * _pp_fetch_dsac_rank(c)),
    # (1) First turn: put down the basics of both lines before anything else.
    _FixedRule("t1_applin",
               lambda c: (c.first_turn and c.card_id == Applin
                          and not c.have_applin),
               lambda c: 2000),
    _FixedRule("t1_chikorita",
               lambda c: (c.first_turn and c.card_id == Chikorita
                          and not c.have_chik),
               lambda c: 1900),
    _FixedRule("t1_otro",
               lambda c: c.first_turn,
               lambda c: 10),
    # (2) Direct evolution of a Pokemon on the current board.
    _FixedRule("evo_meganium",
               lambda c: (c.has_evo and c.card_id == Meganium
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0
                          and c.field.get(Bayleef, 0) >= 1),
               lambda c: 1000),
    _FixedRule("evo_meganium_rush",
               lambda c: (c.has_evo and c.card_id == Meganium
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0
                          and AGENT_STATE.forest_in_play
                          and c.field.get(Chikorita, 0) >= 1
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 900),
    _FixedRule("evo_bayleef_rush",
               lambda c: (c.has_evo and c.card_id == Bayleef
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Bayleef, 0) == 0
                          and c.field.get(Chikorita, 0) >= 1
                          and AGENT_STATE.forest_in_play
                          and c.hand.get(Meganium, 0) >= 1),
               lambda c: 950),
    _FixedRule("evo_bayleef",
               lambda c: (c.has_evo and c.card_id == Bayleef
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Bayleef, 0) == 0
                          and c.field.get(Chikorita, 0) >= 1),
               lambda c: 850),
    _FixedRule("evo_dipplin_rush",
               lambda c: (c.has_evo and c.card_id == Dipplin
                          and c.hand.get(Dipplin, 0) == 0
                          and c.field.get(Applin, 0) >= 1
                          and AGENT_STATE.forest_in_play
                          and c.hand.get(Hydrapple_ex, 0) >= 1),
               lambda c: 920),
    _FixedRule("evo_dipplin",
               lambda c: (c.has_evo and c.card_id == Dipplin
                          and c.hand.get(Dipplin, 0) == 0
                          and c.field.get(Applin, 0) >= 1),
               lambda c: 800),
    # (2b) THE SEAT THE HAND ALREADY FINISHES. Every rung above buys a link for
    # a body that is already on the board; this one buys the BODY, for links the
    # hand is already holding, on the turn Forest of Vitality lets it evolve the
    # moment it lands. Without it the ladder fell through to `fb_applin` (650)
    # and lost the fetch to `fb_chikorita` (800) -- a lone Basic that starts
    # nothing this turn beating the Basic that becomes a Stage 2 before the turn
    # ends. The band sits just under `evo_bayleef_rush` (950), which reaches the
    # same Stage 2 without spending a bench seat or three plays to do it, and
    # above every `fb_*` fallback, which reach nothing today.
    #
    # THE TIE-BREAK IS STATED, NOT INHERITED FROM THE MENU. Two complete lines
    # in one hand is not a rare board -- the frozen corpus has one
    # (`registro_001_alakazam_10_asiento1`, turn 8: Dipplin + Hydrapple ex AND
    # Bayleef + Meganium in hand, one bench seat, Applin and Chikorita both in
    # the deck) -- and on a bare `steps` tie the winner would be whichever the
    # simulator listed first. The line that ends in the GRASS DOUBLER goes
    # first, which is the order `chikorita_combo_completo` (990) already states
    # over `applin_combo_completo` (980) one ladder over: Wild Growth pays for
    # every other body on the board, and the other Stage 2 does not.
    # `GRASS_DOUBLER_LINE_IDS` is derived, so the deck whose doubler sits on
    # another line gets the same order without editing this file.
    _FixedRule("rush_seat_the_hand_completes",
               lambda c: _pp_fetch_seat_steps(c) >= 1,
               lambda c: (790 + 70 * _pp_fetch_seat_steps(c)
                          + (12 if c.card_id in GRASS_DOUBLER_LINE_IDS
                             else 0))),
    _FixedRule("evo_otro",
               lambda c: c.has_evo,
               lambda c: 10),
    # (3) Fallback: complete lines from hand.
    _FixedRule("fb_bayleef",
               lambda c: (c.card_id == Bayleef and not AGENT_STATE.meganium_in_play
                          and c.have_chik and not c.have_bay),
               lambda c: 850),
    _FixedRule("fb_dipplin",
               lambda c: (c.card_id == Dipplin and c.have_applin
                          and not c.have_dipplin),
               lambda c: 800),
    _FixedRule("fb_meganium",
               lambda c: (c.card_id == Meganium and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0 and c.have_bay),
               lambda c: 700),
    _FixedRule("fb_chikorita",
               lambda c: (c.card_id == Chikorita and not AGENT_STATE.meganium_in_play
                          and c.field.get(Chikorita, 0)
                          + c.field.get(Bayleef, 0)
                          + c.field.get(Meganium, 0) < 1
                          and c.hand.get(Chikorita, 0) < 1
                          and c.bench_count < 5),
               lambda c: 800),
    _FixedRule("fb_applin",
               lambda c: c.card_id == Applin and c.bench_count < 5,
               lambda c: 650),
]

__all__ = [
    '_pp_buscables',
    '_pp_es_t1',
    '_pp_budew_dump',
    '_v_pp_t1',
    '_pp_evo_value',
    '_pp_forest_this_turn',
    '_pp_seat_the_hand_completes',
    '_pp_fetch_seat_steps',
    '_pp_evolution_pending_search',
    '_pp_opening_sac_target',
    '_pp_fetch_osac_rank',
    '_score_poke_pad_play',
    '_RULES_PP_PLAY',
    '_AJUSTES_PP_PLAY',
    '_PP_NON_RULEBOX_IDS',
    '_CtxPPFetch',
    '_RULES_PP_FETCH',
]
