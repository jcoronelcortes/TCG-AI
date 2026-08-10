"""The oracle scored a prediction about one body against a different one.

`judge()` took the plan's `remain_hp` and compared it with whichever single
opposing body had lost hp that step. `AGENT_STATE.plan.target` was in the dict
and nothing read it. The file's own docstring called that out --- "without a
reliable map from `plan.target` to a board serial, attributing a prediction to
one of several damaged bodies would invent findings" --- and then invented them
anyway for the single-body case, which is the common one.

WHAT IT COST. The night of 9-10 August reported PHANTOM_KO as the headline
finding: 110-166 wrong boards per thousand games, concentrated on the Crustle
family, written up as the agent believing it kills a wall that survives.

Of the 611 dumped PHANTOM_KO, **545 --- 89.2 % --- had the plan pointing at a
BENCHED body while the attack landed on the active.** Three taken at random
predicted leaving a 70 hp body at -70 and were scored against a body of 150 or
300 that had just taken 100. The agent was right: *if I gust that, it falls*.
It then did not gust, attacked the wall in front, and the wall survived.

And it explains why Crustle led every table. Against a wall the best prize
route is almost always a gust onto their bench, so that is where the plan
points and that is where the misattribution lives. The concentration was the
detector's, not the agent's.

Re-measured on crustle_wall_9 at n=1000 with the target checked: PHANTOM_KO
124 -> 17, and the deck's residue 4.92 % -> 1.58 %.

A prediction is comparable only against the body it was made for. What is left
over is COUNTED (`skipped_other_target`), never silently dropped: this file's
rule is that a blind spot is a number in the output rather than a silence.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from differential_oracle import judge, planned_serial


def obs_con(activo, banca, asiento=1):
    jugadores = [None, None]
    jugadores[asiento] = {"active": [activo] if activo else [],
                          "bench": list(banca)}
    jugadores[1 - asiento] = {"active": [], "bench": []}
    return {"current": {"players": jugadores}}


def cuerpo(serial, hp):
    return {"serial": serial, "hp": hp, "maxHp": hp}


# --- planned_serial: 0 is their active, 1 and up their bench ---------------

def test_target_zero_is_their_active():
    o = obs_con(cuerpo(10, 150), [cuerpo(20, 70), cuerpo(30, 90)])
    assert planned_serial(o, 1, 0) == 10


def test_target_one_and_up_walk_their_bench():
    o = obs_con(cuerpo(10, 150), [cuerpo(20, 70), cuerpo(30, 90)])
    assert planned_serial(o, 1, 1) == 20
    assert planned_serial(o, 1, 2) == 30


@pytest.mark.parametrize("target", [-1, 3, 99, None])
def test_a_target_that_resolves_to_nothing_is_None(target):
    """None means "cannot attribute", and the caller keeps the old behaviour."""
    o = obs_con(cuerpo(10, 150), [cuerpo(20, 70)])
    assert planned_serial(o, 1, target) is None


# --- judge: the prediction only counts against its own body ----------------

def test_the_real_case_is_no_longer_a_finding():
    """The board that produced 545 of the 611: a gust that did not happen.

    The plan is about their 70 hp benched body and predicts leaving it at -70.
    The attack lands on the 150 hp active for 100. Before the fix this was a
    PHANTOM_KO; the agent had said nothing wrong.
    """
    before = {80: 150, 20: 70}
    after = {80: 50, 20: 70}
    plan = {"attacker": 0, "target": 1, "attack_index": 0, "remain_hp": -70}
    finding, skip = judge(before, after, plan, 0, target_serial=20)
    assert finding is None
    assert skip == "target"


def test_a_phantom_on_the_planned_body_is_still_reported():
    """Sensitivity: the fix must not buy its quiet by going blind.

    Same prediction, and this time the attack DID land on the body the plan was
    about. That is a real phantom and it has to survive.
    """
    before = {20: 70}
    after = {20: 30}
    plan = {"attacker": 0, "target": 1, "attack_index": 0, "remain_hp": -70}
    finding, skip = judge(before, after, plan, 0, target_serial=20)
    assert skip is False
    assert finding["kind"] == "PHANTOM_KO"
    assert finding["serial"] == 20


def test_a_missed_ko_on_the_planned_body_is_still_reported():
    before = {20: 70}
    after = {}
    plan = {"attacker": 0, "target": 1, "attack_index": 0, "remain_hp": 30}
    finding, skip = judge(before, after, plan, 0, target_serial=20)
    assert skip is False
    assert finding["kind"] == "MISSED_KO"


def test_without_a_target_it_behaves_as_it_always_did():
    """`None` is the escape hatch the self-test uses; it must not change."""
    before = {80: 150}
    after = {80: 50}
    plan = {"attacker": 0, "target": 1, "attack_index": 0, "remain_hp": -70}
    finding, skip = judge(before, after, plan, 0, target_serial=None)
    assert skip is False
    assert finding["kind"] == "PHANTOM_KO"


def test_the_skipped_ones_are_counted_and_not_dropped():
    """The rule of this file: a blind spot is a number, not a silence."""
    import differential_oracle as oracle
    fuente = Path(oracle.__file__).read_text()
    assert "skipped_other_target" in fuente
    assert "OTRO cuerpo" in fuente, "el descarte tiene que salir en el informe"
