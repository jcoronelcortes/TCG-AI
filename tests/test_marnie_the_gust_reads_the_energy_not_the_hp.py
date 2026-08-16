"""Between two Munkidori it is the ENERGY that decides, never the HP -- and the
Froslass sits between the charged half of the species and the bare one.

Scenario (user, episode 93680377 step 173, turn 14, vs Marnie -- game WON, and
the gust still went to the wrong body):

    US (seat 1, 2 prizes)                RIVAL (4 prizes)
    active Hydrapple ex 280/330, 2G      active Munkidori 90/110, 1D
    bench  Ogerpon ex 4G, Hydrapple ex,  bench  [0] **Munkidori 100/110, 0e**
           Ogerpon ex 2G, Ogerpon ex 1G,        [1] **Munkidori 100/110, 1D**
           Fezandipiti ex                       [2] Marnie's Morgrem 100/100, 1D
                                                [3] Froslass 90/90
                                                [4] Marnie's Morgrem 100/100, 1D

Boss's Orders is already down; this is the TARGET select. The agent brought up
the body at index **0** -- the BARE Munkidori.

WHY, AND IT IS NOT THE HP
-------------------------
`marnie_the_engine_before_the_line` is the rung that owns this board, and it was
right to fire: our bench answers the Grimmsnarl ex, so the engine outranks the
line. What it could not do is tell the two Munkidori apart. Both are Munkidori,
both sit at exactly 100/110, so both were lifted to the same 15600 and the
argmax kept the FIRST -- "first on their bench" is not a reason, it is the
absence of one. The trace of that board, with the ladder before this change:

    idx 0  bare Munkidori    3450 -> 15600     <- chosen, by position alone
    idx 1  charged Munkidori 6450 -> 15600
    idx 3  Froslass          9600 -> 15400

Note the `tier_ko` the `max` throws away: 6000 for the charged Munkidori against
3000 for the bare one. The chains already knew which of the two was the more
developed body; the floor is what flattened them.

THE LADDER (user)
-----------------
    Munkidori WITH energy  >  Froslass  >  Munkidori WITHOUT energy  >  Snorunt

and inside any one rung, the body with the LOWEST current HP. Read in the two
directions the user stated it: a Munkidori outranks the Froslass while at least
one Munkidori carries energy, and with only bare Munkidori on the field the
Froslass goes first. One ladder answers both because the Froslass rung sits
between the two halves of the species.

Adrena-Brain costs no energy and a bare Munkidori still fires it, so the split
is not about the ability. It is about which copy their turn is already built
around: the charged one also ATTACKS out of the seat the gust sells it, and the
bare one is a body they have yet to pay for.

HP DOES NOT CHOOSE A RUNG. The tiebreak is bounded to 39, well under the 400
that separates two rungs, so no amount of damage lifts a bare Munkidori over a
Froslass or a Froslass over a charged Munkidori. It only separates bodies that
have already tied on everything the chains read -- which is exactly the pair
this record put on the board.

The whole ladder is `ptcg/decision/boss_orders.py::_marnie_engine_rung`; the
matchup gate it hangs from is unchanged and documented in
`tests/test_marnie_the_engine_before_the_line.py`.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from ptcg.state.agent_state import AGENT_STATE

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step174_el_gusteo_elige_el_munkidori_cargado.json")

MUNKIDORI = m.Munkidori
FROSLASS = m.Froslass
SNORUNT = m.Snorunt_Ice          # the print these lists actually play (70 HP)
MORGREM = m.Marnies_Morgrem
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
DARKNESS = 7                      # Basic {D} Energy, the id the record carries


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    AGENT_STATE.op_is_marnie_deck = False
    yield
    m._init_cards_tracking()
    AGENT_STATE.op_is_marnie_deck = False


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _me(o):
    return o["current"]["players"][o["current"]["yourIndex"]]


def _op(o):
    return o["current"]["players"][1 - o["current"]["yourIndex"]]


def _body(o, i):
    return _op(o)["bench"][i]


def _put(o, i, card_id, hp, max_hp, energy=0):
    """Rewrite one body of THEIR bench, keeping the shape the readers expect."""
    b = _body(o, i)
    b.update(id=card_id, hp=hp, maxHp=max_hp, preEvolution=[], tools=[])
    b["energies"] = [DARKNESS] * energy
    b["energyCards"] = [{"id": DARKNESS, "playerIndex": _op(o)["bench"][i]["playerIndex"],
                         "serial": 900 + i * 10 + k} for k in range(energy)]
    return b


def _gusted(o):
    """Run the agent on the target select and return the body it brought up."""
    chosen = m.agent(o)
    assert len(chosen) == 1
    return _body(o, chosen[0])


def _rung(card_id, hp, energy):
    return m._marnie_engine_rung(SimpleNamespace(
        card_id=card_id, hp=hp, energy=energy))


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_target_select_of_step_173():
    o = _obs()
    assert o["current"]["turn"] == 14
    # Boss's Orders is already down: the menu is the five bodies of their bench.
    assert o["select"]["context"] == 3
    assert [op["index"] for op in o["select"]["option"]] == [0, 1, 2, 3, 4]
    assert o["select"]["effect"]["id"] == m.Boss_Orders

    # THE PAIR THAT TIED: same species, same 100/110, and only the energy apart.
    assert [(b["id"], b["hp"], b["maxHp"], len(b["energies"]))
            for b in _op(o)["bench"]] == [
        (MUNKIDORI, 100, 110, 0),
        (MUNKIDORI, 100, 110, 1),
        (MORGREM, 100, 100, 1),
        (FROSLASS, 90, 90, 0),
        (MORGREM, 100, 100, 1)]

    # Us: a Hydrapple ex in front and a charged Ogerpon ex on the bench, which is
    # the reserve that switches the engine ladder on at all.
    assert _me(o)["active"][0]["id"] == HYDRAPPLE
    assert _me(o)["bench"][0]["id"] == OGERPON
    assert len(_me(o)["bench"][0]["energies"]) == 4


def test_the_engine_rung_is_the_one_that_owns_this_board():
    """The gate is unchanged: our bench answers the Grimmsnarl ex, so the engine
    outranks the line. Every assertion below is about WHICH engine body."""
    o = _obs()
    def pk(d):
        return SimpleNamespace(id=d["id"], hp=d["hp"], maxHp=d["maxHp"],
                               energies=list(d["energies"]),
                               energyCards=d["energyCards"], tools=d["tools"],
                               serial=d["serial"])
    me, op = _me(o), _op(o)
    my_state = SimpleNamespace(active=[pk(me["active"][0])],
                               bench=[pk(b) for b in me["bench"]])
    op_state = SimpleNamespace(active=[pk(op["active"][0])],
                               bench=[pk(b) for b in op["bench"]])
    grass = sum(len(p.energies) for p in [my_state.active[0]] + my_state.bench)
    assert m._marnie_bench_answers_the_grimmsnarl(
        my_state, op_state, grass, len(my_state.bench), False)


# ---------------------------------------------------------------------------
# 2. The record: energy breaks the tie the HP could not
# ---------------------------------------------------------------------------

def test_the_gust_takes_the_charged_munkidori_and_not_the_bare_one():
    o = _obs()
    got = _gusted(o)
    assert (got["id"], len(got["energies"])) == (MUNKIDORI, 1), (
        "con dos Munkidori identicos salvo la energia, el gusteo va al CARGADO: "
        "es la copia que ademas ataca desde el asiento que le estamos vendiendo")
    assert got["serial"] == 7        # the body at index 1 of the record


def test_the_hp_does_not_choose_between_the_two_halves_of_the_species():
    """THE FIRST RULE, stated as its worst case: the bare Munkidori almost dead
    and the charged one untouched. HP is a tiebreak inside a rung and cannot
    reach across one."""
    o = _obs()
    _put(o, 0, MUNKIDORI, 10, 110, energy=0)     # bare, one counter from dying
    _put(o, 1, MUNKIDORI, 110, 110, energy=1)    # charged, at full
    got = _gusted(o)
    assert (got["hp"], len(got["energies"])) == (110, 1)


def test_between_two_charged_munkidori_the_one_with_less_hp_goes_first():
    """SECOND RULE, first half: inside the charged rung the tiebreak is the HP,
    and it is the LOWEST that goes."""
    o = _obs()
    _put(o, 0, MUNKIDORI, 40, 110, energy=1)
    _put(o, 1, MUNKIDORI, 100, 110, energy=1)
    assert _gusted(o)["hp"] == 40
    # ...and it is the HP and not the bench order that did it.
    o = _obs()
    _put(o, 0, MUNKIDORI, 100, 110, energy=1)
    _put(o, 1, MUNKIDORI, 40, 110, energy=1)
    assert _gusted(o)["hp"] == 40


def test_between_two_bare_munkidori_with_no_froslass_the_lowest_hp_goes_first():
    """SECOND RULE, second half. The Froslass is taken off the board so the bare
    rung is the top one, which is the only way to observe its internal order."""
    o = _obs()
    _put(o, 0, MUNKIDORI, 100, 110, energy=0)
    _put(o, 1, MUNKIDORI, 60, 110, energy=0)
    _put(o, 3, MORGREM, 100, 100, energy=1)      # no Froslass anywhere
    assert _gusted(o)["hp"] == 60


# ---------------------------------------------------------------------------
# 3. Where the Froslass sits, which is the same rule read twice
# ---------------------------------------------------------------------------

def test_with_only_bare_munkidori_the_froslass_goes_first():
    """THIRD RULE, first half: a Froslass in play and no charged Munkidori on
    the field -- the Froslass is the target."""
    o = _obs()
    _put(o, 0, MUNKIDORI, 100, 110, energy=0)
    _put(o, 1, MUNKIDORI, 100, 110, energy=0)
    _op(o)["active"][0]["energies"] = []          # their active Munkidori too
    _op(o)["active"][0]["energyCards"] = []
    assert _gusted(o)["id"] == FROSLASS


def test_a_charged_munkidori_we_cannot_gust_does_not_lift_the_bare_ones():
    """THE READING OF THE AMBIGUOUS CASE, pinned on purpose so that changing it
    is a decision and not an accident.

    "Munkidori outranks Froslass when at least one Munkidori has energy" is
    about the body being CHOSEN, not about a copy somewhere on the board. Their
    ACTIVE Munkidori carries a Darkness here -- it is exactly the board of the
    record -- but the active spot is not on the gust menu, so what the Supporter
    can actually buy is a bare Munkidori or the Froslass, and the ladder puts
    the Froslass first. Lifting the bare ones because of a copy we cannot reach
    would pay the charged Munkidori's price for a body that is not it.
    """
    o = _obs()
    _put(o, 0, MUNKIDORI, 100, 110, energy=0)
    _put(o, 1, MUNKIDORI, 100, 110, energy=0)
    assert len(_op(o)["active"][0]["energies"]) == 1     # their active IS charged
    assert _op(o)["active"][0]["id"] == MUNKIDORI
    assert _gusted(o)["id"] == FROSLASS


def test_one_charged_munkidori_is_enough_to_outrank_the_froslass():
    """THIRD RULE, second half. The Froslass is left at 10 HP and the Munkidori
    at full: the rung, not the damage, is what decides."""
    o = _obs()
    _put(o, 0, MUNKIDORI, 100, 110, energy=0)
    _put(o, 1, MUNKIDORI, 110, 110, energy=1)
    _put(o, 3, FROSLASS, 10, 90, energy=0)
    got = _gusted(o)
    assert (got["id"], len(got["energies"])) == (MUNKIDORI, 1)


def test_the_bare_munkidori_still_outranks_the_snorunt():
    """The bottom of the ladder: with the Froslass gone, a bare Munkidori is
    still worth more than the Snorunt that would become the next Froslass."""
    o = _obs()
    _put(o, 0, MUNKIDORI, 100, 110, energy=0)
    _put(o, 1, SNORUNT, 70, 70, energy=0)
    _put(o, 3, MORGREM, 100, 100, energy=1)
    assert _gusted(o)["id"] == MUNKIDORI


def test_the_froslass_outranks_the_snorunt_when_no_munkidori_is_charged():
    o = _obs()
    _put(o, 0, MUNKIDORI, 100, 110, energy=0)
    _put(o, 1, SNORUNT, 70, 70, energy=0)
    _op(o)["active"][0]["energies"] = []
    _op(o)["active"][0]["energyCards"] = []
    assert _gusted(o)["id"] == FROSLASS


# ---------------------------------------------------------------------------
# 4. The ladder itself: the order is absolute and the tiebreak stays a tiebreak
# ---------------------------------------------------------------------------

def test_the_four_rungs_are_ordered_and_no_hp_can_swap_them():
    """The rungs at their WORST case against each other: every body at full HP
    against the rung below it at 10 HP, which is the largest tiebreak the term
    can ever produce."""
    charged_full = _rung(MUNKIDORI, 110, 1)
    froslass_dying = _rung(FROSLASS, 10, 0)
    froslass_full = _rung(FROSLASS, 90, 0)
    bare_dying = _rung(MUNKIDORI, 10, 0)
    bare_full = _rung(MUNKIDORI, 110, 0)
    snorunt_dying = _rung(SNORUNT, 10, 0)
    assert charged_full > froslass_dying
    assert froslass_full > bare_dying
    assert bare_full > snorunt_dying


def test_the_tiebreak_is_bounded_below_one_rung_of_spacing():
    """What keeps the order absolute: the widest HP swing inside a rung has to
    be smaller than the gap between two rungs."""
    widest = _rung(MUNKIDORI, 0, 1) - _rung(MUNKIDORI, 340, 1)
    spacing = min(m.MARNIE_ENGINE_GUST_RANK[MUNKIDORI] - m.MARNIE_ENGINE_GUST_RANK[FROSLASS],
                  m.MARNIE_ENGINE_GUST_RANK[FROSLASS] - m.MARNIE_ENGINE_DRY_MUNKIDORI,
                  m.MARNIE_ENGINE_DRY_MUNKIDORI - m.MARNIE_ENGINE_GUST_RANK[SNORUNT])
    assert 0 < widest <= m.MARNIE_ENGINE_HP_TIEBREAK_MAX < spacing


def test_inside_a_rung_less_hp_scores_higher():
    assert _rung(MUNKIDORI, 40, 1) > _rung(MUNKIDORI, 100, 1)
    assert _rung(FROSLASS, 40, 0) > _rung(FROSLASS, 90, 0)
    assert _rung(MUNKIDORI, 40, 0) > _rung(MUNKIDORI, 100, 0)


def test_a_body_with_no_hp_reading_sorts_last_inside_its_rung():
    """The 999 default of the context: a shape the reader did not expect must
    not jump the queue over a body we can actually measure."""
    assert _rung(MUNKIDORI, 999, 1) < _rung(MUNKIDORI, 110, 1)
    assert _rung(MUNKIDORI, 999, 1) > m.MARNIE_ENGINE_GUST_RANK[FROSLASS]


def test_the_band_still_sits_between_a_one_prize_and_a_two_prize_knockout():
    """Unchanged reason, re-checked at the new height: the ladder must outrank
    every one-prize KO tier and stay under a genuine two-prize one."""
    top_of_the_one_prize_band = 4 * 3000 + 1100
    floor_of_the_two_prize_band = 7 * 3000
    top_rung = m.BOSS_SCORE_MARNIE_ENGINE_FIRST + _rung(MUNKIDORI, 0, 1)
    bottom_rung = m.BOSS_SCORE_MARNIE_ENGINE_FIRST + _rung(SNORUNT, 70, 0)
    assert top_of_the_one_prize_band < bottom_rung
    assert top_rung < floor_of_the_two_prize_band


def test_the_ladder_does_not_leave_the_marnie_matchup():
    """The one per-deck rung of the chain, re-pinned on the new board: swap the
    line for Dragapult's and the engine order stops applying."""
    o = _obs()
    _op(o)["active"][0].update(id=m.Dreepy, hp=60, maxHp=60,
                               energies=[], energyCards=[])
    _put(o, 2, m.Drakloak, 90, 90, energy=0)
    _put(o, 4, m.Dreepy, 60, 60, energy=0)
    assert _gusted(o)["id"] == m.Drakloak


