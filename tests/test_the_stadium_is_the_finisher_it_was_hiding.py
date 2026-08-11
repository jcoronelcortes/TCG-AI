"""The stadium the winning finisher never subtracted, and the game it cost.

Scenario (`records/registro_007_pasos_063_hasta_063.json`, step 63, turn 7 vs
Archaludon, episode 91627381 -- LOST):

    US (5 prizes)                          OPPONENT (4 prizes)
    active  Hydrapple ex 330, 2 {G}        active  **Duraludon 130/130**, 4 {M}
    bench   Teal Mask Ogerpon ex 2 {G},    bench   **EMPTY**
            Teal Mask Ogerpon ex 1 {G},    stadium **Full Metal Lab** (theirs)
            Chikorita
    hand    Tapu Bulu, Meowth ex, Dipplin, Xerosic's Machinations,
            **Night Stretcher**, Bayleef, **Forest of Vitality**
    discard **three Basic Grass Energy**   (stadium slot and Supporter free)

Their bench is empty, so knocking out that Duraludon ENDS THE GAME. The agent
attacked at once and played nothing else. The engine logged the answer:

    {'attackId': 195, 'cardId': 150, 'playerIndex': 1, ...}
    {'cardId': 169, 'serial': 17, 'type': 16, 'value': **-120**}

Duraludon survived at 10 HP and the game was lost from there.

THE ARITHMETIC. Syrup Storm counts every Grass on OUR side: 2+2+1 = 5, so
30+30x5 = 180. Duraludon resists Grass (-30) -> 150, and Full Metal Lab takes 30
more off a {M} body AFTER weakness and resistance -> **120**. The agent read
150 >= 130.

THE CAUSE, and it is not that the model had never heard of the card. It had:
`_our_effective_damage` grew a `full_metal_lab` keyword the morning the
differential oracle found the stadium. It grew it with a **default of False**,
expressly so that the ~70 call sites would not have to change -- and none of
them ever did. Zero of 69 passed it. The four inline copies of the arithmetic
(the turn plan, Syrup Storm's can-KO, the gust's price, Do the Wave) carried the
whole fix while every finisher went on over-reading by 30.

WHY ONE WRONG NUMBER COST THREE PLAYS. `_active_already_kos` (main.py) fed the
over-read into `_active_attack_wins_now`, which with an empty opposing bench is
the WINNING FINISHER: tier `_TIER_WIN_ATTACK`, score 99000, absolute priority.
That tier does not outrank the rest of the menu, it EMPTIES it. So the Bayleef
was not played, the Night Stretcher was not played and the stadium was not
replaced -- not because any of those branches decided against them, but because
none of them was ever asked.

TWO CARDS IN THAT HAND WON ON THE SPOT, and the over-read hid both:

    Forest of Vitality  replace the stadium -> 180-30      = 150 >= 130
    Night Stretcher     recover one of the three Grass in the discard,
                        attach it -> 30+30x6 = 210-30-30   = 150 >= 130

The second one wins WITH Full Metal Lab still up, which is why the fix has to
reach `_extra_energy_enables_ko` too and not only the finisher.

THE FIX. `full_metal_lab` defaults to `None` = ask the board
(`AGENT_STATE.full_metal_lab_in_play`, which `agent()` writes from the stadium
on every observation). True/False still force the answer, for the tests and for
a projector asking what the damage would be under ANOTHER stadium. The four
inline copies are left alone: none of them calls the canonical function, so
there is no second subtraction -- verified by the -120 asserted below.

WHAT THIS TEST IS NOT. It does not assert "play Forest of Vitality" as a rule.
It asserts that the agent does not spend its one turn on an attack it has been
told is lethal when it is not, and that it takes one of the two routes that
really close the game. The record's board offers both; the test accepts either.
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

from ptcg.calc.damage import _our_effective_damage

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_t7_the_stadium_is_the_finisher_step63.json")

SEAT = 1                       # our seat in the record
DURALUDON = 169
HYDRAPPLE_EX = 150
FOREST = 1261
NIGHT_STRETCHER = 1097
SYRUP_STORM = 195


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _option_index(obs, predicate):
    for i, opt in enumerate(obs["select"]["option"]):
        if predicate(i, opt):
            return i
    return None


def _hand_play(obs, card_id):
    hand = obs["current"]["players"][SEAT]["hand"]
    return _option_index(
        obs, lambda i, o: (o.get("type") == 7
                           and hand[o["index"]]["id"] == card_id))


# ---------------------------------------------------------------------------
# 1. The board is the one the record lost on
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_lone_duraludon_under_their_own_stadium():
    obs = _obs()
    cur = obs["current"]
    op = cur["players"][1 - SEAT]

    assert cur["stadium"][0]["id"] == m.Full_Metal_Lab
    assert not cur["stadiumPlayed"], "the stadium slot is free this turn"
    assert op["active"][0]["id"] == DURALUDON
    assert op["active"][0]["hp"] == 130
    assert op["bench"] == [], "an empty bench: the knockout ends the game"

    me = cur["players"][SEAT]
    assert me["active"][0]["id"] == HYDRAPPLE_EX
    hand = [c["id"] for c in me["hand"]]
    assert FOREST in hand and NIGHT_STRETCHER in hand
    assert sum(1 for c in me["discard"] if c["id"] == m.Basic_Grass_Energy) == 3
    assert not any(c["id"] == m.Basic_Grass_Energy for c in me["hand"]), (
        "no Grass in hand: the Night Stretcher is the only way to one more")


def test_the_five_grass_on_our_side_make_syrup_storm_one_hundred_and_eighty():
    obs = _obs()
    me = obs["current"]["players"][SEAT]
    grass = sum(len(p["energies"]) for p in me["active"] + me["bench"])
    assert grass == 5
    assert 30 + 30 * grass == 180


# ---------------------------------------------------------------------------
# 2. The number itself: 120, which is what the engine logged
# ---------------------------------------------------------------------------

class _Body:
    def __init__(self, card_id, hp=130):
        self.id = card_id
        self.hp = hp
        self.maxHp = hp
        self.energies = []


def test_the_stadium_takes_the_second_thirty_and_the_attack_lands_at_120():
    """-30 resistance, -30 stadium, and 120 is the engine's own number."""
    m.AGENT_STATE.full_metal_lab_in_play = True
    assert _our_effective_damage(_Body(HYDRAPPLE_EX, 330),
                                 _Body(DURALUDON), 180) == 120
    assert 130 - 120 == 10, "the 10 HP the record left it at"


