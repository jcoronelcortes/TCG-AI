"""Full Metal Lab takes 30 off our attacks and the damage model has never heard of it.

FOUND BY `utils/differential_oracle.py`, not by a lost game -- which is the whole
point of having built it. The oracle plays complete games, reads the belief the
decision actually wrote (`AGENT_STATE.plan.remain_hp`) and compares it against
the board libcg produced one step later. No example-based test can find this
class of defect, because such a test asserts the same belief the code has.

THE CARD. `Full Metal Lab` (id 1244), the Archaludon deck's stadium:

    "{M} Pokemon (both yours and your opponent's) take 30 less damage from
     attacks from the opponent's Pokemon (AFTER applying Weakness and
     Resistance)."

Archaludon ex and Duraludon are Metal. While that stadium is on the field every
attack we make into them lands 30 short of what the agent projected.

It is not modelled anywhere. `grep -rn "Full Metal" main.py ptcg/` returns ONE
line and it is a comment -- main.py:6767, written during the autopsy of a game
that was lost 6-1 without attacking from turn 7, which says in passing
"Duraludon RESISTS Grass -30 and Full Metal Lab takes another -30". Somebody
diagnosed it, wrote it down next to the rule it had just broken, and the damage
model was never taught it. The id does not even have a name in ptcg/cards/ids.py.

THE MEASUREMENT. 300 games against `deck/opponents/archaludon.csv`, every judged
attack on a Grass-resisting body, split by which stadium was in play:

    stadium in play        agent - engine     n
    Forest of Vitality     +0  (exact)        106
    no stadium             +0  (exact)          7
    Full Metal Lab         +30 (too generous)  51

The split is total: zero drifting attacks under our stadium, zero exact attacks
under theirs. Against decks that do not play it the agent is 91-97 % exact
(dragapult 91 %, marnie 94 %, hops 97 % -- and hops' own Grass-RESISTING bodies
are in that 97 %, which is what rules out the resistance path being at fault).

THE COST. The gap lands exactly on the knockout boundary, because the resistance
has already brought the number down to the target's hp: the agent computes
base 330 -> 300 after resistance, the body sits at 300, so main.py:5505 writes
`plan.remain_hp = 0` -- "this kills" -- and the engine leaves it at 30. The turn
is spent on an attack that does not close, and so is everything bought to set it
up: the gust, the retreat, the promotion.

FIVE DEAD HYPOTHESES, pinned as dead so nobody re-tests them:

  * NOT a missing resistance -- the obvious guess, since the gap is 30 and so is
    the resistance. Tracing the locals at main.py:5505 reads
    `base=330 damage=300 resta=30 resiste=True` on all 24 reproducing boards.
  * NOT a resistance of 60 rather than 30 -- then every attack into a resisting
    body would drift, and 55-61 % of them are exact.
  * NOT the Fezandipiti exception at main.py:5189, which skips weakness and
    resistance for that attacker: Fezandipiti attacks in ZERO of the 109 cases.
  * NOT an attribution error in the oracle -- the body the plan targeted IS the
    body that was hit, 118 of 118 in the exact group and 92 of 92 in the drifting
    one.
  * NOT `Hero's Cape` on the target: it is present in 35 % of the exact group and
    28 % of the drifting one, i.e. not enriched at all.

THE FIX IS NOT HERE, on purpose. The -30 of the Grass resistance is hardcoded in
SIX places (ptcg/calc/damage.py:250, main.py:5192/6561/7401,
ptcg/turn/supporters.py:969, ptcg/turn/options/play.py:1553) and
`_our_effective_damage` has 70 call sites, so where this reduction belongs -- and
how many of those six copies have to learn it -- is a design decision with a
self-play gate attached, not a one-line patch.
"""

import json
from pathlib import Path

import pytest

FIXTURE = (Path(__file__).parent / "fixtures"
           / "archaludon_the_projection_is_thirty_too_generous.json")

FULL_METAL_LAB = 1244


def _board():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_fixture_is_the_board_the_oracle_found():
    """Guard the evidence itself: these numbers are the finding."""
    finding = _board()["finding"]
    assert finding["kind"] == "PHANTOM_KO"
    assert finding["hp_before"] == 300, "Archaludon ex at exactly its 300 hp"
    assert finding["predicted_remain_hp"] == 0, "the agent believed it was lethal"
    assert finding["hp_after"] == 30, "the engine left it alive at 30"


def test_their_stadium_is_on_the_field_on_this_board():
    """The cause, on the board itself: Full Metal Lab is what takes the 30."""
    stadium = _board()["observation"]["current"].get("stadium") or []
    assert stadium, "the board is not stadium-less"
    assert stadium[0]["id"] == FULL_METAL_LAB


def test_the_card_is_not_modelled_anywhere():
    """The defect in one assertion: the id appears in no source file.

    When Full Metal Lab is finally modelled this test fails, which is the point
    -- it is the reminder that the rest of this file is now stale.
    """
    root = Path(__file__).resolve().parents[1]
    sources = [root / "main.py"] + sorted((root / "ptcg").rglob("*.py"))
    naming = [p for p in sources if str(FULL_METAL_LAB) in p.read_text(encoding="utf-8")]
    assert not naming, (
        f"Full Metal Lab ({FULL_METAL_LAB}) is now named in "
        f"{[p.name for p in naming]} -- if it is modelled, delete this test and "
        f"the xfail below")


def test_the_resistance_is_not_the_culprit():
    """Pinned so the dead hypothesis is not re-investigated.

    The gap is 30 and Archaludon resists Grass by 30, which makes "the
    resistance is missing" the obvious first guess. It is wrong: the 30 is
    already off. The stadium takes a SECOND 30, after weakness and resistance,
    exactly as the card says.
    """
    finding = _board()["finding"]
    engine_damage = finding["hp_before"] - finding["hp_after"]
    agent_damage = finding["hp_before"] - finding["predicted_remain_hp"]
    assert agent_damage - engine_damage == 30
    assert agent_damage == 300, "agent: base 330, minus 30 resistance"
    assert engine_damage == 270, "engine: the same 300, minus 30 more of stadium"


@pytest.mark.xfail(strict=True,
                   reason="open: Full Metal Lab (1244) is unmodelled; where the "
                          "-30 belongs across six hardcoded copies is a design "
                          "decision with a self-play gate")
def test_the_projection_matches_what_the_engine_resolves():
    """What should hold: a predicted knockout is a knockout.

    Delete the xfail when the stadium is modelled.
    """
    finding = _board()["finding"]
    predicted_ko = finding["predicted_remain_hp"] <= 0
    actual_ko = finding["hp_after"] is None or finding["hp_after"] <= 0
    assert predicted_ko == actual_ko