# ---------------------------------------------------------------------------
# 5. THE OTHER LADDER. Which chain runs is decided by OUR active, and the
#    matchup does not change with it.
# ---------------------------------------------------------------------------

_JAM_FIXTURE = (ROOT / "tests" / "fixtures"
                / "marnie_the_relay_inherits_the_seat_step72.json")

# Their bench in `registro_008` step 72, in menu order.
J_MUNKI_CHARGED, J_MUNKI_BARE, J_GRIMM, J_FROS = 0, 1, 2, 3


def _jam_obs(unlock=True):
    """The step-72 board, with the seat UNLOCKED by default.

    Three Grass on the Tapu Bulu pay its retreat (cost 3) without letting it
    attack (Wood Hammer costs 4): our active cannot attack, so
    `ptcg/turn/options/card.py` routes the menu to the JAM chain -- and it CAN
    step aside, so `can_ko` reaches their bench through the benched Ogerpon.
    That pair is the only state in which the engine ladder has anything to say
    in this chain, and it is the state the relay rule's own control describes.
    """
    with open(_JAM_FIXTURE, encoding="utf-8") as f:
        o = copy.deepcopy(json.load(f)["observation"])
    if unlock:
        active = o["current"]["players"][1]["active"][0]
        active["energies"] = [1, 1, 1]
        active["energyCards"] = [{"id": 1, "playerIndex": 1, "serial": 900 + i}
                                 for i in range(3)]
    return o


