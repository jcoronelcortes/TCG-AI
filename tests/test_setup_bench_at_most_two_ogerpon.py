"""The setup bench also obeys the "a maximum of two Ogerpon ex" cap.

Scenario (`log/89629887.json`, setup, episode 89629887, LOST vs Crustle +
Cornerstone Mask Ogerpon ex). The opening hand:

    hand   **Teal Mask Ogerpon ex x3**, Tapu Bulu, Meowth ex, Lana's Aid,
           Lillie's Determination, Ultra Ball

Tapu Bulu went to the active spot -- correct, it is the reference non-ex
attacker -- and then the three Teal Mask Ogerpon ex went onto the **bench**. From
turn 2 the opposing active was a **Cornerstone Mask Ogerpon ex**: its Cornerstone
Stance cancels the damage of attacks by Pokemon **with an ability**, which is
every ex of ours. The three bodies did **0** for the rest of the game, they were
**6 prizes** parked on the bench, they left a single free slot for the pieces
that DO damage in that matchup (the Chikorita->Bayleef->Meganium line, Dipplin)
and, with three ex on the field, the `_block_4th_ex` veto of the PLAY shut the
door on any further ex -- the Meowth ex that stayed in hand included.

Cause -- the cap existed, but not at setup. The PLAY branch already refuses a
third copy (`field_counts[card.id] >= 2 -> SCORE_VETO` vs Crustle/Cornerstone,
and only 20500 with a Grass in hand for any other deck), yet
`SETUP_BENCH_POKEMON` scored **every** copy the same (6) and the setup takes
every option scoring >= 0 up to `maxCount`. The three copies were tied at 6, so
the three went down.

The cap is **deck-agnostic** because the setup is blind: the opponent has not
revealed their active, so neither `op_is_crustle_deck` nor
`op_is_cornerstone_deck` can be on yet. Holding the third copy in hand costs
nothing -- it comes down later if the matchup allows it -- while a benched body
can never be taken back.

`field_counts` is of no use here: at setup the bench is empty and the active is
placed FACE DOWN (`my_state.active` holds a None and the tracking skips it), so
it counts 0 for every option. What is counted is the ordinal of the copy inside
the hand plus `AGENT_STATE.setup_active_id`, which the SETUP_ACTIVE decision
writes down in `finalize.py` -- the only moment at which the starter is known.
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_cornerstone_t0_setup_at_most_two_ogerpon.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
CHIKORITA = m.Chikorita


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.AGENT_STATE.setup_active_id = None
    yield
    m._init_cards_tracking()
    m.AGENT_STATE.setup_active_id = None


def _sequence():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["sequence"])


def _bench_ids(seq):
    """Replays the two setup decisions and returns what goes onto the bench."""
    m.agent(seq[0]["observation"])              # the starting active
    obs = seq[1]["observation"]                 # the initial bench
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    return [me["hand"][obs["select"]["option"][i]["index"]]["id"]
            for i in result]


def test_only_two_ogerpon_reach_the_setup_bench():
    ids = _bench_ids(_sequence())
    assert ids.count(OGERPON) == 2, (
        f"en el setup bajan como maximo DOS Teal Mask Ogerpon ex: el tercero "
        f"es un cuerpo mudo frente al muro y ocupa el sitio de la linea "
        f"Meganium; obtuvo {ids}")


def test_the_third_ogerpon_stays_in_hand():
    # The copy is not lost: the PLAY branch puts it down later if the matchup
    # allows it and there is room. What cannot be undone is a benched body.
    seq = _sequence()
    ids = _bench_ids(seq)
    obs = seq[1]["observation"]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    in_hand = sum(1 for c in me["hand"] if c["id"] == OGERPON)
    assert in_hand - ids.count(OGERPON) == 1, (
        f"la tercera copia se conserva en mano; de {in_hand} en mano bajaron "
        f"{ids.count(OGERPON)}")


def test_the_face_down_active_ogerpon_counts_towards_the_cap():
    # With no Tapu Bulu in hand the starter is a Teal Mask Ogerpon ex, and it is
    # placed face down. If the cap only looked at the bench, two more would go
    # down and there would be THREE in play: `setup_active_id` closes that hole.
    seq = _sequence()
    act = seq[0]["observation"]
    me = act["current"]["players"][act["current"]["yourIndex"]]
    for c in me["hand"]:
        if c["id"] == TAPU:
            c["id"] = OGERPON
    ids = _bench_ids(seq)
    assert ids.count(OGERPON) == 1, (
        f"con un Ogerpon ex de activo solo cabe UNO mas en la banca; "
        f"obtuvo {ids}")


def test_two_copies_still_go_down():
    # Boundary: the cap is TWO, it does not become "only one".
    seq = _sequence()
    obs = seq[1]["observation"]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    me["hand"][4]["id"] = CHIKORITA
    ids = _bench_ids(seq)
    assert ids.count(OGERPON) == 2, (
        f"con dos copias en mano bajan las dos; obtuvo {ids}")


def test_the_starting_active_is_still_tapu_bulu():
    # Control: the cap touches the BENCH, not the choice of starter. Tapu Bulu
    # keeps being the active over the three Ogerpon ex.
    seq = _sequence()
    obs = seq[0]["observation"]
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    chosen = me["hand"][obs["select"]["option"][result[0]]["index"]]["id"]
    assert chosen == TAPU, (
        f"el activo inicial sigue siendo Tapu Bulu; obtuvo id {chosen}")
