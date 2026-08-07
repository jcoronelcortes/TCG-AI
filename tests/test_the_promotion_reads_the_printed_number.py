"""At their match point the promotion believed a 30 that the engine resolves at 210.

Scenario (self-play mirror, game 90 turn 17; the board is
`tests/fixtures/mirror_t17_the_promotion_reads_the_printed_number.json`, dumped
by the promotion census written up in `docs/history/menu-order-ties.md`):

    US (3 prizes left)                THEM (2 prizes left)
    bench  Meganium 160/160, 0        active  Hydrapple ex 330/330, 2 Grass
           Fezandipiti ex 210/210, 0  bench   Hydrapple ex (2), Ogerpon ex (2),
           Teal Mask Ogerpon ex 210,6         Meowth ex
           Applin 40/40, 0
           Applin 40/40, 0

We retreat, and this menu takes the front seat. They are TWO prizes from the
game, so any ex we promote IS the game. The agent promoted the Teal Mask Ogerpon
ex -- charged, and worth exactly the two prizes they need.

WHY IT FIRED, and it is not the promotion rules being wrong. The rules that would
have stopped it are all there and all measured: the doomed penalty, the "hand
over the fewest prizes" fallback, and an explicit MATCH POINT VETO whose sentence
is this board ("bringing up a doomed body is not a bad trade: it is losing the
game"). Every one of them is gated on whether the candidate SURVIVES their
attack, and that question is asked of `_op_active_attack_damage_to` without
`scaled=True`:

    candidate               hp    blind   scaled
    Meganium               160       30      210
    Fezandipiti ex         210       30      210
    Teal Mask Ogerpon ex   210       30      210
    Applin                  40       30      210

Syrup Storm's PRINTED damage is 30; it scales with the Grass across their whole
field and the engine resolves it at 210 here. Read blind, **every candidate
survives**, so nobody is doomed, no prize fallback runs, the veto's own guard is
satisfied by phantom survivors, and the choice is settled by bonuses written for
a board where the front body lives.

`ptcg/cards/op_scaling.py` is opt-in on purpose -- turning the true number on at
all 42 call sites measured negative three times out of three, because the
thresholds downstream were fitted to the blind one. That argument is about
CALIBRATION, and at their match point there is nothing left to calibrate: the
body in front either survives or the game ends. So the projection stops being
opt-in exactly there, and the rules that were already written do the rest.
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
            / "mirror_t17_the_promotion_reads_the_printed_number.json")

MEGANIUM = m.Meganium
FEZANDIPITI = m.Fezandipiti_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
APPLIN = m.Applin


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _promotion():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return copy.deepcopy(data["sequence"][1]["observation"])


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _theirs(obs):
    cur = obs["current"]
    return cur["players"][1 - cur["yourIndex"]]


def _promoted(obs):
    choice = m.agent(obs)
    index = obs["select"]["option"][choice[0]]["index"]
    return _mine(obs)["bench"][index]


def _prizes(pokemon_dict):
    """Two for an ex, one otherwise -- read off the same table the agent uses."""
    return 2 if pokemon_dict["id"] in m.OUR_EX_IDS else 1


def test_the_board_is_the_one_described():
    obs = _promotion()
    bench = _mine(obs)["bench"]
    assert [b["id"] for b in bench] == [MEGANIUM, FEZANDIPITI, OGERPON,
                                        APPLIN, APPLIN]
    assert len(_theirs(obs)["prize"]) == 2                  # their match point
    assert len(_theirs(obs)["active"][0]["energies"]) == 2   # Syrup Storm prints 30


def test_the_body_that_takes_the_front_does_not_end_the_game():
    """The whole finding: at their match point the front seat cannot be worth
    their whole pile while a cheaper body is on the bench."""
    promoted = _promoted(_promotion())
    assert _prizes(promoted) < 2


def test_a_cheaper_candidate_really_was_available():
    """A guard on the assertion above: it means nothing if every candidate were
    an ex."""
    obs = _promotion()
    assert any(_prizes(b) == 1 for b in _mine(obs)["bench"])


def test_with_their_pile_at_four_the_ordinary_promotion_returns():
    """The boundary: away from match point their knockout does not end the game,
    the calibrated rules keep the board, and the charged body goes up."""
    obs = _promotion()
    _theirs(obs)["prize"] = [None] * 4
    assert _promoted(obs)["id"] == OGERPON


def test_it_is_the_SCALE_that_decides_and_not_the_printed_number():
    """The mechanism, isolated. Syrup Storm counts the Grass across their whole
    field: strip their bench of energy and the same attack really does land for
    little, the candidates really do survive, and the ex is a fine promotion
    again. If this test ever passes for the wrong reason, the one above it and
    this one disagree."""
    obs = _promotion()
    for body in _theirs(obs)["bench"]:
        if body is not None:
            body["energies"] = []
            body["energyCards"] = []
    _theirs(obs)["active"][0]["energies"] = []
    _theirs(obs)["active"][0]["energyCards"] = []
    assert _promoted(obs)["id"] == OGERPON