def _jam_bench(o):
    return o["current"]["players"][0]["bench"]


def _jam_gusted(o):
    chosen = m.agent(o)
    return _jam_bench(o)[chosen[0]]


def _jam_score(ctx):
    from ptcg.engine.rules import _resolve_rules
    return _resolve_rules(m._RULES_GUST_NUISANCE, m._ADJUST_GUST_NUISANCE,
                          ctx, default=-200)[0]


def _jam_ctxs(o):
    """The contexts as the agent builds them, so the numbers below are the ones
    the decision was made on."""
    from ptcg.turn.options import card as opt_card
    seen = {}
    original = opt_card._ctx_gust_target

    def spy(card, opt, *a, **k):
        ctx = original(card, opt, *a, **k)
        seen[opt.index] = ctx
        return ctx

    opt_card._ctx_gust_target = spy
    try:
        m.agent(o)
    finally:
        opt_card._ctx_gust_target = original
    return seen


def test_the_jam_chain_is_the_one_running_on_this_board():
    """Without this the section below would be re-testing the offensive chain
    under another name."""
    o = _jam_obs()
    ctxs = _jam_ctxs(o)
    assert set(ctxs) == {0, 1, 2, 3}
    # Our active cannot attack -- that is what selects the chain -- but every
    # candidate is knockable through the retreat, which is what lets the ladder
    # have an opinion at all.
    assert all(c.can_ko for c in ctxs.values())
    assert all(c.marnie_engine_first for c in ctxs.values())


