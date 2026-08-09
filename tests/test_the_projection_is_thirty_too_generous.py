"""The agent's own damage projection is 30 too generous, and the engine says so.

FOUND BY `utils/differential_oracle.py`, not by a lost game -- which is the
whole point of building it. The oracle plays complete games, reads the belief
the decision actually wrote (`AGENT_STATE.plan.remain_hp`) and compares it
against the board libcg produced one step later. No example-based test can find
this class of defect, because an example-based test asserts the same belief the
code has.

THE BOARD. `records`-shaped fixture harvested from a self-play game against
`deck/opponents/archaludon.csv`. Our Hydrapple ex attacks their Archaludon ex,
which sits at exactly 300 hp:

    the agent computes  base_damage = 330
    Archaludon resists Grass, so main.py:5193 subtracts 30  ->  damage = 300
    300 >= 300, so main.py:5505 writes  plan.remain_hp = 0   ("this kills")
    the engine resolves the attack and leaves the body at    30

The knockout does not happen. The agent spent its turn on an attack it believed
was lethal, and everything bought to set it up -- the gust, the retreat, the
promotion -- was paid for nothing. Against a body that resists, the arithmetic
lands exactly on the knockout boundary, which is why this deck is where it shows.

WHAT THE CAUSE IS NOT. Three hypotheses were tested against the data and all
three are dead, so nobody has to re-test them:

  * NOT a missing resistance. The resistance IS applied: at main.py:5505 the
    captured locals read `base=330 damage=300 resta=30 resiste=True` on all 24
    reproducing boards.
  * NOT the Fezandipiti exception at main.py:5189, which skips weakness and
    resistance entirely for that attacker. Fezandipiti is our attacker in ZERO
    of the 109 cases carrying this signature.
  * NOT a pending attachment being counted before it is made. The turn's
    attachment was already spent in 9 of the 24 boards.

WHAT IT LOOKS LIKE. `base_damage` itself is one Grass unit too high -- our
attacks scale at 30 per Grass, and across every opposing deck the oracle's
deltas are overwhelmingly NEGATIVE and land on multiples of 30 (-30, -60, -90).
The agent over-counts the Grass its own attack will have when it resolves. Which
unit is over-counted is the open question, and answering it means changing the
damage model, so it is deliberately not answered here.

This test is `xfail(strict=True)`: it states what SHOULD hold. The day the
projection is fixed it turns green and pytest fails the run for an unexpected
pass, which is the reminder to delete the xfail and keep the assertion.
"""

import json
from pathlib import Path

import pytest

FIXTURE = (Path(__file__).parent / "fixtures"
           / "archaludon_the_projection_is_thirty_too_generous.json")


def _board():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_fixture_is_the_board_the_oracle_found():
    """Guard the evidence itself: these numbers are the finding."""
    finding = _board()["finding"]
    assert finding["kind"] == "PHANTOM_KO"
    assert finding["hp_before"] == 300, "Archaludon ex at exactly its 300 hp"
    assert finding["predicted_remain_hp"] == 0, "the agent believed it was lethal"
    assert finding["hp_after"] == 30, "the engine left it alive at 30"


def test_the_resistance_is_not_the_culprit():
    """Pinned so the dead hypothesis is not re-investigated.

    The gap is 30 and Archaludon resists Grass by 30, which makes "the
    resistance is missing" the obvious first guess. It is wrong: tracing the
    locals at main.py:5505 shows base=330 -> damage=300, the 30 already taken
    off. The projection is 30 too generous BEFORE the resistance is applied.
    """
    finding = _board()["finding"]
    engine_damage = finding["hp_before"] - finding["hp_after"]
    agent_damage = finding["hp_before"] - finding["predicted_remain_hp"]
    assert agent_damage - engine_damage == 30
    assert engine_damage == 270, "engine: base 300 minus 30 resistance"
    assert agent_damage == 300, "agent: base 330 minus the SAME 30 resistance"


@pytest.mark.xfail(strict=True,
                   reason="open: base_damage is one Grass unit (30) too high; "
                          "fixing it changes the damage model and needs a gate")
def test_the_projection_matches_what_the_engine_resolves():
    """What should hold: a predicted knockout is a knockout.

    Delete the xfail when the projection is fixed.
    """
    finding = _board()["finding"]
    predicted_ko = finding["predicted_remain_hp"] <= 0
    actual_ko = finding["hp_after"] is None or finding["hp_after"] <= 0
    assert predicted_ko == actual_ko
