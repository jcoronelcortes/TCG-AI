"""Assorted Supporters -- Dawn, Lana's Aid -- and THE DECK AS A CLOCK.

ONE SUPPORTER PER TURN. That single constraint is what makes this whole family
of decisions competitive rather than independent: Boss's Orders, Xerosic's,
Lillie's, Dawn and Lana's Aid are all bidding for the same slot, so each
scorer's real question is not "is this good" but "is this the best use of the
only Supporter we get". The values they produce share one scale
(`SCORE_SUPPORTER_VALUE_BASE`) precisely so they can be compared.

Dawn (search out an evolution line) and Lana's Aid (recover up to three
non-Rule-Box Pokemon or basic Energy) are scored here. The heavier Supporters
have their own modules -- `boss_orders.py`, `disruption.py` -- and Lillie's
Determination is still in main.py.

THE DECK CLOCK, which is this file's most reusable idea and is not about
Supporters at all. Our own deck running out loses the game, and both hands of
that clock are known: one card drawn per turn, at best one prize taken per
turn. So the prizes we still need cost that many turns, and if the deck does
not cover them the race is lost on time no matter how the board looks.
`_deck_clock_runs_out` is that comparison, and `_refill_deck_delta` is the
correction that keeps it honest -- a refill Supporter shuffles the hand back
before drawing, so with a short hand it BURNS deck rather than netting it, and
"play the refill to survive the clock" is only true when the arithmetic
actually comes out positive.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Forest_of_Vitality
from ptcg.cards.ids import Basic_Grass_Energy, Dawn, LANA_SCORE_WIN_NOW, Lanas_Aid, Lillie_Determination, SCORE_SUPPORTER_VALUE_BASE, SCORE_VETO
from ptcg.engine.context import DecisionContext
from ptcg.engine.rules import _Adjustment, _FixedRule, _resolve_with_trace
from ptcg.decision.disruption import _stamp_pendiente
from ptcg.turn.game_plan import plan_of


def _lillie_draw_count(my_prize):
    """Cards drawn by Lillie's Determination: 6, or 8 with all 6 prizes
    untouched (the card's text)."""
    return 8 if my_prize == 6 else 6


def _refill_deck_delta(deck_count, hand_len, my_prize):
    """Cards the DECK gains from playing Lillie's Determination (negative = it
    burns them).

    It shuffles the hand back in -- everything except the Supporter itself --
    and then draws. So the deck ends at `deck + (hand - 1) - draw`, and the
    delta is what the deck-out brake already reasons with, written down once.
    """
    return (hand_len - 1) - _lillie_draw_count(my_prize)


def _deck_clock_runs_out(deck_count, my_prize):
    """Does our own deck run out before we can take the prizes we still need?

    The deck is a CLOCK, and both hands of it are known: we draw one card at the
    start of every turn of ours, and at the very best we take one prize per turn.
    So `prizes left` turns are needed and only `deck` are available -- when the
    deck does not cover them the race is already lost on time, however well the
    board is going, and every card the engine burns brings the end closer.

    The comparison is `<=` and not `<` because equality only survives the
    perfect game: a prize on every single turn and not one card spent on
    searching, drawing or charging. Anything else and the last draw comes up
    empty.
    """
    return deck_count <= my_prize


def _lillie_beats_the_deck_clock(c):
    """Is this Lillie's the play that buys the turns the win still needs?

    Both halves are required and both are deck-agnostic: the clock has run out
    (`_deck_clock_runs_out`) AND shuffling the hand back really NETS deck cards
    (`_refill_deck_delta` > 0). With a short hand the refill BURNS deck, and
    firing there would bring the end closer instead of pushing it away.
    """
    _my = c.my_state
    _deck = getattr(_my, 'deckCount', 60)
    _prize = len(getattr(_my, 'prize', None) or [])
    return (_deck_clock_runs_out(_deck, _prize)
            and _refill_deck_delta(_deck, c.hand_len, _prize) > 0)


def _lana_veto_duro(c):
    """Vetoes that in the original RETURN without going through the
    adjustments (the adjustments below must not rescue them)."""
    if c.state.supporterPlayed:
        return True
    if c.op_is_comfey_deck and sum(
            1 for x in (c.my_state.discard or [])
            if getattr(x, 'id', None) == Basic_Grass_Energy) < 2:
        # vs Comfey (user, registro_005): Lana's ONLY to recover >= 2 energies
        # (our Pokemon there are ex: Lana's does not recover them).
        return True
    if _stamp_pendiente(c):
        return True
    return False


_RULES_LANA_PLAY = [
    _FixedRule("hard_veto",
               _lana_veto_duro,
               lambda c: SCORE_VETO),
    # THE RECOVERY IS THE FINISHER (user, episode 90115646 turn 10 vs
    # Archaludon ex, LOST). It goes above `no_value` because the value layer
    # cannot see this line: `_grass_plan` prices Grass by whether it puts a body
    # in ATTACK RANGE, and the active Ogerpon ex already reached
    # `ATTACK_ENERGY_REQ` -- it asked for nothing. For an attacker that SCALES
    # (Myriad Leaf Shower, Syrup Storm) the extra energy is not legality, it is
    # damage, and two more Grass were the difference between 270 and the 330
    # that knocked out their 300 HP ex for the last two prizes. See
    # `_win_via_energy_recovery`, which is the one that does the arithmetic.
    _FixedRule("winning_recovery",
               lambda c: (not _lana_veto_duro(c)
                          and plan_of(c).lethal_recovery),
               lambda c: LANA_SCORE_WIN_NOW),
    # no_value can be RESCUED by mega_line_floor (faithful to the original,
    # where that max() lives after the assignment of the value veto).
    _FixedRule("no_value",
               lambda c: c.supp_values.get(Lanas_Aid, 0) <= 0,
               lambda c: SCORE_VETO),
    _FixedRule("supporter_value",
               lambda c: True,
               lambda c: (SCORE_SUPPORTER_VALUE_BASE
                          + int(c.supp_values.get(Lanas_Aid, 0) * 1.4)
                          + c.supporter_boost)),
]


_AJUSTES_LANA_PLAY = [
    # Meganium line active with no playable energy: recovering energy from
    # the discard is worth a floor of 4500.
    _Adjustment("mega_line_floor",
            lambda c, s: (not _lana_veto_duro(c)
                          and c.mega_line_active and s < 4500
                          and not c.state.supporterPlayed
                          and c.hand_counts.get(Basic_Grass_Energy, 0) == 0
                          and not c.state.energyAttached
                          and any(x.id == Basic_Grass_Energy
                                  for x in c.my_state.discard)),
            lambda c, s: max(s, 4500)),
    # Rule (user, log 86509038 step 62 vs Mega Lucario, LOST): with no
    # attacker this turn, Lana's only beats Lillie's if it ENABLES an attack;
    # otherwise it yields (cap 2000, still playable in case Lillie's falls).
    _Adjustment("yields_to_lillie_no_attack",
            lambda c, s: (not _lana_veto_duro(c) and s > 0
                          # ... but a route that ENDS THE GAME yields to nothing:
                          # the cap is about a turn that still has a tomorrow.
                          and not plan_of(c).lethal_recovery
                          and c.active_cant_attack
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1
                          and not c.state.supporterPlayed
                          and not c.supp_values.get('_lana_enables_attack')),
            lambda c, s: min(s, 2000)),
]


def _score_lanas_aid_play(ctx: DecisionContext, score: int) -> int:
    """Scores playing Lana's Aid (recovers non-ex Pokemon + Energy from the
    discard). Body migrated to the RULES ENGINE (phase 4); the incoming `score`
    is ignored (the original overwrote it in every branch)."""
    return _resolve_with_trace("lana->play", _RULES_LANA_PLAY,
                               _AJUSTES_LANA_PLAY, ctx, default=0)


def _score_dawn_play(ctx: DecisionContext) -> int:
    """Scores playing Dawn (searches Basic + Stage 1 + Stage 2 from the deck).

    Branch extracted from the scoring loop WITHOUT any behaviour change, so that
    `_supp_play_score` (the predictor of "which Supporter gets played this
    turn") can consult the SAME source that really decides."""
    if ctx.state.supporterPlayed:
        return SCORE_VETO
    if _stamp_pendiente(ctx):
        return SCORE_VETO
    _dawn_val = ctx.supp_values.get(Dawn, 0)
    if _dawn_val <= 0:
        return SCORE_VETO
    return (SCORE_SUPPORTER_VALUE_BASE + int(_dawn_val * 1.4)
            + ctx.supporter_boost)


def _dawn_forest_avail(c):
    return AGENT_STATE.forest_in_play or c.hand.get(Forest_of_Vitality, 0) >= 1

__all__ = [
    '_lillie_draw_count',
    '_refill_deck_delta',
    '_deck_clock_runs_out',
    '_lillie_beats_the_deck_clock',
    '_lana_veto_duro',
    '_score_lanas_aid_play',
    '_score_dawn_play',
    '_RULES_LANA_PLAY',
    '_AJUSTES_LANA_PLAY',
    '_dawn_forest_avail',
]
