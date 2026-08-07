"""The Grass goes to the ACTIVE when that is the knockout, even with a Tapu on the bench.

THE BOARD (`utils/wall_probe.py` dump `seco_019`, turn 14 vs crustle_wall_6, now
frozen as a fixture). Our active is a **Meowth ex at 0 energy** -- retreat cost 1,
no attack of its own -- so the menu offers no RETREAT at all. On the bench sits a
**Tapu Bulu with four Grass**: Wood Hammer 220. In front, a **Crustle 170/170**.
One Basic Grass in hand and the turn's attachment unspent.

The line is four steps and it takes a prize: Grass onto the ACTIVE, retreat
(now payable), promote the Tapu, Wood Hammer. The agent instead attached to a
BENCHED DIPPLIN AT ZERO ENERGY and ended the turn.

WHY, AND IT IS NOT THE DETECTOR. `_attach_enable_retreat_ko` saw the whole thing
-- `_grass_unlocks_active_retreat` returns (True, False) on this board -- and its
own comment fixes its band at **41000**, "a LETHAL line for this turn: above Teal
Dance (31500-31600) and the bench charges (~30000)". It never got there. The
`elif` chain tested `_tapu_sac_enable_retreat` FIRST, which is the older, narrower
version of the same idea (Tapu Bulu with four Grass -- that is, the whole plan of
the Crustle matchup), and that branch scores **24000**. A routine bench charge
scores 31000. So on precisely the boards the special case covers, the lethal line
was outbid by a charge onto a body that does nothing.

The general rule now goes first. When it stays quiet the special case still
answers at 24000, which is what it was calibrated for -- "above bench
DEVELOPMENT", which is not the same as above a bench CHARGE, and that gap is the
whole bug.

MEASURED, and the result is NEUTRAL. Two arms of 3000 games each per list,
swapping this one file on disk (selfplay's --base swaps main.py only, and this
change lives in `ptcg/`):

    crustle_wall_6   candidate 56.5% [54.7-58.2]   base 56.5% [54.8-58.3]
    crustle_wall_2   candidate 75.2% [73.7-76.7]   base 74.7% [73.1-76.3]

Golden corpus: 0 flips. The frequency explains both numbers -- a census over
8,478 decisions against crustle_wall_6 finds the stuck active one Grass from its
retreat cost on **6.3%** of decisions, a bench knockout available on 0.07%, and
the Tapu subset where the shadowing happens on **0.06%**. Against crustle_wall_2,
0.28%.

IT IS KEPT ANYWAY, under the rule the project already has for this: neutral gets
reverted unless it corrects a value that was demonstrably wrong. A rule receiving
24000 where its own documentation specifies 41000, and losing to a charge it was
written to outrank, is a wrong value and not a preference. The agent was
declining a knockout it had already detected.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from cg.api import AreaType, OptionType  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_wall_stuck_active_tapu_ready.json")

CRUSTLE_GRASS = 345
WOOD_HAMMER = 1326


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)


def _obs():
    return copy.deepcopy(json.loads(_FIXTURE.read_text(encoding="utf-8"))
                         ["observation"])


def _sides(obs):
    current = m.to_observation_class(obs).current
    return (current.players[current.yourIndex],
            current.players[1 - current.yourIndex])


# ---------------------------------------------------------------------------
# 1. The board is the one the tool dumped
# ---------------------------------------------------------------------------

def test_the_active_is_stuck_and_the_answer_is_on_the_bench():
    obs = _obs()
    mine, theirs = _sides(obs)
    active = mine.active[0]

    assert active.id == m.Meowth_ex and not active.energies
    assert m.RETREAT_COST.get(active.id) == 1, "one Grass is the whole fee"
    assert not any(o.get("type") == int(OptionType.RETREAT)
                   for o in obs["select"]["option"]), (
        "sin energia no hay RETREAT en el menu: por eso la carga es el desbloqueo")

    tapu = next(b for b in mine.bench if b and b.id == m.Tapu_Bulu)
    assert len(tapu.energies) == 4, "Wood Hammer cuesta 4"

    wall = theirs.active[0]
    assert wall.id == CRUSTLE_GRASS and wall.hp == 170
    assert m._our_effective_damage(tapu, wall, 220) >= wall.hp, (
        "el relevo remata: 220 sobre 170")


def test_the_grass_in_hand_is_the_only_one_and_the_attachment_is_free():
    obs = _obs()
    mine, _ = _sides(obs)
    assert sum(1 for c in mine.hand if c.id == m.Basic_Grass_Energy) == 1
    assert not m.to_observation_class(obs).current.energyAttached


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_energy_goes_to_the_active_that_has_to_retreat():
    obs = _obs()
    choice = m.agent(obs)
    picked = obs["select"]["option"][choice[0]]
    assert picked["type"] == int(OptionType.ATTACH), picked
    assert picked["inPlayArea"] == int(AreaType.ACTIVE), (
        "la energia va al ACTIVO: es lo que paga la retirada hacia el KO")


def test_the_detector_of_the_line_was_never_the_problem():
    """`_grass_unlocks_active_retreat` reports the knockout on this board. What
    failed was the band the answer got, which is why the fix is an ordering."""
    obs = _obs()
    m.agent(obs)
    mine, theirs = _sides(obs)
    total_grass = sum(
        len(p.energies or []) for p in
        [x for x in (mine.active or []) if x] + [x for x in (mine.bench or []) if x])
    bench_count = sum(1 for b in (mine.bench or []) if b)

    unlock_ko, unlock_chip = m._grass_unlocks_active_retreat(
        mine, theirs, m.AGENT_STATE.meganium_in_play, total_grass, bench_count,
        False, False, budget=1)
    assert unlock_ko is True and unlock_chip is False
    assert m._bench_attacker_can_ko(
        mine, theirs.active[0], m.AGENT_STATE.meganium_in_play, total_grass,
        bench_count, max(0, total_grass - 1), False) is True


def test_the_special_case_still_answers_when_the_general_rule_is_quiet():
    """The Tapu branch is not dead code: it keeps its 24000 for the boards the
    general detector does not claim. Asserted on the source ordering rather than
    on a board, because constructing one where they disagree means defeating
    `_grass_unlocks_active_retreat`'s own guards -- and the ordering is the
    invariant that matters: general first, special case second."""
    source = (ROOT / "ptcg" / "turn" / "options" / "attach.py").read_text()
    general = source.index("elif _attach_enable_retreat_ko:")
    special = source.index("elif _tapu_sac_enable_retreat:")
    assert general < special, (
        "el caso especial del Tapu no puede volver a tapar la regla general")
    assert "score = 41000" in source and "score = 24000" in source
