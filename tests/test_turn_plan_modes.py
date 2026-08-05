"""The TURN PLAN: the four sentences a turn can be under.

Companion of tests/test_match_point_gusts_before_developing.py, which covers the
record that made `ptcg/turn/game_plan.py` necessary. This file covers the plan
ITSELF over synthetic boards -- the states that never came up in a recorded game
-- and above all the DEFENSIVE half, which the record does not exercise: the
record's turn ends the game, so nothing there ever asks what the opponent takes
on the reply.

The four modes, and what each one is FOR:

    WIN_NOW   a route closes the game -> execute it, everything else is noise
    DENY      no route and THEY close it on the reply -> reduce what they take
    RACE      no route, but we take prizes and survive -> attack
    DEVELOP   nothing decisive today -> build the board

The order between them is not cosmetic. A turn that ends the game does not care
what the reply would have been, and a turn where the reply ends the game does not
care about development.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from ptcg.calc.opponent import build_op_scale
from ptcg.turn import game_plan as gp


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


class _Board:
    """The smallest thing `build_turn_plan` reads: two sides and a turn state.

    The plan takes its inputs by keyword and touches nothing else, so a handful
    of stubs is enough -- and it keeps each case readable as the SENTENCE it is
    testing instead of as sixty cards of accounting.
    """

    class _State:
        def __init__(self, energy_attached=False, supporter_played=False):
            self.energyAttached = energy_attached
            self.supporterPlayed = supporter_played

    class _Side:
        def __init__(self, active=None, bench=(), hand_count=0):
            self.active = [active] if active is not None else []
            self.bench = list(bench)
            self.handCount = hand_count


def _pk(card_id, energies=0, hp=None):
    data = m.card_table[card_id]
    return m.Pokemon(
        id=card_id, serial=1000 + card_id,
        hp=(data.hp if hp is None else hp), maxHp=(hp or data.hp),
        appearThisTurn=False, energies=[1] * energies, energyCards=[],
        tools=[], preEvolution=[])


def _plan(*, mine, theirs, hand=None, my_prize=6, op_prize=6,
          energy_attached=False, supporter_played=False,
          wins_active=False, wins_gust=False, wins_promote=False):
    hand = hand or {}
    state = _Board._State(energy_attached, supporter_played)
    # The scaled projection of their reply reads the per-turn snapshot; in a real
    # game `agent()` builds it. Building it here too is what makes the defensive
    # half of these cases faithful instead of always reading a printed 30.
    m.AGENT_STATE.op_scale = build_op_scale(mine, theirs)
    return gp.build_turn_plan(
        my_prize=my_prize, op_prize=op_prize,
        my_state=mine, op_state=theirs, state=state,
        hand_counts=hand,
        total_grass=sum(len(p.energies) for p in
                        (mine.active + mine.bench) if p is not None),
        bench_count=len(mine.bench),
        meganium_in_play=False, neutralization_zone=False,
        op_hand_count=theirs.handCount,
        active_attack_wins_now=wins_active,
        win_via_boss_gust=wins_gust,
        win_ko_active_via_promote=wins_promote)


OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
TAPU = m.Tapu_Bulu
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
GRIMMSNARL = 648        # Marnie's Grimmsnarl ex: 320 HP, a real finisher
FROSLASS = 104          # 1 prize, no attack worth the name


# ---------------------------------------------------------------------------
# WIN_NOW: the route, and which route
# ---------------------------------------------------------------------------

def test_the_cheapest_route_is_the_one_committed_to():
    """Three routes win; the plan picks the one that commits least.

    Attacking with the active as it stands spends nothing, the promotion pays a
    retreat and the gust burns the Supporter. With all three available, keeping
    the Supporter free is strictly better.
    """
    mine = _Board._Side(_pk(OGERPON, 4), [_pk(TAPU, 4)])
    theirs = _Board._Side(_pk(FROSLASS, 0, hp=90), [_pk(TAPU, 2)])
    plan = _plan(mine=mine, theirs=theirs, hand={m.Boss_Orders: 1}, my_prize=1,
                 wins_active=True, wins_gust=True, wins_promote=True)
    assert plan.win_route == gp.ROUTE_ACTIVE
    assert not plan.win_needs_supporter

    plan = _plan(mine=mine, theirs=theirs, hand={m.Boss_Orders: 1}, my_prize=1,
                 wins_gust=True, wins_promote=True)
    assert plan.win_route == gp.ROUTE_PROMOTE

    plan = _plan(mine=mine, theirs=theirs, hand={m.Boss_Orders: 1}, my_prize=1,
                 wins_gust=True)
    assert plan.win_route == gp.ROUTE_GUST
    assert plan.win_needs_supporter and plan.mode == gp.MODE_WIN_NOW


def test_a_gust_without_the_boss_in_hand_is_not_a_route():
    """`_win_via_boss_gust` also fires with the Boss's in the DECK (the Meowth ->
    Last-Ditch engine has a path to it). A ROUTE has to be executable TODAY."""
    mine = _Board._Side(_pk(OGERPON, 4), [])
    theirs = _Board._Side(_pk(HYDRAPPLE, 2), [_pk(TAPU, 2)])

    assert _plan(mine=mine, theirs=theirs, hand={}, my_prize=1,
                 wins_gust=True).win_route == ''
    assert _plan(mine=mine, theirs=theirs, hand={m.Boss_Orders: 1}, my_prize=1,
                 supporter_played=True, wins_gust=True).win_route == ''
    assert _plan(mine=mine, theirs=theirs, hand={m.Boss_Orders: 1}, my_prize=1,
                 wins_gust=True).win_route == gp.ROUTE_GUST


def test_the_gust_that_needs_a_charge_is_marked_as_such():
    """The two shapes of a winning gust, and why the turn's ORDER depends on it.

    Myriad Leaf Shower counts the energy on BOTH actives. Against a Tapu Bulu with
    2 energies our Ogerpon with 4 already kills (30+30x6 = 210 >= 140) and the
    gust IS the finisher. Against a bare Meganium (160 HP, no energy) it does
    30+30x4 = 150 and needs the turn's Grass first: there the gust has to WAIT for
    the charge, which is what `gust_closes_it_now` protects.
    """
    mine = _Board._Side(_pk(OGERPON, 4), [])
    ready = _Board._Side(_pk(HYDRAPPLE, 2), [_pk(TAPU, 2)])
    not_ready = _Board._Side(_pk(HYDRAPPLE, 2), [_pk(MEGANIUM, 0)])

    plan = _plan(mine=mine, theirs=ready, hand={m.Boss_Orders: 1}, my_prize=1,
                 wins_gust=True)
    assert not plan.win_needs_charge and plan.gust_closes_it_now

    plan = _plan(mine=mine, theirs=not_ready,
                 hand={m.Boss_Orders: 1, m.Basic_Grass_Energy: 1}, my_prize=1,
                 wins_gust=True)
    assert plan.win_needs_charge and not plan.gust_closes_it_now


# ---------------------------------------------------------------------------
# DENY / RACE / DEVELOP: the turn that does not end the game
# ---------------------------------------------------------------------------

def test_a_lethal_reply_puts_the_turn_in_deny():
    """Shadow Bullet (180) finishes our already-wounded Ogerpon ex (170 left) and
    those 2 prizes close their count."""
    mine = _Board._Side(_pk(OGERPON, 0, hp=170), [_pk(CHIKORITA, 0)])
    theirs = _Board._Side(_pk(GRIMMSNARL, 3, hp=320), [], hand_count=5)

    plan = _plan(mine=mine, theirs=theirs, my_prize=4, op_prize=2)
    assert plan.op_prizes_next == 2, "nuestro Ogerpon ex vale 2 premios"
    assert plan.op_wins_next and plan.mode == gp.MODE_DENY


def test_the_reply_that_does_not_close_their_count_is_not_deny():
    """The same board with them at 3 prizes: the KO hurts, it does not end the
    game, and the turn goes back to being about what we build."""
    mine = _Board._Side(_pk(OGERPON, 0, hp=170), [_pk(CHIKORITA, 0)])
    theirs = _Board._Side(_pk(GRIMMSNARL, 3, hp=320), [], hand_count=5)

    plan = _plan(mine=mine, theirs=theirs, my_prize=4, op_prize=3)
    assert plan.op_prizes_next == 2 and not plan.op_wins_next
    assert plan.mode == gp.MODE_DEVELOP


def test_taking_a_prize_without_closing_is_a_race():
    mine = _Board._Side(_pk(OGERPON, 4), [])
    theirs = _Board._Side(_pk(FROSLASS, 0, hp=90), [], hand_count=3)

    plan = _plan(mine=mine, theirs=theirs, my_prize=4, op_prize=4)
    assert plan.prizes_today == 1 and plan.mode == gp.MODE_RACE


def test_a_sterile_turn_is_develop():
    mine = _Board._Side(_pk(OGERPON, 0), [])
    theirs = _Board._Side(_pk(HYDRAPPLE, 1), [], hand_count=3)

    plan = _plan(mine=mine, theirs=theirs, my_prize=4, op_prize=4)
    assert plan.prizes_today == 0 and not plan.op_wins_next
    assert plan.mode == gp.MODE_DEVELOP


def test_the_reply_of_a_body_we_are_about_to_knock_out_does_not_count():
    """The defect the census found (ago 2026), and the reason it mattered.

    `op_prizes_next` was projected from the Pokemon standing in front of us --
    including on the turns where our own attack sends it to the discard. Over 200
    self-play games that called "we lose on the reply" on turns where we were
    removing the very attacker making it: DENY was 7.9% of decisions and dropped
    to 4.5% once the KO was taken into account, and 379 energy decisions were
    flagged "no tomorrow" on turns that were precisely the case
    `_tapu_future_charge` exists for -- charging the bench body for a turn that
    does exist.

    Board: their Marnie's Grimmsnarl ex (320 HP, 3 energies) one-shots our
    wounded Ogerpon ex with Shadow Bullet (180 >= 170) and they are at 2 prizes.
    But Myriad counts both actives -- 30 + 30 x (4+3) = 240, doubled by the Grass
    weakness = 480 -- so the Grimmsnarl does not survive our turn.
    """
    mine = _Board._Side(_pk(OGERPON, 4, hp=170), [_pk(CHIKORITA, 0)])
    theirs = _Board._Side(_pk(GRIMMSNARL, 3, hp=320), [], hand_count=5)

    plan = _plan(mine=mine, theirs=theirs, my_prize=4, op_prize=2)
    assert plan.prizes_today == 2, "el Grimmsnarl ex cae este turno"
    assert plan.op_prizes_next == 0 and not plan.op_wins_next, (
        "no hay respuesta de un cuerpo que se va al descarte en nuestro turno")

    # CONTROL: the same board with our Ogerpon uncharged. Now Myriad does
    # 30 + 30 x 3 = 120, doubled 240 < 320: the Grimmsnarl survives, attacks, and
    # the reply DOES close their count.
    unarmed = _Board._Side(_pk(OGERPON, 0, hp=170), [_pk(CHIKORITA, 0)])
    plan = _plan(mine=unarmed, theirs=theirs, my_prize=4, op_prize=2)
    assert plan.prizes_today == 0
    assert plan.op_prizes_next == 2 and plan.op_wins_next
    assert plan.mode == gp.MODE_DENY


def test_a_gusted_bench_ko_does_not_disarm_their_reply():
    """Knocking out a body we GUST leaves their active where it is -- and its
    attack with it. Only a KO on the ACTIVE voids the projection."""
    # Their active is a Hydrapple ex we canNOT reach (Myriad 30+30x(3+2) = 180 <
    # 330) but whose Syrup Storm, with 4 {G} on their board, does 150 -- enough
    # for our wounded Ogerpon ex and enough to close their count at 2 prizes.
    # Their benched Tapu Bulu (140) DOES die to that same Myriad after a gust.
    mine = _Board._Side(_pk(OGERPON, 3, hp=140), [_pk(CHIKORITA, 0)])
    theirs = _Board._Side(_pk(HYDRAPPLE, 2), [_pk(TAPU, 2)], hand_count=5)

    plan = _plan(mine=mine, theirs=theirs, hand={m.Boss_Orders: 1},
                 my_prize=4, op_prize=2)
    assert plan.prizes_today >= 1, "su Tapu Bulu de banca si muere tras el gusteo"
    assert plan.op_wins_next, (
        "el Hydrapple sigue en el activo: su respuesta no se desarma gusteando")


# ---------------------------------------------------------------------------
# The arithmetic of the denial: when conceding a smaller corpse changes anything
# ---------------------------------------------------------------------------

def test_denial_only_pays_when_the_cheaper_body_does_not_close_it_either():
    mine = _Board._Side(_pk(OGERPON, 0, hp=170), [_pk(CHIKORITA, 0)])
    theirs = _Board._Side(_pk(GRIMMSNARL, 3, hp=320), [], hand_count=5)

    # They need 2: our ex closes it, a 1-prize body does not -> the swap saves it.
    assert _plan(mine=mine, theirs=theirs, my_prize=2,
                 op_prize=2).denial_saves_the_game(1)

    # They need 1: EVERY corpse ends the game and the pivot buys nothing. This is
    # the case the `my_prize >= 3` gate in the retreat scorer was written for.
    assert not _plan(mine=mine, theirs=theirs, my_prize=2,
                     op_prize=1).denial_saves_the_game(1)


def test_denial_stands_down_when_the_turn_still_has_a_win_or_a_prize():
    """A route or a prize on the board outranks the denial: the turn has
    something better to do than concede tempo."""
    mine = _Board._Side(_pk(OGERPON, 4), [_pk(CHIKORITA, 0)])
    theirs = _Board._Side(_pk(GRIMMSNARL, 3, hp=320), [], hand_count=5)

    # Myriad reaches 30+30x(4+3) = 210, doubled by the Grass weakness = 420 >= 320:
    # there IS a prize today, so no denial.
    plan = _plan(mine=mine, theirs=theirs, my_prize=4, op_prize=2)
    assert plan.prizes_today == 2 and not plan.denial_saves_the_game(1)

    plan = _plan(mine=mine, theirs=theirs, my_prize=2, op_prize=2,
                 wins_active=True)
    assert plan.mode == gp.MODE_WIN_NOW and not plan.denial_saves_the_game(1)


# ---------------------------------------------------------------------------
# The empty plan: a context without one behaves as it did before the plan existed
# ---------------------------------------------------------------------------

def test_no_plan_is_inert():
    assert not gp.NO_PLAN.wins_this_turn
    assert not gp.NO_PLAN.lethal_gust
    assert not gp.NO_PLAN.gust_closes_it_now
    assert not gp.NO_PLAN.denial_saves_the_game(1)
    assert gp.plan_of(object()) is gp.NO_PLAN
    assert gp.plan_of(None) is gp.NO_PLAN