def test_in_the_jam_chain_the_bigger_prize_still_wins():
    """THE BRACKET. Their Grimmsnarl ex is on the bench at 310/320 and pays TWO
    prizes; the engine ladder must not outbid it. This chain has no `tier_ko` to
    say so, which is why `the_bigger_prize_outranks_the_engine` exists."""
    o = _jam_obs()
    got = _jam_gusted(o)
    assert got["id"] == m.Grimmsnarl_ex
    ctxs = _jam_ctxs(o)
    assert ctxs[J_GRIMM].prizes == 2
    assert _jam_score(ctxs[J_GRIMM]) > _jam_score(ctxs[J_MUNKI_CHARGED])


def test_with_no_bigger_prize_the_jam_chain_uses_the_same_engine_ladder():
    """Take the two-prize body off their bench and the same order as in the
    offensive chain appears: charged Munkidori (100/110, 1e) over the Froslass
    over the bare Munkidori (80/110)."""
    o = _jam_obs()
    _jam_bench(o)[J_GRIMM].update(id=m.Marnies_Morgrem, hp=100, maxHp=100)
    got = _jam_gusted(o)
    assert (got["id"], len(got["energies"])) == (MUNKIDORI, 1)
    ctxs = _jam_ctxs(o)
    assert (_jam_score(ctxs[J_MUNKI_CHARGED])
            > _jam_score(ctxs[J_FROS])
            > _jam_score(ctxs[J_MUNKI_BARE]))


