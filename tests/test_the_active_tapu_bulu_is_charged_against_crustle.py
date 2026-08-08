"""vs Crustle, the ACTIVE Tapu Bulu takes the turn's energy.

THE RULE (user, registro_002 step 17 vs Crustle, LOST; restated ago 2026):
against the ex-immune wall, Tapu Bulu is our MAIN attacker -- our ex do ZERO to
Crustle, so Wood Hammer is the only thing on our side that removes it -- and an
active Tapu Bulu therefore has the FIRST charging priority, from the first turn.

IT WAS ONLY HALF IMPLEMENTED, and this file is about the half that was missing.
A charge has two halves that live in two different functions, and a rule that
only does one of them does nothing:

  * the ACT of attaching (`ptcg/turn/options/attach.py`). The generic first-turn
    veto -- "do not charge the opening active" -- used to cancel the attachment
    outright. `_ft_veto_ids` already exempts Tapu Bulu when `op_is_crustle_deck`,
    and that half has been in place since jul 2026;
  * the DESTINATION (`ptcg/turn/energy.py`). Here the active Tapu Bulu scored
    20100 (20000 + 100 for being active) while a benched Applin scored 28500
    (22000 + the 6500 of `_ctm_applin_bench`). The Applin won.

The hole was hidden by the shape of the board the rule was measured on. The
+11000 "Crustle band" was being paid for `_ctm_chikorita_bench` -- whether the
CHIKORITA LINE happened to be on our bench -- which says nothing about the body
being charged. With a Chikorita there the active Tapu reached 31100 and won;
with the Applin line alone it never got the turn's energy until it already had
three, on EVERY turn, not just the first:

    bench = Applin only, active Tapu at 0 energies, vs Crustle
        turn 2  -> the benched Applin      turn 6  -> the benched Applin
        turn 4  -> the benched Applin      turn 8  -> the benched Applin

Now the band is earned by BEING the active Tapu Bulu against that wall. The two
arms do not stack: one band, because 42100 would climb into the lethal floor
(41000+) reserved for charges that take a prize today.

WHAT THIS FILE DOES NOT CLAIM. The golden corpus is blind to it -- of its five
crustle_wall games, ZERO have a board with an active Tapu Bulu below four
energies and an attachment on the menu -- so "no flips" there is not evidence
about this rule, and these are the tests that watch it instead.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Scenario, pk, G

TAPU = m.Tapu_Bulu
APPLIN = m.Applin
CHIKORITA = m.Chikorita
MEOWTH = m.Meowth_ex
CRUSTLE = m.Crustle_Grass
DWEBBLE = m.Dwebble_Grass
ABRA = m.Abra


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m._init_cards_tracking()


def _attachment(bench, op_active, turn=2, tapu_energies=0):
    """The turn's attachment on a board with an active Tapu Bulu.

    Returns "ACTIVE", the id of the benched body that got it, or None if the
    agent chose not to attach at all.
    """
    obs = (Scenario(turn=turn, step=12, first_player=1,
                    energy_played=False, supporter_played=True)
           .my_active(pk(TAPU, energies=[G] * tapu_energies))
           .my_bench(*[pk(b) for b in bench])
           .my_hand(m.Basic_Grass_Energy)
           .op_active(pk(op_active, energies=[G]))
           .op_zones(hand=5, deck=40, prizes=6)
           .menu_hand(with_attachment=True).build())
    opt = obs["select"]["option"][m.agent(obs)[0]]
    if opt["type"] != int(m.OptionType.ATTACH):
        return None
    if opt["inPlayArea"] == int(m.AreaType.ACTIVE):
        return "ACTIVE"
    return bench[opt["inPlayIndex"]]


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bench", [
    [APPLIN],                 # the board the hole lived on
    [CHIKORITA],              # the board the old clause already covered
    [APPLIN, CHIKORITA],
    [APPLIN, MEOWTH],
    [MEOWTH],
])
def test_the_active_tapu_takes_the_energy_whatever_the_bench_looks_like(bench):
    """What earns the charge is being the active Tapu Bulu in front of the
    wall, not what the bench happens to hold."""
    assert _attachment(bench, DWEBBLE) == "ACTIVE"


@pytest.mark.parametrize("turn", [2, 4, 6, 8])
def test_it_is_not_a_first_turn_rule(turn):
    """"From the first turn", not "on the first turn": every turn Tapu's climb
    to four energies is deferred is a turn the wall lives."""
    assert _attachment([APPLIN], DWEBBLE, turn=turn) == "ACTIVE"


@pytest.mark.parametrize("op_active", [DWEBBLE, CRUSTLE])
def test_the_matchup_is_read_off_the_line_and_not_off_the_wall_itself(op_active):
    """`op_is_crustle_deck` switches on for the Dwebble too: the point of the
    rule is to have Tapu charged BEFORE the
    wall is on the board."""
    assert _attachment([APPLIN], op_active) == "ACTIVE"


# ---------------------------------------------------------------------------
# What it does NOT do
# ---------------------------------------------------------------------------

def test_a_charged_tapu_is_not_overcharged():
    """Wood Hammer needs four effective energies and no more. With them already
    on the body the attachment is not spent on it -- the surplus rules above own
    that question."""
    assert _attachment([APPLIN], DWEBBLE, turn=4, tapu_energies=4) != "ACTIVE"


@pytest.mark.parametrize("bench", [[APPLIN], [CHIKORITA]])
def test_against_any_other_deck_nothing_moves(bench):
    """The band is Crustle-only on both arms, so an ordinary matchup keeps the
    answer it had: the bench attacker the ladder was already choosing."""
    assert _attachment(bench, ABRA) == bench[0]


def test_the_two_arms_do_not_stack():
    """One band, not two. A Chikorita on the bench AND the active Tapu in front
    of the wall must not add up to 42100, which would climb into the lethal
    floor (41000+) reserved for charges that take a prize today.

    Measured through the ladder rather than by reading the constant: a charge in
    the lethal band outranks Teal Dance, so if the arms stacked the ability
    would stop being offered ahead of the attachment on a board that has both.
    """
    obs = (Scenario(turn=4, step=12, first_player=1,
                    energy_played=False, supporter_played=True)
           .my_active(pk(TAPU))
           .my_bench(pk(CHIKORITA))
           .my_hand(m.Basic_Grass_Energy)
           .op_active(pk(DWEBBLE, energies=[G]))
           .op_zones(hand=5, deck=40, prizes=6)
           .menu_hand(with_attachment=True).build())
    # The spy goes on `main.score_option`, NOT on `ptcg.turn.scoring`: main.py
    # binds it with `from ... import`, which copies the reference, so patching
    # the module would leave the copy main.py actually calls untouched. It is
    # the same trap `AgentState` exists to avoid, seen from the test side.
    scores = []
    original = m.score_option

    def _spy(tc, o, score):
        out = original(tc, o, score)
        if (o.type == m.OptionType.ATTACH
                and getattr(o, "inPlayArea", None) == m.AreaType.ACTIVE
                and isinstance(out, (int, float))):
            scores.append(out)
        return out

    m.score_option = _spy
    try:
        m.agent(obs)
    finally:
        m.score_option = original
    assert scores, "el escenario dejo de ofrecer el adjunte al activo"
    assert max(scores) < 41000, (
        f"la carga del Tapu activo entro en la banda letal: {max(scores)}")
