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

It went unmodelled until now, and the way it hid is the interesting part. Before
this commit `grep -rn "Full Metal" main.py ptcg/` returned ONE line and it was a
COMMENT -- main.py:6767, written during the autopsy of a game lost 6-1 without
attacking from turn 7, saying in passing "Duraludon RESISTS Grass -30 and Full
Metal Lab takes another -30". Somebody diagnosed it, wrote it down beside the
rule it had just broken, and the damage model was never taught it. The id did
not even have a name in ptcg/cards/ids.py.

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

THE FIX, wave 1. `Full_Metal_Lab` (1244) is now named in ptcg/cards/ids.py, and
the -30 is applied in two places: the canonical `_our_effective_damage`, behind a
`full_metal_lab=False` keyword so that none of its 70 call sites had to change at
once, and the inline copy in main.py that feeds `plan.remain_hp` -- the line this
was measured on. On the board below the agent now predicts 30 where it used to
predict 0, which is exactly what the engine resolved.

The other FOUR copies of the Grass resistance arithmetic still do not know about
the stadium (main.py:6561/7401, ptcg/turn/supporters.py:969,
ptcg/turn/options/play.py:1553). They are wave 2, one at a time, each measured:
this is the same "one copy was fixed and the others kept lying" that produced
this defect in the first place, and fixing five copies blind would be the same
mistake in the other direction.
"""

import json
from pathlib import Path

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


def test_the_card_is_modelled_now():
    """It went unmodelled long enough to lose games; keep it named."""
    from ptcg.cards.ids import Full_Metal_Lab
    assert Full_Metal_Lab == FULL_METAL_LAB


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


def test_the_agent_now_predicts_what_the_engine_resolved():
    """The regression, run against the LIVE agent rather than frozen numbers.

    The first version of this test asserted on the fixture's own fields, which
    meant it could never have gone green from a code change -- it was reading
    the record of the bug, not the behaviour. This replays the board through
    main.py and reads the prediction the decision writes.
    """
    import sys
    root = Path(__file__).resolve().parents[1]
    for extra in (str(root), str(root / "utils")):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    import selfplay as sp

    board = _board()
    agent = sp.load_agent(str(root / "main.py"), "full_metal_lab_regression")
    sp._reset_si_aplica(agent)
    agent.agent(board["observation"])

    engine_left = board["finding"]["hp_after"]
    assert agent.AGENT_STATE.plan.remain_hp == engine_left == 30, (
        "the projection must land where the engine did; it used to say 0 "
        "(a knockout) and the body survived at 30")
