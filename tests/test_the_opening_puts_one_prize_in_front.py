"""The opening: one prize in front, the real attacker behind it.

THE PLAN (user, ago 2026), one sentence in three decisions:

    WHEN THE OPPONENT STARTS TAKING PRIZES, THE BODY IN FRONT PAYS ONE, NOT
    TWO -- while the attacker we actually want is assembled on the bench.

Most of the field knocks a 210 HP ex out on its SECOND turn, and if the
opponent goes first that is our second turn, before we have attacked once.
Handing them two prizes there is handing them a third of the game for a body
that had not done anything yet.

The three decisions, and where each of them lives:

  1. THE SETUP (`SETUP_ACTIVE_BASIC_ORDER` / `SETUP_ACTIVE_EX_ORDER` in
     ptcg/cards/ids.py, scored in ptcg/turn/options/card.py). Every body in
     this deck is a Basic, ex included, so "start with a Basic" means start
     with a Basic that is NOT an ex: Tapu Bulu, then Applin, then Chikorita.
     Only a hand with none of them reaches the ex, and there the order is Teal
     Mask Ogerpon ex, Fezandipiti ex, Meowth ex.

  2. THE FIRST TURN. Started with a Basic, nothing changes -- the energy goes
     to the bench as it always has. Started with an ex, the single attachment
     of the turn goes to the ex itself (`_opening_sac_charge_active`), because
     that is what makes the engine OFFER the retreat, and the turn also tries
     to produce a one-prize body: from hand (`_opening_sac_wall_in_hand`) or,
     failing that, out of the deck with a Poke Pad (`_pp_opening_sac_target`).

  3. THE END OF THAT TURN (`_opening_sac_pivot`, main.py). Against the eight
     openings that cannot cash the ex in early the ex STAYS in front; against
     everything else -- the sixteen archetypes the user listed, and "others" --
     it retreats and a one-prize body takes the front. That half has its own
     file, `test_the_ex_does_not_wait_in_front_on_our_first_turn.py`; what is
     pinned here is the setup and the first-turn preparation.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import OptionType, SelectContext
from state_builder import Scenario, pk

_SETUP_FIXTURE = ROOT / "tests" / "fixtures" / "setup_activo_tapu_bulu.json"

G = int(m.EnergyType.GRASS)
W = int(m.EnergyType.WATER)

TAPU = m.Tapu_Bulu
APPLIN = m.Applin
CHIKORITA = m.Chikorita
OGERPON = m.Teal_Mask_Ogerpon_ex
FEZANDIPITI = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex
PINSIR = m.Pinsir
ALAKAZAM = m.Alakazam_ex
ABRA = m.Abra


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m._init_cards_tracking()


# ---------------------------------------------------------------------------
# 1. The setup
# ---------------------------------------------------------------------------

def _setup(*hand_ids):
    """A SETUP_ACTIVE_POKEMON menu offering exactly `hand_ids`, in that order.

    Built off the real fixture so the shape of the observation is the
    simulator's own; only the hand and the options are rewritten.
    """
    obs = copy.deepcopy(json.load(open(_SETUP_FIXTURE, encoding="utf-8"))
                        ["observation"])
    cur = obs["current"]
    me = cur["players"][cur["yourIndex"]]
    me["hand"] = [{"id": cid, "playerIndex": cur["yourIndex"],
                   "serial": 500 + i} for i, cid in enumerate(hand_ids)]
    obs["select"]["option"] = [
        {"area": 2, "index": i, "playerIndex": cur["yourIndex"], "type": 3}
        for i in range(len(hand_ids))]
    assert obs["select"]["context"] == int(SelectContext.SETUP_ACTIVE_POKEMON)
    return obs


def _seated(obs):
    cur = obs["current"]
    me = cur["players"][cur["yourIndex"]]
    return me["hand"][obs["select"]["option"][m.agent(obs)[0]]["index"]]["id"]


@pytest.mark.parametrize("hand,expected", [
    # The three named Basics, in the user's order, each against the next.
    ((APPLIN, TAPU), TAPU),
    ((CHIKORITA, TAPU), TAPU),
    ((CHIKORITA, APPLIN), APPLIN),
    ((CHIKORITA, APPLIN, TAPU), TAPU),
])
def test_the_basics_go_in_the_order_the_user_gave(hand, expected):
    assert _seated(_setup(*hand)) == expected


@pytest.mark.parametrize("basic", [TAPU, APPLIN, CHIKORITA, PINSIR])
@pytest.mark.parametrize("ex", [OGERPON, FEZANDIPITI, MEOWTH])
def test_no_ex_ever_outranks_a_non_ex_basic(basic, ex):
    """The one sentence the whole branch is built on. A 60 HP Applin in front
    is a worse body than a 210 HP Ogerpon ex in every way except the one that
    decides the game: when it falls the opponent is one prize closer, not two.
    Pinsir is in the list on purpose -- it is not named in the order, and an
    unnamed one-prize Basic still goes ahead of every ex."""
    assert _seated(_setup(ex, basic)) == basic


@pytest.mark.parametrize("hand,expected", [
    ((FEZANDIPITI, OGERPON), OGERPON),
    ((MEOWTH, OGERPON), OGERPON),
    ((MEOWTH, FEZANDIPITI), FEZANDIPITI),
    ((MEOWTH, FEZANDIPITI, OGERPON), OGERPON),
])
def test_with_no_basic_the_ex_order_decides(hand, expected):
    """The fallback, not a preference: reaching it means every body in hand
    costs two prizes, and then what counts is which of them the first turn can
    still use. Teal Dance develops from the active spot; Flip the Script only
    pays out after a knockout; Last-Ditch Catch works from the BENCH, so the
    active spot wastes the Meowth ex outright."""
    assert _seated(_setup(*hand)) == expected


def test_a_second_copy_no_longer_flips_the_order():
    """The tie-break the old ladder had: a Chikorita or an Applin we held TWO
    of scored the same (7), so two Chikorita and one Applin put the Chikorita
    in front -- the user's order says Applin. Holding a spare is a reason to be
    relaxed about the body we seat, not a reason to change which line starts
    developing."""
    assert _seated(_setup(CHIKORITA, CHIKORITA, APPLIN)) == APPLIN


# ---------------------------------------------------------------------------
# 2. The first turn, having started with an ex
# ---------------------------------------------------------------------------

def _first_turn(active=None, bench=(), hand=(), op_active=None,
                energy_played=True, **menu):
    """Our first turn going SECOND (turn 2), the seat the rule fires in, with
    an Alakazam in front: an opener that threatens nothing today and is one
    card from Powerful Hand."""
    sc = (Scenario(turn=2, step=20, first_player=1,
                   energy_played=energy_played, supporter_played=True)
          .my_active(active if active is not None else pk(OGERPON, energies=[G]))
          .op_active(op_active if op_active is not None
                     else pk(ABRA, energies=[G]))
          .op_zones(hand=5, deck=40, prizes=6))
    if bench:
        sc = sc.my_bench(*bench)
    if hand:
        sc = sc.my_hand(*hand)
    return sc.menu_hand(**menu).build()


def _chosen(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


def test_the_energy_of_the_turn_goes_to_the_active_ex():
    """"If we start with an ex in the active spot we attach ONE energy to it"
    (user). Read as arithmetic it is the same sentence as the pivot: the engine
    only OFFERS a retreat once the cost is on the body, so with an unpaid fee
    the ex ends the turn in front -- the outcome the rule exists to avoid."""
    obs = _first_turn(active=pk(OGERPON), bench=(pk(APPLIN),),
                      hand=(m.Basic_Grass_Energy,), energy_played=False,
                      with_attachment=True)
    opt = _chosen(obs)
    assert opt["type"] == int(m.OptionType.ATTACH), opt
    assert opt["inPlayArea"] == int(m.AreaType.ACTIVE), (
        "la Planta va al ex ACTIVO: es lo unico que hace que el motor OFREZCA "
        "la retirada")


def test_starting_with_a_basic_the_energy_still_goes_to_the_bench():
    """The other half of the user's rule, and the half that is a NO-OP: with a
    one-prize body already in front there is nothing to hide, so the charge
    goes on being decided by the logic that owns it -- the bench attacker."""
    obs = _first_turn(active=pk(APPLIN), bench=(pk(OGERPON),),
                      hand=(m.Basic_Grass_Energy,), energy_played=False,
                      with_attachment=True)
    opt = _chosen(obs)
    assert opt["type"] == int(m.OptionType.ATTACH), opt
    assert opt["inPlayArea"] != int(m.AreaType.ACTIVE)


@pytest.mark.parametrize("in_hand", [TAPU, APPLIN, CHIKORITA])
def test_the_one_prize_body_comes_out_of_the_hand(in_hand):
    """All three rungs are Basics, so a body missing from the board can still
    be arranged for: it goes down and comes up in the same turn."""
    obs = _first_turn(bench=(pk(MEOWTH),), hand=(in_hand, m.Ultra_Ball),
                      with_retreat=True)
    opt = _chosen(obs)
    assert opt["type"] == int(m.OptionType.PLAY)
    cur = obs["current"]
    assert cur["players"][cur["yourIndex"]]["hand"][opt["index"]]["id"] == in_hand


def test_the_poke_pad_goes_and_gets_the_body(monkeypatch):
    """"It is allowed to use a Poke Pad this turn to look for a Basic,
    especially if we do not have Tapu Bulu and need to find it" (user). With no
    one-prize body on the bench and none in hand the pivot cannot fire at all,
    and the Poke Pad is the one card that can still produce one."""
    ctx = m.DecisionContext.__new__(m.DecisionContext)
    from ptcg.decision.poke_pad import _pp_opening_sac_target
    from ptcg.state.zones import ZONE_DECK

    class _Ctx:
        cards_in_deck = {TAPU: {ZONE_DECK: 1}, APPLIN: {ZONE_DECK: 2},
                         CHIKORITA: {ZONE_DECK: 2}}
        field_counts = {}
        hand_counts = {}
        bench_count = 1
        opening_sac_needs_body = True

    assert _pp_opening_sac_target(_Ctx) == TAPU
    # Tapu already in play: the search moves down the same order.
    _Ctx.field_counts = {TAPU: 1}
    assert _pp_opening_sac_target(_Ctx) == APPLIN
    # ...and it stays silent when the pivot is not asking for a body.
    _Ctx.opening_sac_needs_body = False
    assert _pp_opening_sac_target(_Ctx) is None
    del ctx


def test_the_poke_pad_fetch_follows_the_same_order():
    """The fetch menu is a different decision from the decision to PLAY the
    Poke Pad, with a different context object, so the order is stated twice --
    and the two statements have to agree."""
    from ptcg.decision.poke_pad import _CtxPPFetch, _RULES_PP_FETCH
    from ptcg.engine.rules import _resolve_with_trace

    class _State:
        turn = 2

    def _score(card_id, needs_body=True):
        return _resolve_with_trace(
            "pp->fetch", _RULES_PP_FETCH, [],
            _CtxPPFetch(card_id, {}, {}, 1, _State, needs_body), default=10)

    assert _score(TAPU) > _score(APPLIN) > _score(CHIKORITA)
    # Above the ordinary first-turn development rung the Applin would win.
    assert _score(TAPU) > _score(APPLIN, needs_body=False)