def test_the_jam_chain_also_puts_the_engine_before_the_line():
    """The parent sentence, in the other ladder. `opponent_line_higher_evolution`
    scores a benched Marnie's Morgrem 6000 + 3000 + 50 = 9050 and is blind to
    which body is winning the game; the engine floor is 15000."""
    o = _jam_obs()
    _jam_bench(o)[J_GRIMM].update(id=m.Marnies_Morgrem, hp=100, maxHp=100)
    ctxs = _jam_ctxs(o)
    assert ctxs[J_GRIMM].prizes == 1 and ctxs[J_GRIMM].is_stage1
    assert _jam_score(ctxs[J_MUNKI_CHARGED]) > _jam_score(ctxs[J_GRIMM])
    assert _jam_gusted(o)["id"] == MUNKIDORI


def test_with_the_seat_locked_the_engine_ladder_stays_quiet():
    """THE CONTROL, and it is the board of the record the jam chain was written
    from: a stuck active reaches nothing, `can_ko` is False for all four, and
    `the_relay_inherits_the_seat` decides with its own reasons."""
    o = _jam_obs(unlock=False)
    ctxs = _jam_ctxs(o)
    assert not any(c.can_ko for c in ctxs.values())
    assert _jam_gusted(o)["id"] == m.Grimmsnarl_ex


