"""On a dead turn the Last-Ditch Catch fetches the ENERGY, not the refill.

Record (user, episode 90591443 step 84, turn 8 vs Marnie's Grimmsnarl ex /
Froslass, LOST). The first menu of the turn:

    US                                          RIVAL
    active  Teal Mask Ogerpon ex 20 HP, 2 of 3   active  Grimmsnarl ex 310/320, 2 {D}
    bench   Meganium 2 of 4, Ogerpon ex 0 of 3,  bench   Froslass, Munkidori x2,
            Ogerpon ex 2 of 3, Tapu Bulu 0 of 4          Impidimp x2
    hand    Chikorita, Bayleef, Boss's Orders, Hydrapple ex,
            Forest of Vitality, Meowth ex x2, Xerosic's -- NO GRASS
    discard 2 Basic Grass                        prizes  6 us / 4 them

Nothing could attack and nothing could be charged: with no Grass in hand the
turn's attachment had nothing to attach and Teal Dance nothing to pay itself
with. The only energy that still existed was in our own DISCARD. The agent
played Boss's Orders, gusted the Froslass and ended the turn with zero prizes.

What the line was worth: bench a Meowth ex, Last-Ditch Catch fetches LANA'S AID,
it recovers the two Grass, one goes on the active (Meganium's Wild Growth makes
each worth 2) and Myriad Leaf Shower does 30 + 30 x (4 ours + 2 theirs) = 210,
doubled by their Grass weakness = 420 on a 310 HP Marnie's Grimmsnarl ex. Their
attacker and two prizes, out of a turn that was about to end for nothing.

TWO THINGS WERE IN THE WAY, and each is fixed where it lives:

  * the Meowth ex was never benched. The Froslass branch of the play scorer
    (`ptcg/turn/options/play.py`) already carried the dead-turn exception for
    this very matchup, but it asked "can the active retreat" -- a retreat COST,
    read alone. Our active could pay it, so the exception switched off, even
    though retreating led to nobody: every body on the bench was short of its
    own attack cost. The clause now asks the whole question, retreat AND a body
    ready to come up (`_bench_attacker_ready`);
  * the fetch pointed at the refill. `stuck_without_energy` fires on exactly
    these boards -- "the active cannot attack and there is no Grass in hand" --
    and hard-codes Lillie's Determination as the answer, capping every other
    candidate at 150. Refilling is right when a CARD is missing; here the
    missing thing was ENERGY, and it was already ours. The new
    `recovery_creates_the_ko` rule of `_RULES_MEOWTH_FETCH` asks the SHARED
    arithmetic of `ROUTE_RECOVER` (`_recovery_creates_the_ko`, factored out of
    `_win_via_energy_recovery` so there is one sum and not two) and points the
    fetch at Lana's Aid when the recovery is what creates the knockout.

It yields to a SHORT HAND (<= 2 cards, the ladder's own cut-off): there the
refill is not competing with the recovery, it contains it -- Lillie's draws
eight out of a thirteen-Grass deck and shuffles away nothing worth keeping.

Coverage:
  * the record's board: the Meowth ex goes down, the Boss's Orders does not;
  * the fetch itself, on the prompt that follows: Lana's Aid;
  * control -- no Grass in the discard: there is nothing to recover and the
    fetch falls back to Lillie's;
  * control -- a hand of two: the refill contains the recovery and wins;
  * control -- a benched attacker already at its cost: the retreat rescues the
    turn, it is not dead, and the Boss's Orders keeps it;
  * DETECT IS NOT EXECUTE -- the tail of the line on the record's board: the
    recovered Grass reaches the ACTIVE and not the bench (which is how
    `ROUTE_RECOVER` failed against Crustle), the attack happens, and the very
    same board without the recovery ends the turn;
  * the shared arithmetic, and that factoring it out left `ROUTE_RECOVER`
    answering exactly as before (`test_the_recovery_that_wins_the_game.py`).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType, OptionType
import ptcg.turn.game_plan as gp

GRASS = m.Basic_Grass_Energy
MEOWTH = m.Meowth_ex
BOSS = m.Boss_Orders
LANA = m.Lanas_Aid
LILLIE = m.Lillie_Determination
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
TAPU = m.Tapu_Bulu

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step84_the_recovery_the_last_ditch_goes_for.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _data():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _played(obs, choice):
    """The id of the card the chosen PLAY option puts down, or None."""
    assert choice, f"the agent returned nothing: {choice}"
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != int(OptionType.PLAY):
        return None
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return mine["hand"][opt["index"]]["id"]


def _fetched(obs, choice):
    """The id of the card the chosen deck-search option takes."""
    assert choice, f"the agent returned nothing: {choice}"
    sel = obs["select"]
    return sel["deck"][sel["option"][choice[0]]["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step84_the_board_is_the_records_one():
    obs = _data()["observation"]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 8 and not cur["supporterPlayed"]
    assert not cur["energyAttached"], "the turn's attachment is still unspent"
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 0, (
        "no Grass in hand: neither the attachment nor Teal Dance can pay itself")
    assert sum(1 for c in mine["discard"] if c["id"] == GRASS) == 2, (
        "the two Basic Grass in the discard are the turn's only energy")
    # Nothing of ours reaches its own attack cost.
    assert len(mine["active"][0]["energies"]) == 2
    assert mine["active"][0]["id"] == OGERPON  # Myriad Leaf Shower costs 3
    assert sorted((p["id"], len(p["energies"])) for p in mine["bench"]) == sorted(
        [(MEGANIUM, 2), (OGERPON, 0), (OGERPON, 2), (TAPU, 0)])
    assert sum(1 for c in mine["hand"] if c["id"] == MEOWTH) == 2
    assert sum(1 for c in mine["hand"] if c["id"] == BOSS) == 1
    assert theirs["active"][0]["hp"] == 310


def test_step84_benches_the_meowth_instead_of_gusting():
    obs = _data()["observation"]
    choice = m.agent(obs)
    assert _played(obs, choice) == MEOWTH, (
        f"a turn that cannot attack with anything and holds the energy in its "
        f"own discard: the Last-Ditch Catch is the play, not a gust that takes "
        f"no prize; got {choice}")


def test_step84_does_not_spend_the_supporter_slot_on_the_boss():
    obs = _data()["observation"]
    choice = m.agent(obs)
    assert _played(obs, choice) != BOSS, (
        "Boss's Orders takes the turn's only Supporter slot, and the Supporter "
        "the fetch is about to bring is what turns the turn into a knockout")


# ---------------------------------------------------------------------------
# 2. The fetch: the energy, not the refill
# ---------------------------------------------------------------------------

def test_the_last_ditch_fetches_the_recovery():
    obs = _data()["synthetic_fetch_prompt"]
    choice = m.agent(obs)
    assert _fetched(obs, choice) == LANA, (
        f"the missing thing is ENERGY and it is already ours: Lana's Aid "
        f"recovers it and the attack exists; got {choice}")


def test_with_nothing_in_the_discard_the_refill_wins_again():
    obs = _data()["synthetic_fetch_dry_discard"]
    choice = m.agent(obs)
    assert _fetched(obs, choice) == LILLIE, (
        "with no Grass in the discard there is nothing to recover: the fetch "
        "goes back to refilling the hand")


def test_a_hand_of_two_prefers_the_refill():
    obs = _data()["synthetic_fetch_short_hand"]
    choice = m.agent(obs)
    assert _fetched(obs, choice) == LILLIE, (
        "with two cards the refill CONTAINS the recovery: Lillie's draws eight "
        "out of a thirteen-Grass deck and shuffles away nothing worth keeping")


# ---------------------------------------------------------------------------
# 3. The control on the play: a legal retreat is not a play
# ---------------------------------------------------------------------------

def test_a_ready_bench_attacker_keeps_the_turn_alive():
    obs = _data()["synthetic_bench_attacker_ready"]
    choice = m.agent(obs)
    assert _played(obs, choice) != MEOWTH, (
        "with a benched Ogerpon ex already at its attack cost the retreat DOES "
        "rescue the turn: it is not a dead turn and the Meowth ex -- a 2-prize "
        "body in front of a Froslass that pings the bench -- stays in hand")


# ---------------------------------------------------------------------------
# 4. DETECT IS NOT EXECUTE: the tail of the line
# ---------------------------------------------------------------------------
# A rule that spots a knockout and then cannot carry it out is worse than no
# rule: it spends the Supporter and the body for nothing. That is exactly how
# `ROUTE_RECOVER` failed against Crustle -- it detected the win in 11 boards and
# the recovered Grass went to the BENCH in 8 of them. So the three steps after
# the fetch are pinned here on the record's board rebuilt with the scenario
# builder: the Grass reaches the ACTIVE, the attack happens, and without the
# recovery the very same board ends the turn.

def _after_the_recovery(active_energy, active_physical, hand, **menu):
    from state_builder import Scenario, pk, G
    import golden_corpus as gc
    gc.reset_agent(m)
    return (Scenario(turn=8, step=88, tac=6, first_player=1,
                     supporter_played=True,
                     energy_played=menu.pop("energy_played", False))
            .my_active(pk(OGERPON, hp=20, energies=[G] * active_energy,
                          fisicas=active_physical))
            .my_bench(pk(MEGANIUM, hp=150, energies=[G, G], fisicas=1,
                         pre_evo=[m.Chikorita, m.Bayleef]),
                      pk(OGERPON, hp=200),
                      pk(OGERPON, hp=200, energies=[G, G], fisicas=1),
                      pk(TAPU, hp=140),
                      pk(MEOWTH, hp=170))
            .my_hand(*hand)
            .op_active(pk(648, hp=310, max_hp=320, energies=[8, 8]))
            .op_bench(pk(104, hp=90, max_hp=90),
                      pk(112, hp=100, max_hp=110, energies=[8]),
                      pk(646, hp=70, max_hp=70))
            .op_zones(hand=3, deck=34, prizes=4)
            .deck(LANA)
            .rest_to_discard()
            .menu_hand(**menu)
            .build())


def test_the_recovered_grass_goes_to_the_active():
    obs = _after_the_recovery(2, 1, [GRASS, GRASS],
                              with_attachment=True, with_attack=True)
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"the recovery exists to charge the attacker; got {opt}")
    assert opt.get("inPlayArea") == int(AreaType.ACTIVE), (
        "parked on the bench the recovery buys nothing -- this is how "
        "ROUTE_RECOVER failed against Crustle")


def test_with_the_cost_covered_the_agent_attacks():
    obs = _after_the_recovery(4, 2, [], energy_played=True, with_attack=True)
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("attackId") == 120, (
        f"Myriad Leaf Shower is on the menu and knocks their active out; "
        f"got {opt}")


def test_without_the_recovery_the_same_board_ends_the_turn():
    # The premise of the whole rule, measured instead of asserted: at 2 of 3 and
    # with the attachment spent, there is nothing to do with this turn.
    obs = _after_the_recovery(2, 1, [], energy_played=True, with_attack=True)
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(OptionType.END), (
        f"if this board could do something, the turn was never dead; got {opt}")


# ---------------------------------------------------------------------------
# 5. The shared arithmetic
# ---------------------------------------------------------------------------

def _recovery_flag_on(obs):
    """`_meowth_recovery_ko` as agent() computed it for this observation."""
    import ptcg.turn.scoring as sc
    seen = {}
    original = sc.score_option

    def traced(tc, o, score):
        seen.setdefault("flag", getattr(tc, "_meowth_recovery_ko", "<absent>"))
        return original(tc, o, score)

    sc.score_option = traced
    m.score_option = traced
    try:
        m.agent(obs)
    finally:
        sc.score_option = original
        m.score_option = original
    return seen.get("flag")


def test_the_recovery_arithmetic_sees_the_knockout_on_the_records_board():
    assert _recovery_flag_on(_data()["observation"]) is True, (
        "two Grass out of the discard put the active Ogerpon ex at 4 effective: "
        "Myriad Leaf Shower 30 + 30 x (4 + 2) = 210, doubled by their Grass "
        "weakness = 420 on 310 HP")


def test_the_arithmetic_says_no_once_the_discard_is_empty_of_grass():
    obs = _data()["synthetic_fetch_dry_discard"]
    assert _recovery_flag_on(obs) is False, (
        "with nothing to recover the sum has to come back false: the rule that "
        "reads it must never fire on a board where Lana's Aid brings no energy")


def test_there_is_only_one_fetch_ladder():
    """`_RULES_MEOWTH_FETCH` must stay a SINGLE object, and here is why.

    It used to exist twice -- main.py re-bound the name after
    `from ptcg.decision.meowth import *`, shadowing the package's copy -- and
    the two were read from different places:

      * `_meowth_fetch_prediction` (main.py) decides, BEFORE benching the Meowth
        ex, which Supporter the search would bring, and it read main's copy;
      * the real Last-Ditch prompt (`ptcg/turn/options/card.py`) imports the
        rule list from `ptcg.decision.meowth`, so it read the package's.

    A rule added to one and not the other makes the agent bench a 2-prize body
    for a fetch it then does not make -- and nothing would say so: no exception,
    no red test, just a different decision in a game. Two sibling ladders had
    already drifted that way (`_RULES_NS_GRASS`, `_RULES_UB_MEOWTH`).

    So main.py's copies were deleted rather than kept in sync, and this is the
    invariant that replaces the synchronisation: one list, one truth.
    """
    import ptcg.decision.meowth as pkg
    assert m._RULES_MEOWTH_FETCH is pkg._RULES_MEOWTH_FETCH, (
        "main.py has re-bound the fetch ladder again: the prediction and the "
        "real fetch can now disagree about which Supporter the Last-Ditch "
        "Catch brings")


def test_the_shared_arithmetic_is_the_one_the_winning_route_uses():
    # The refactor's contract in one line: `_win_via_energy_recovery` no longer
    # carries its own copy of the sum. If someone re-inlines it, this fails and
    # `test_the_recovery_that_wins_the_game.py` stops guarding this rule too.
    import inspect
    src = inspect.getsource(gp._win_via_energy_recovery)
    assert "_recovery_creates_the_ko" in src, (
        "the winning route must delegate to the shared arithmetic, not keep a "
        "second copy of it")