def test_and_it_is_subtracted_once_not_twice():
    """The four inline copies of the arithmetic still exist; none of them feeds
    this function, so the board's flag cannot be applied twice."""
    m.AGENT_STATE.full_metal_lab_in_play = True
    assert _our_effective_damage(_Body(HYDRAPPLE_EX, 330),
                                 _Body(DURALUDON), 180,
                                 full_metal_lab=True) == 120


def test_either_of_the_two_routes_reaches_the_hundred_and_thirty():
    """Both cards in that hand close the game, by different halves of the sum."""
    m.AGENT_STATE.full_metal_lab_in_play = False       # Forest of Vitality
    assert _our_effective_damage(_Body(HYDRAPPLE_EX, 330),
                                 _Body(DURALUDON), 180) == 150
    m.AGENT_STATE.full_metal_lab_in_play = True        # Night Stretcher
    assert _our_effective_damage(_Body(HYDRAPPLE_EX, 330),
                                 _Body(DURALUDON), 210) == 150


# ---------------------------------------------------------------------------
# 3. The decision: the turn is not spent on an attack that does not finish
# ---------------------------------------------------------------------------

def test_step63_does_not_attack_into_the_stadium():
    obs = _obs()
    attack = _option_index(obs, lambda i, o: o.get("attackId") == SYRUP_STORM)
    assert attack is not None, "the attack IS on the menu; the point is not taking it"
    assert m.agent(obs) != [attack], (
        "Syrup Storm lands at 120 on a 130 HP body: attacking now spends the "
        "turn that wins the game")


def test_step63_takes_one_of_the_two_routes_that_close_the_game():
    obs = _obs()
    forest = _hand_play(obs, FOREST)
    stretcher = _hand_play(obs, NIGHT_STRETCHER)
    assert forest is not None and stretcher is not None
    assert m.agent(obs)[0] in (forest, stretcher), (
        "either replacing the stadium or recovering the energy makes it lethal")


def test_the_flag_is_what_decides_it_and_the_board_is_what_sets_the_flag():
    """The counterfactual, run through the whole agent: with the same board and
    ANY other stadium, attacking is right and the agent attacks. It is the card
    on the field that moves the decision, not a rule about this matchup."""
    obs = _obs()
    obs["current"]["stadium"] = [{"id": m.Forest_of_Vitality,
                                  "playerIndex": SEAT, "serial": 999}]
    obs["current"]["stadiumPlayed"] = True
    attack = _option_index(obs, lambda i, o: o.get("attackId") == SYRUP_STORM)
    assert m.agent(obs) == [attack], (
        "with the stadium gone Syrup Storm is 150 >= 130 and the game is over")