def test_the_two_chains_carry_the_SAME_rung_object():
    """One sentence, one place. Two copies of this rule is exactly how the
    matchup came to depend on whether our active happened to be usable."""
    named = [a for a in m._ADJUST_GUST_NUISANCE
             if getattr(a, "name", None) == "marnie_the_engine_before_the_line"]
    other = [a for a in m._ADJUST_GUST_OFFENSIVE
             if getattr(a, "name", None) == "marnie_the_engine_before_the_line"]
    assert len(named) == len(other) == 1
    assert named[0] is other[0]


def test_the_bigger_prize_bracket_sits_between_the_engine_and_the_relay():
    """The band, in numbers: above the engine ceiling and below the relay, which
    stays on top because a locked seat outranks the matchup."""
    engine_ceiling = m.BOSS_SCORE_MARNIE_ENGINE_FIRST + _rung(MUNKIDORI, 0, 1)
    two_prizes = (m.BOSS_SCORE_MARNIE_ENGINE_FIRST + m.MARNIE_ENGINE_BIGGER_PRIZE
                  + 2 * m.MARNIE_ENGINE_BIGGER_PRIZE_STEP)
    three_prizes = (m.BOSS_SCORE_MARNIE_ENGINE_FIRST + m.MARNIE_ENGINE_BIGGER_PRIZE
                    + 3 * m.MARNIE_ENGINE_BIGGER_PRIZE_STEP)
    relay_floor = 20000 + 1 * 2000
    assert engine_ceiling < two_prizes < three_prizes < relay_floor


def test_the_bigger_prize_bracket_does_not_leave_the_marnie_matchup():
    """It is the missing half of THIS ladder's band, not a general repair of the
    jam chain's prize-blindness: without `marnie_engine_first` it never fires."""
    rung = next(a for a in m._ADJUST_GUST_NUISANCE
                if getattr(a, "name", None)
                == "the_bigger_prize_outranks_the_engine")
    ctx = SimpleNamespace(marnie_engine_first=False, can_ko=True, prizes=3)
    assert not rung.when(ctx, 500)
    ctx.marnie_engine_first = True
    assert rung.when(ctx, 500)
    # ...and a vetoed target is not resurrected by it either.
    assert not rung.when(ctx, m.SCORE_FORBID)
